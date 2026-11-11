import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import (
    generate_one_time_token,
    hash_one_time_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.community import AuditLog
from app.models.enums import UserRoleType
from app.models.user import AuthToken, User, UserProfile, UserRole
from app.services.audit import audit
from app.services.geo import as_utc
from app.services.notification_service import send_event_email
from app.schemas.auth import Token, UserLogin, UserRegister

security_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Dependency that extracts, decodes and verifies JWT bearer token."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is deactivated")
    
    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Returns the signed-in user if a valid access token is present, otherwise None (anonymous)."""
    if not credentials or not credentials.credentials:
        return None
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access" or not payload.get("sub"):
        return None
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    return user if user and user.is_active else None


def get_current_active_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency that strictly enforces Administrator privileges."""
    if not user.has_role(UserRoleType.ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Administrator privileges required"
        )
    return user


def get_current_active_host(user: User = Depends(get_current_user)) -> User:
    """Dependency that validates host role."""
    if not user.has_role(UserRoleType.HOST.value) and not user.has_role(UserRoleType.ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Host privileges required"
        )
    return user


def register_user(db: Session, data: UserRegister) -> User:
    """Registers a new user and assigns their initial role."""
    existing = db.query(User).filter(User.email == data.email.lower().strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists"
        )
    
    # Hash password securely
    hashed_pw = hash_password(data.password)
    new_user = User(
        email=data.email.lower().strip(),
        hashed_password=hashed_pw,
        full_name=data.full_name.strip(),
        phone_number=data.phone_number.strip() if data.phone_number else None,
        is_active=True,
        is_verified=False
    )
    db.add(new_user)
    db.flush()  # Populates new_user.id
    
    # Primary role: driver by default, or host
    role_to_assign = data.role.lower().strip()
    if role_to_assign not in [UserRoleType.DRIVER.value, UserRoleType.HOST.value]:
        role_to_assign = UserRoleType.DRIVER.value
    
    db.add(UserRole(user_id=new_user.id, role_name=role_to_assign))
    
    # Every host is also automatically enabled as a driver
    if role_to_assign == UserRoleType.HOST.value:
        db.add(UserRole(user_id=new_user.id, role_name=UserRoleType.DRIVER.value))
    
    # Initialize profile
    db.add(UserProfile(user_id=new_user.id, preferred_city="Bengaluru"))
    
    # Record audit log
    db.add(AuditLog(
        user_id=new_user.id,
        action="USER_REGISTERED",
        resource_type="User",
        resource_id=str(new_user.id),
        details_json=json.dumps({"role": role_to_assign})
    ))
    
    db.commit()
    db.refresh(new_user)
    request_email_verification(db, new_user)
    return new_user


def authenticate_user(db: Session, data: UserLogin) -> Token:
    """Authenticates credentials and returns signed JWT access & refresh tokens."""
    user = db.query(User).filter(User.email == data.email.lower().strip()).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email address or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated"
        )
    
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    
    # Audit login
    db.add(AuditLog(
        user_id=user.id,
        action="USER_LOGIN",
        resource_type="User",
        resource_id=str(user.id)
    ))
    db.commit()
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


# --- one-time tokens: email verification and password reset ----------------------------------
_MAX_TOKENS_PER_HOUR = 3


def _issue_token(db: Session, user: User, purpose: str, ttl: timedelta) -> Optional[str]:
    now = datetime.now(timezone.utc)
    recent = db.query(AuthToken).filter(AuthToken.user_id == user.id, AuthToken.purpose == purpose,
                                        AuthToken.created_at >= now - timedelta(hours=1)).count()
    if recent >= _MAX_TOKENS_PER_HOUR:
        return None
    for old in db.query(AuthToken).filter(AuthToken.user_id == user.id, AuthToken.purpose == purpose,
                                          AuthToken.used_at.is_(None)).all():
        old.used_at = now  # only the newest link works
    raw = generate_one_time_token()
    db.add(AuthToken(user_id=user.id, purpose=purpose, token_hash=hash_one_time_token(raw), expires_at=now + ttl))
    db.commit()
    return raw


def request_email_verification(db: Session, user: User) -> bool:
    if user.is_verified:
        return False
    raw = _issue_token(db, user, "email_verify", timedelta(hours=settings.EMAIL_VERIFY_EXPIRE_HOURS))
    if not raw:
        return False
    link = f"{settings.FRONTEND_URL}/auth/verify-email?token={raw}"
    send_event_email(db, user, "email_verification", {"link": link, "hours": settings.EMAIL_VERIFY_EXPIRE_HOURS})
    return True


def _consume_token(db: Session, raw: str, purpose: str) -> Optional[AuthToken]:
    tok = db.query(AuthToken).filter(AuthToken.token_hash == hash_one_time_token(raw or ""),
                                     AuthToken.purpose == purpose).first()
    if not tok or tok.used_at is not None or as_utc(tok.expires_at) < datetime.now(timezone.utc):
        return None
    return tok


def verify_email(db: Session, raw_token: str) -> User:
    tok = _consume_token(db, raw_token, "email_verify")
    if not tok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This verification link is invalid or has expired")
    user = db.query(User).filter(User.id == tok.user_id).first()
    user.is_verified = True
    user.email_verified_at = datetime.now(timezone.utc)
    tok.used_at = datetime.now(timezone.utc)
    audit(db, user.id, "EMAIL_VERIFIED", "User", user.id)
    db.commit()
    return user


def request_password_reset(db: Session, email: str) -> None:
    """Always silent about whether the account exists."""
    user = db.query(User).filter(User.email == email.lower().strip(), User.is_active == True).first()  # noqa: E712
    if not user:
        return
    raw = _issue_token(db, user, "password_reset", timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES))
    if not raw:
        return
    link = f"{settings.FRONTEND_URL}/auth/reset-password?token={raw}&email={user.email}"
    send_event_email(db, user, "password_reset", {"link": link, "minutes": settings.PASSWORD_RESET_EXPIRE_MINUTES})
    audit(db, user.id, "PASSWORD_RESET_REQUESTED", "User", user.id, commit=True)


def confirm_password_reset(db: Session, email: str, raw_token: str, new_password: str) -> None:
    tok = _consume_token(db, raw_token, "password_reset")
    user = db.query(User).filter(User.id == tok.user_id).first() if tok else None
    if not tok or not user or user.email != email.lower().strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This reset link is invalid or has expired")
    user.hashed_password = hash_password(new_password)
    now = datetime.now(timezone.utc)
    tok.used_at = now
    for other in db.query(AuthToken).filter(AuthToken.user_id == user.id, AuthToken.purpose == "password_reset",
                                            AuthToken.used_at.is_(None)).all():
        other.used_at = now
    audit(db, user.id, "PASSWORD_RESET_COMPLETED", "User", user.id)
    db.commit()
    send_event_email(db, user, "password_changed", {"link": f"{settings.FRONTEND_URL}/auth/forgot-password"})
