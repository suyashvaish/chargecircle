from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    PasswordResetConfirm,
    PasswordResetRequest,
    Token,
    UserLogin,
    UserOut,
    UserRegister,
)
from app.services.auth_service import (
    authenticate_user,
    confirm_password_reset,
    get_current_user,
    register_user,
    request_email_verification,
    request_password_reset as svc_request_password_reset,
    verify_email,
)
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: UserRegister, db: Session = Depends(get_db)):
    """Registers a new user account with initial role assignment."""
    user = register_user(db, data)
    return user


@router.post("/login", response_model=Token)
def login(data: UserLogin, db: Session = Depends(get_db)):
    """Authenticates email & password, returning JWT access & refresh tokens."""
    return authenticate_user(db, data)


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    """Returns the authenticated user's profile and active roles."""
    return current_user


@router.post("/password-reset/request")
def request_password_reset(data: PasswordResetRequest, db: Session = Depends(get_db)):
    """Emails a single-use reset link if the account exists. The response never reveals whether it does."""
    svc_request_password_reset(db, data.email)
    return {"message": "If an account with that email exists, reset instructions have been sent."}


@router.post("/password-reset/confirm")
def confirm_reset(data: PasswordResetConfirm, db: Session = Depends(get_db)):
    """Sets a new password using a valid, unexpired, single-use token."""
    confirm_password_reset(db, data.email, data.reset_token, data.new_password)
    return {"message": "Password has been successfully updated. Please sign in."}


class VerifyEmailRequest(BaseModel):
    token: str


@router.post("/verify-email")
def confirm_email(data: VerifyEmailRequest, db: Session = Depends(get_db)):
    verify_email(db, data.token)
    return {"message": "Email verified."}


@router.post("/resend-verification")
def resend_verification(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.is_verified:
        return {"message": "Your email is already verified."}
    request_email_verification(db, current_user)
    return {"message": "If a verification email was due, it has been sent."}
