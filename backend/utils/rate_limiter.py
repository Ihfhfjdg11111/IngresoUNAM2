"""
Distributed rate limiting with Redis support.
Falls back to in-memory storage if Redis is not available.
"""
import time
import threading
import os
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from .config import RATE_LIMIT_WINDOW

# Try to import Redis, but make it optional
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class RateLimiter:
    """
    Distributed rate limiter with Redis support.
    Falls back to in-memory storage if Redis is unavailable.
    """
    
    def __init__(self):
        self._redis_client: Optional[redis.Redis] = None
        self._redis_enabled = False
        self._memory_store: Dict[str, List[Tuple[float, int]]] = defaultdict(list)
        self._memory_lock = threading.Lock()
        self._window = RATE_LIMIT_WINDOW
        
        # Try to initialize Redis
        if REDIS_AVAILABLE:
            self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis connection if REDIS_URL is configured"""
        redis_url = os.environ.get('REDIS_URL')
        if not redis_url:
            print("[RateLimiter] REDIS_URL not set, using in-memory storage")
            return
        
        try:
            self._redis_client = redis.from_url(
                redis_url,
                encoding='utf-8',
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                max_connections=10
            )
            self._redis_enabled = True
            print(f"[RateLimiter] Redis connected successfully")
        except Exception as e:
            print(f"[RateLimiter] Redis connection failed: {e}, using in-memory storage")
            self._redis_client = None
            self._redis_enabled = False
    
    async def check_rate_limit(self, key: str, max_requests: int, window: int = None) -> bool:
        """
        Check if request is within rate limit.
        
        Args:
            key: Identifier for the client (e.g., IP + endpoint)
            max_requests: Maximum allowed requests in the window
            window: Time window in seconds (defaults to RATE_LIMIT_WINDOW)
        
        Returns:
            True if request is allowed, False if rate limited
        """
        if window is None:
            window = self._window
        
        if self._redis_enabled and self._redis_client:
            return await self._check_redis(key, max_requests, window)
        else:
            return self._check_memory(key, max_requests, window)
    
    async def _check_redis(self, key: str, max_requests: int, window: int) -> bool:
        """Check rate limit using Redis with sliding window"""
        try:
            now = time.time()
            redis_key = f"ratelimit:{key}"
            
            # Remove old entries (outside the window)
            cutoff = now - window
            await self._redis_client.zremrangebyscore(redis_key, 0, cutoff)
            
            # Count current requests
            current_count = await self._redis_client.zcard(redis_key)
            
            if current_count >= max_requests:
                return False
            
            # Add current request
            await self._redis_client.zadd(redis_key, {str(now): now})
            
            # Set expiration on the key
            await self._redis_client.expire(redis_key, window + 1)
            
            return True
            
        except Exception as e:
            # Fallback to memory if Redis fails
            print(f"[RateLimiter] Redis error, falling back to memory: {e}")
            return self._check_memory(key, max_requests, window)
    
    def _check_memory(self, key: str, max_requests: int, window: int) -> bool:
        """Check rate limit using in-memory storage"""
        current_time = time.time()
        
        with self._memory_lock:
            # Clean old entries for this key
            if key in self._memory_store:
                self._memory_store[key] = [
                    (t, count) for t, count in self._memory_store[key]
                    if current_time - t < window
                ]
            
            # Check if limit exceeded
            request_count = len(self._memory_store[key])
            if request_count >= max_requests:
                return False
            
            # Record this request
            self._memory_store[key].append((current_time, request_count + 1))
            return True
    
    async def get_status(self, key: str, window: int = None) -> dict:
        """
        Get current rate limit status for a key.
        
        Returns:
            dict with 'requests' (count), 'window_remaining' (seconds), 'limit' (max)
        """
        if window is None:
            window = self._window
        
        if self._redis_enabled and self._redis_client:
            return await self._get_redis_status(key, window)
        else:
            return self._get_memory_status(key, window)
    
    async def _get_redis_status(self, key: str, window: int) -> dict:
        """Get status from Redis"""
        try:
            now = time.time()
            redis_key = f"ratelimit:{key}"
            
            # Remove old entries and count
            cutoff = now - window
            await self._redis_client.zremrangebyscore(redis_key, 0, cutoff)
            count = await self._redis_client.zcard(redis_key)
            
            # Get oldest entry for window remaining calculation
            oldest = await self._redis_client.zrange(redis_key, 0, 0, withscores=True)
            if oldest:
                window_remaining = int(window - (now - oldest[0][1]))
            else:
                window_remaining = window
            
            return {
                "requests": count,
                "window_remaining": max(0, window_remaining),
                "limit": None  # Will be set by caller
            }
        except Exception as e:
            return self._get_memory_status(key, window)
    
    def _get_memory_status(self, key: str, window: int) -> dict:
        """Get status from memory"""
        current_time = time.time()
        
        with self._memory_lock:
            if key not in self._memory_store:
                return {"requests": 0, "window_remaining": window, "limit": None}
            
            valid_entries = [
                (t, count) for t, count in self._memory_store[key]
                if current_time - t < window
            ]
            
            if not valid_entries:
                return {"requests": 0, "window_remaining": window, "limit": None}
            
            oldest_timestamp = min(t for t, _ in valid_entries)
            window_remaining = int(window - (current_time - oldest_timestamp))
            
            return {
                "requests": len(valid_entries),
                "window_remaining": max(0, window_remaining),
                "limit": None
            }
    
    def cleanup_memory(self, max_age_seconds: int = 3600) -> int:
        """
        Cleanup old entries from in-memory store.
        Only needed for memory storage; Redis auto-expires.
        
        Returns:
            Number of keys removed
        """
        current_time = time.time()
        keys_to_remove = []
        
        with self._memory_lock:
            for key, timestamps in list(self._memory_store.items()):
                valid_entries = [
                    (t, count) for t, count in timestamps
                    if current_time - t < max_age_seconds
                ]
                
                if valid_entries:
                    self._memory_store[key] = valid_entries
                else:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self._memory_store[key]
        
        return len(keys_to_remove)
    
    async def reset(self, key: str = None) -> bool:
        """
        Reset rate limit for a specific key or all keys.
        Admin function for testing/emergencies.
        
        Args:
            key: Specific key to reset, or None for all
        
        Returns:
            True if successful
        """
        if self._redis_enabled and self._redis_client:
            try:
                if key:
                    await self._redis_client.delete(f"ratelimit:{key}")
                else:
                    # Find and delete all rate limit keys
                    cursor = 0
                    while True:
                        cursor, keys = await self._redis_client.scan(
                            cursor, match="ratelimit:*", count=100
                        )
                        if keys:
                            await self._redis_client.delete(*keys)
                        if cursor == 0:
                            break
                return True
            except Exception as e:
                print(f"[RateLimiter] Redis reset error: {e}")
                return False
        else:
            # Memory reset
            with self._memory_lock:
                if key:
                    self._memory_store.pop(key, None)
                else:
                    self._memory_store.clear()
            return True
    
    @property
    def is_redis_enabled(self) -> bool:
        """Check if Redis is being used"""
        return self._redis_enabled


# Global rate limiter instance
rate_limiter = RateLimiter()


# Convenience functions for backward compatibility
def check_rate_limit(key: str, max_requests: int) -> bool:
    """Synchronous wrapper for backward compatibility - uses in-memory only"""
    return rate_limiter._check_memory(key, max_requests, RATE_LIMIT_WINDOW)


def cleanup_rate_limit_store(max_age_seconds: int = 3600) -> int:
    """Cleanup old entries from memory store"""
    return rate_limiter.cleanup_memory(max_age_seconds)


def get_rate_limit_status(key: str) -> dict:
    """Get rate limit status for a key from memory"""
    return rate_limiter._get_memory_status(key, RATE_LIMIT_WINDOW)
