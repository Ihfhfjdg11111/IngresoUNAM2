import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.database import db
from utils.config import MONGO_URL

async def test_db():
    print('Testing MongoDB connection...')
    print(f'URL: {MONGO_URL[:40]}...')
    try:
        # Try to ping the database
        result = await db.command('ping')
        print(f'Ping result: {result}')
        # Try to count documents
        count = await db.users.count_documents({})
        print(f'Users count: {count}')
        print('Database connection OK!')
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_db())
