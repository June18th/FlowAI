from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    def __init__(self):
        self._pool: aioredis.ConnectionPool | None = None
        self._hashed_password: str = pwd_context.hash(settings.default_password)

    def _get_pool(self) -> aioredis.ConnectionPool:
        if self._pool is None:
            self._pool = aioredis.ConnectionPool(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password or None,
                decode_responses=True,
                max_connections=10,
                protocol=2,
            )
        return self._pool

    async def _get_redis(self) -> aioredis.Redis:
        return aioredis.Redis(connection_pool=self._get_pool())

    async def close(self) -> None:
        if self._pool:
            await self._pool.disconnect()
            self._pool = None

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _create_access_token(self, username: str) -> str:
        expire = self._now() + timedelta(minutes=settings.access_token_expiration_minutes)
        payload = {
            "sub": username,
            "tokenType": "access",
            "exp": expire,
            "iat": self._now(),
        }
        return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

    def _create_refresh_token(self) -> str:
        return uuid.uuid4().hex

    async def issue_tokens(self, username: str) -> dict:
        access_token = self._create_access_token(username)
        refresh_token = self._create_refresh_token()
        r = await self._get_redis()
        key = f"auth:refresh:{refresh_token}"
        ttl = settings.refresh_token_expiration_hours * 3600
        await r.setex(key, ttl, username)
        return {
            "token": access_token,
            "refreshToken": refresh_token,
            "user": {"username": username},
        }

    async def login(self, username: str, password: str) -> dict | None:
        if username == settings.default_username and pwd_context.verify(password, self._hashed_password):
            return await self.issue_tokens(username)
        return None

    async def refresh(self, refresh_token: str) -> dict | None:
        r = await self._get_redis()
        key = f"auth:refresh:{refresh_token}"
        username = await r.get(key)
        if not username:
            return None
        await r.delete(key)
        return await self.issue_tokens(username)

    async def logout(self, refresh_token: str | None) -> None:
        if refresh_token:
            r = await self._get_redis()
            await r.delete(f"auth:refresh:{refresh_token}")

    def validate_token(self, token: str) -> str | None:
        try:
            payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
            if payload.get("tokenType") != "access":
                return None
            username = payload.get("sub")
            if username is None:
                return None
            return username
        except JWTError:
            return None

    def get_username_by_token(self, token: str) -> str | None:
        return self.validate_token(token)


auth_service = AuthService()
