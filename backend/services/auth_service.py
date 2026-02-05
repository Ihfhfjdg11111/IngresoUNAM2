"""
Authentication service
"""
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict
from utils.config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRATION_HOURS


class AuthService:
    """Service for authentication operations"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt"""
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify a password against its hash"""
        try:
            return bcrypt.checkpw(password.encode(), hashed.encode())
        except Exception:
            return False
    
    @staticmethod
    def create_token(user_id: str, email: str, role: str) -> str:
        """Create a JWT access token"""
        payload = {
            "user_id": user_id,
            "email": email,
            "role": role,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    @staticmethod
    def decode_token(token: str) -> Optional[Dict]:
        """Decode and validate a JWT token"""
        try:
            return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None
    
    @staticmethod
    def generate_id(prefix: str = "") -> str:
        """Generate a unique ID with optional prefix"""
        import uuid
        return f"{prefix}{uuid.uuid4().hex[:12]}"
