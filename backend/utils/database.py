"""
Database configuration and connection
"""
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
from .config import MONGO_URL, DB_NAME

# MongoDB client and database instance
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]


async def setup_database_indexes():
    """Setup required indexes on startup"""
    # Unique index to prevent race condition in attempt creation
    await db.attempts.create_index(
        [("user_id", 1), ("simulator_id", 1), ("status", 1)],
        unique=True,
        partialFilterExpression={"status": "in_progress"}
    )
    
    # TTL index for user_sessions - auto-delete expired sessions
    await db.user_sessions.create_index(
        [("expires_at", 1)],
        expireAfterSeconds=0
    )
    
    # Index for session tokens
    await db.user_sessions.create_index(
        [("session_token", 1)],
        unique=True
    )
    
    # Index for user email lookups
    await db.users.create_index(
        [("email", 1)],
        unique=True
    )
    
    # Index for faster attempt queries
    await db.attempts.create_index(
        [("user_id", 1), ("started_at", -1)]
    )
