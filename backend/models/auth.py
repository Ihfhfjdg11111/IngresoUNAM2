"""
Pydantic models for authentication and users
"""
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from utils import sanitize_string
from utils.config import MIN_PASSWORD_LENGTH, MAX_PASSWORD_LENGTH, MAX_NAME_LENGTH


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < MIN_PASSWORD_LENGTH:
            raise ValueError(f'Password must be at least {MIN_PASSWORD_LENGTH} characters')
        if len(v) > MAX_PASSWORD_LENGTH:
            raise ValueError(f'Password must be at most {MAX_PASSWORD_LENGTH} characters')
        return v

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        sanitized = sanitize_string(v, MAX_NAME_LENGTH)
        if not sanitized:
            raise ValueError('Name is required')
        return sanitized


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    email: str
    name: str
    role: str
    picture: Optional[str] = None
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserListResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    email: str
    name: str
    role: str
    picture: Optional[str] = None
    created_at: str
    attempts_count: Optional[int] = 0


class RoleUpdateRequest(BaseModel):
    role: str

    @field_validator('role')
    @classmethod
    def validate_role(cls, v):
        if v not in ["student", "admin"]:
            raise ValueError('Role must be student or admin')
        return v
