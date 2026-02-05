"""
Pydantic models for users and authentication
"""
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator, EmailStr
from ..utils import sanitize_string, validate_email, MAX_NAME_LENGTH

class UserCreate(BaseModel):
    email: str
    password: str
    name: str

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        email = v.lower().strip()
        if not validate_email(email):
            raise ValueError('Invalid email format')
        return email

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        return v

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        sanitized = sanitize_string(v, MAX_NAME_LENGTH)
        if not sanitized:
            raise ValueError('Name is required')
        return sanitized

class UserLogin(BaseModel):
    email: str
    password: str

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        return v.lower().strip()

class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    email: str
    name: str
    role: str
    picture: Optional[str] = None
    is_premium: bool = False
    created_at: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
