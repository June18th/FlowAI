from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rate_limiter import RateLimiter


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_first_request_allowed(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        pipe = MagicMock()
        pipe.execute = AsyncMock(return_value=[None, 0, None, None])

        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = pipe

        with patch("app.rate_limiter.auth_service._get_redis", return_value=mock_redis):
            allowed = await limiter.is_allowed("test:127.0.0.1")
            assert allowed is True

    @pytest.mark.asyncio
    async def test_exceeding_limit_blocked(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        pipe = MagicMock()
        pipe.execute = AsyncMock(return_value=[None, 5, None, None])

        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = pipe

        with patch("app.rate_limiter.auth_service._get_redis", return_value=mock_redis):
            allowed = await limiter.is_allowed("test:127.0.0.1")
            assert allowed is False

    @pytest.mark.asyncio
    async def test_redis_failure_fails_open(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)

        with patch("app.rate_limiter.auth_service._get_redis", side_effect=Exception("down")):
            allowed = await limiter.is_allowed("test:127.0.0.1")
            assert allowed is True  # Fail open
