"""
Authentication routes - Now using direct Google OAuth (no Emergent)
"""
import os
from fastapi import APIRouter, HTTPException, Depends, Request, Response
from typing import Dict
from datetime import datetime, timezone, timedelta

from models import UserCreate, UserLogin, TokenResponse, UserResponse
from utils.database import db
from utils.config import MAX_NAME_LENGTH, GOOGLE_REDIRECT_URI
from utils.security import sanitize_string
from utils.oauth import (
    get_google_auth_url, 
    exchange_code_for_tokens, 
    get_user_info,
    GoogleOAuthError
)
from services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


async def get_current_user(request: Request) -> Dict:
    """Get current user from session or JWT token"""
    from fastapi.security import HTTPBearer
    security = HTTPBearer(auto_error=False)
    
    # Check cookie first
    session_token = request.cookies.get("session_token")
    if session_token:
        session = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
        if session:
            expires_at = session.get("expires_at")
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at > datetime.now(timezone.utc):
                user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0, "password": 0})
                if user:
                    return user
    
    # Check Authorization header
    credentials = await security(request)
    if credentials:
        token = credentials.credentials
        payload = AuthService.decode_token(token)
        if payload:
            user = await db.users.find_one({"user_id": payload["user_id"]}, {"_id": 0, "password": 0})
            if user:
                return user
    
    raise HTTPException(status_code=401, detail="Authentication required")


async def get_admin_user(user: Dict = Depends(get_current_user)) -> Dict:
    """Verify user is admin"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserCreate, request: Request):
    """Register a new user with email/password"""
    from utils.rate_limiter import rate_limiter
    from utils.config import RATE_LIMIT_MAX_REQUESTS
    
    client_ip = request.client.host if request.client else "unknown"
    if not await rate_limiter.check_rate_limit(f"register_{client_ip}", RATE_LIMIT_MAX_REQUESTS):
        raise HTTPException(status_code=429, detail="Too many requests")
    
    email_lower = user_data.email.lower()
    existing = await db.users.find_one({"email": email_lower}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = AuthService.generate_id("user_")
    now = datetime.now(timezone.utc).isoformat()
    
    await db.users.insert_one({
        "user_id": user_id,
        "email": email_lower,
        "password": AuthService.hash_password(user_data.password),
        "name": user_data.name,
        "role": "student",
        "picture": None,
        "created_at": now,
        "auth_provider": "email"  # Track auth method
    })
    
    token = AuthService.create_token(user_id, email_lower, "student")
    
    return TokenResponse(
        access_token=token,
        user=UserResponse(user_id=user_id, email=email_lower, name=user_data.name, role="student", created_at=now)
    )


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, request: Request):
    """Login with email and password"""
    from utils.rate_limiter import rate_limiter
    from utils.config import RATE_LIMIT_MAX_LOGIN
    
    client_ip = request.client.host if request.client else "unknown"
    if not await rate_limiter.check_rate_limit(f"login_{client_ip}", RATE_LIMIT_MAX_LOGIN):
        raise HTTPException(status_code=429, detail="Too many login attempts")
    
    email_lower = credentials.email.lower()
    user = await db.users.find_one({"email": email_lower}, {"_id": 0})
    
    # Constant-time comparison
    if not user:
        AuthService.hash_password("dummy")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not AuthService.verify_password(credentials.password, user.get("password", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = AuthService.create_token(user["user_id"], user["email"], user["role"])
    
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            user_id=user["user_id"], email=user["email"], name=user["name"],
            role=user["role"], picture=user.get("picture"), created_at=user["created_at"]
        )
    )


@router.get("/google/url")
async def get_google_oauth_url(request: Request):
    """
    Get Google OAuth URL for frontend redirect
    This replaces the Emergent auth flow
    """
    try:
        # Store state in session or return to frontend
        # Frontend should store this and verify on callback
        auth_url = get_google_auth_url()
        return {"auth_url": auth_url}
    except GoogleOAuthError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/google/callback")
async def google_oauth_callback(request: Request, response: Response):
    """
    Handle Google OAuth callback
    Exchanges code for tokens and creates/logs in user
    """
    body = await request.json()
    code = body.get("code")
    
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code required")
    
    try:
        # Exchange code for tokens
        token_data = await exchange_code_for_tokens(code)
        access_token = token_data.get("access_token")
        
        if not access_token:
            raise HTTPException(status_code=400, detail="Failed to obtain access token")
        
        # Get user info from Google
        user_info = await get_user_info(access_token)
        
        email = user_info.get("email", "").lower()
        name = sanitize_string(user_info.get("name", ""), MAX_NAME_LENGTH)
        picture = user_info.get("picture")
        google_id = user_info.get("id")
        
        if not email:
            raise HTTPException(status_code=400, detail="Email not provided by Google")
        
        # Check if user exists
        user = await db.users.find_one({"email": email}, {"_id": 0, "password": 0})
        now = datetime.now(timezone.utc)
        
        if user:
            # Update user info
            await db.users.update_one(
                {"email": email},
                {"$set": {
                    "name": name,
                    "picture": picture,
                    "google_id": google_id,
                    "last_login": now.isoformat()
                }}
            )
            user_id = user["user_id"]
            role = user["role"]
            created_at = user["created_at"]
        else:
            # Create new user
            user_id = AuthService.generate_id("user_")
            role = "student"
            created_at = now.isoformat()
            
            await db.users.insert_one({
                "user_id": user_id,
                "email": email,
                "password": None,  # No password for OAuth users
                "name": name,
                "role": role,
                "picture": picture,
                "google_id": google_id,
                "created_at": created_at,
                "auth_provider": "google",
                "last_login": now.isoformat()
            })
        
        # Create session
        session_token = AuthService.generate_id("session_")
        expires_at = now + timedelta(days=7)
        
        await db.user_sessions.update_one(
            {"user_id": user_id},
            {"$set": {
                "session_token": session_token,
                "expires_at": expires_at.isoformat(),
                "created_at": now.isoformat()
            }},
            upsert=True
        )
        
        # Set cookie - secure only in production
        secure_cookie = os.environ.get("ENV", "development") == "production"
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            secure=secure_cookie,
            samesite="lax",
            path="/",
            max_age=7*24*60*60
        )
        
        # Generate JWT
        jwt_token = AuthService.create_token(user_id, email, role)
        
        return {
            "access_token": jwt_token,
            "user": {
                "user_id": user_id,
                "email": email,
                "name": name,
                "role": role,
                "picture": picture,
                "created_at": created_at
            }
        }
        
    except GoogleOAuthError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")


@router.get("/me", response_model=UserResponse)
async def get_me(user: Dict = Depends(get_current_user)):
    """Get current user info"""
    return UserResponse(
        user_id=user["user_id"], email=user["email"], name=user["name"],
        role=user["role"], picture=user.get("picture"), created_at=user["created_at"]
    )


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Logout user"""
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    secure_cookie = os.environ.get("ENV", "development") == "production"
    response.delete_cookie(key="session_token", path="/", secure=secure_cookie, samesite="lax")
    return {"message": "Logged out"}


@router.post("/link-google")
async def link_google_account(request: Request, user: Dict = Depends(get_current_user)):
    """
    Link Google account to existing email account
    Allows users to login with either method
    """
    body = await request.json()
    code = body.get("code")
    
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code required")
    
    try:
        token_data = await exchange_code_for_tokens(code)
        user_info = await get_user_info(token_data.get("access_token"))
        
        google_email = user_info.get("email", "").lower()
        
        # Verify email matches current user
        if google_email != user["email"]:
            raise HTTPException(
                status_code=400, 
                detail="Google email must match your account email"
            )
        
        # Link accounts
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {
                "google_id": user_info.get("id"),
                "picture": user_info.get("picture") or user.get("picture"),
                "auth_provider": "hybrid"  # Can use both email and Google
            }}
        )
        
        return {"message": "Google account linked successfully"}
        
    except GoogleOAuthError as e:
        raise HTTPException(status_code=400, detail=str(e))
