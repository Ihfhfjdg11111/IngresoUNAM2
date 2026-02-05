import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.database import db
from services.auth_service import AuthService

async def test_login():
    print('Testing login...')
    
    # Create a test user if not exists
    email = "test@test.com"
    user = await db.users.find_one({"email": email})
    
    if not user:
        print(f"Creating test user: {email}")
        user_id = AuthService.generate_id("user_")
        from datetime import datetime, timezone
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "password": AuthService.hash_password("test123"),
            "name": "Test User",
            "role": "student",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        print(f"Test user created: {user_id}")
    else:
        print(f"Test user exists: {user['user_id']}")
        # Update password
        await db.users.update_one(
            {"email": email},
            {"$set": {"password": AuthService.hash_password("test123")}}
        )
        print("Password updated to: test123")
    
    # Verify password
    user = await db.users.find_one({"email": email})
    is_valid = AuthService.verify_password("test123", user["password"])
    print(f"Password verification: {is_valid}")
    
    # Create token
    token = AuthService.create_token(user["user_id"], email, "student")
    print(f"Token created: {token[:30]}...")

if __name__ == "__main__":
    asyncio.run(test_login())
