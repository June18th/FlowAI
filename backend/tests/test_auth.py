from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.config import settings
from app.services.auth_service import AuthService, pwd_context


class TestAuthService:
    def test_password_hashing(self):
        """bcrypt hash and verify."""
        password = "admin123"
        hashed = pwd_context.hash(password)
        assert hashed != password
        assert len(hashed) > 30
        assert pwd_context.verify(password, hashed)
        assert not pwd_context.verify("wrong", hashed)

    def test_default_password_is_hashed(self):
        """Default password should be hashed at init, not stored in plaintext."""
        auth = AuthService()
        assert auth._hashed_password != settings.default_password
        assert pwd_context.verify(settings.default_password, auth._hashed_password)

    @pytest.mark.asyncio
    async def test_login_rejects_wrong_password(self):
        """Wrong password should return None."""
        auth = AuthService()

        with patch.object(auth, "_get_redis", return_value=AsyncMock()):
            result = await auth.login("admin", "wrongpassword")
            assert result is None
