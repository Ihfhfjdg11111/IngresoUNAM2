"""
Google OAuth 2.0 direct implementation
Replaces Emergent AI authentication
"""
import os
import httpx
from typing import Optional, Dict
from datetime import datetime, timezone

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:3000/auth/callback")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


class GoogleOAuthError(Exception):
    """Custom exception for Google OAuth errors"""
    pass


def get_google_auth_url(state: Optional[str] = None) -> str:
    """
    Generate Google OAuth authorization URL
    
    Args:
        state: Optional state parameter for security
        
    Returns:
        Authorization URL to redirect user
    """
    if not GOOGLE_CLIENT_ID:
        raise GoogleOAuthError("GOOGLE_CLIENT_ID not configured")
    
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    
    if state:
        params["state"] = state
    
    from urllib.parse import urlencode
    query_string = urlencode(params)
    return f"{GOOGLE_AUTH_URL}?{query_string}"


async def exchange_code_for_tokens(code: str) -> Dict:
    """
    Exchange authorization code for access tokens
    
    Args:
        code: Authorization code from Google callback
        
    Returns:
        Dictionary with access_token, refresh_token, etc.
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise GoogleOAuthError("Google OAuth credentials not configured")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code != 200:
            error_data = response.json()
            raise GoogleOAuthError(f"Token exchange failed: {error_data.get('error_description', 'Unknown error')}")
        
        return response.json()


async def get_user_info(access_token: str) -> Dict:
    """
    Get user info from Google using access token
    
    Args:
        access_token: Valid Google access token
        
    Returns:
        User info: email, name, picture, etc.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if response.status_code != 200:
            raise GoogleOAuthError("Failed to fetch user info")
        
        return response.json()


async def verify_google_token(id_token: str) -> Optional[Dict]:
    """
    Verify Google ID token (for one-tap sign-in or mobile apps)
    
    Args:
        id_token: Google ID token
        
    Returns:
        Decoded token payload if valid, None otherwise
    """
    import jwt
    from jwt import PyJWKClient
    
    try:
        # Fetch Google's public keys
        jwks_url = "https://www.googleapis.com/oauth2/v3/certs"
        jwks_client = PyJWKClient(jwks_url)
        
        # Get signing key
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)
        
        # Verify token
        payload = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=GOOGLE_CLIENT_ID,
            issuer=["https://accounts.google.com", "accounts.google.com"]
        )
        
        return payload
    except Exception as e:
        print(f"Token verification failed: {e}")
        return None


async def refresh_access_token(refresh_token: str) -> Dict:
    """
    Refresh an expired access token
    
    Args:
        refresh_token: Valid refresh token
        
    Returns:
        New tokens dictionary
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise GoogleOAuthError("Google OAuth credentials not configured")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "grant_type": "refresh_token",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code != 200:
            raise GoogleOAuthError("Token refresh failed")
        
        return response.json()
