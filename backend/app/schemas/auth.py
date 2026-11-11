from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    exp: Optional[int] = None
    type: Optional[str] = None


class UserRoleOut(BaseModel):
    id: int
    role_name: str

    class Config:
        from_attributes = True


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    full_name: str = Field(..., min_length=2)
    phone_number: Optional[str] = None
    role: str = Field(default="driver", description="driver or host")


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    email: EmailStr
    reset_token: str
    new_password: str = Field(..., min_length=8)


class UserProfileOut(BaseModel):
    bio: Optional[str] = None
    preferred_city: Optional[str] = "Bengaluru"
    preferred_language: Optional[str] = "en"
    emergency_contact: Optional[str] = None

    class Config:
        from_attributes = True


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    phone_number: Optional[str] = None
    is_active: bool
    is_verified: bool
    avatar_url: Optional[str] = None
    roles: List[UserRoleOut] = []
    profile: Optional[UserProfileOut] = None
    created_at: datetime

    class Config:
        from_attributes = True
