"""
MongoDB indexes setup for IngresoUNAM
Run this module to ensure all required indexes exist.
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from utils.config import MONGO_URL, DB_NAME


async def create_indexes():
    """Create all required MongoDB indexes"""
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    # 1. Unique index to prevent race condition in attempt creation
    # Only one in_progress attempt per user per simulator
    try:
        await db.attempts.create_index(
            [("user_id", 1), ("simulator_id", 1), ("status", 1)],
            unique=True,
            partialFilterExpression={"status": "in_progress"},
            name="unique_in_progress_attempt"
        )
        print("✓ Created unique index on attempts (user_id, simulator_id, status) for in_progress")
    except Exception as e:
        print(f"  Note: attempts index may already exist: {e}")
    
    # 2. TTL index for user_sessions - auto-delete expired sessions after 7 days
    try:
        await db.user_sessions.create_index(
            [("expires_at", 1)],
            expireAfterSeconds=0,  # Delete documents when expires_at is reached
            name="ttl_expired_sessions"
        )
        print("✓ Created TTL index on user_sessions.expires_at")
    except Exception as e:
        print(f"  Note: user_sessions TTL index may already exist: {e}")
    
    # 3. Index for faster user lookups
    try:
        await db.users.create_index([("email", 1)], unique=True, name="unique_email")
        print("✓ Created unique index on users.email")
    except Exception as e:
        print(f"  Note: users.email index may already exist: {e}")
    
    # 4. Index for session token lookups
    try:
        await db.user_sessions.create_index(
            [("session_token", 1)],
            unique=True,
            name="unique_session_token"
        )
        print("✓ Created unique index on user_sessions.session_token")
    except Exception as e:
        print(f"  Note: user_sessions.session_token index may already exist: {e}")
    
    # 5. Index for faster attempt queries
    try:
        await db.attempts.create_index(
            [("user_id", 1), ("started_at", -1)],
            name="user_attempts_sorted"
        )
        print("✓ Created index on attempts (user_id, started_at)")
    except Exception as e:
        print(f"  Note: attempts user index may already exist: {e}")
    
    # 6. Index for subscriptions
    try:
        await db.subscriptions.create_index(
            [("user_id", 1), ("status", 1)],
            name="user_active_subscriptions"
        )
        print("✓ Created index on subscriptions (user_id, status)")
    except Exception as e:
        print(f"  Note: subscriptions index may already exist: {e}")
    
    print("\n✅ All indexes created successfully!")
    client.close()


if __name__ == "__main__":
    asyncio.run(create_indexes())
