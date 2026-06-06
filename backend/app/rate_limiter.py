from __future__ import annotations

import time

from app.services.auth_service import auth_service


class RateLimiter:
    """Redis-based sliding-window rate limiter."""

    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def is_allowed(self, key: str) -> bool:
        """Return True if the request is within the rate limit."""
        now = time.time()
        window_start = now - self.window_seconds

        try:
            r = await auth_service._get_redis()
            pipe = r.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, self.window_seconds)
            _, count, _, _ = await pipe.execute()
            return count < self.max_requests
        except Exception:
            return True  # Fail open if Redis is down


rate_limiter = RateLimiter(max_requests=5, window_seconds=60)
