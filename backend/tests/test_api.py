from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_login_success(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.services.auth_service.auth_service._get_redis", return_value=AsyncMock()):
            resp = await client.post("/api/v1/auth/login", json={
                "username": "admin",
                "password": "admin123",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "code" in data


@pytest.mark.asyncio
async def test_login_invalid(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/login", json={
            "username": "nonexistent",
            "password": "wrong",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 401


@pytest.mark.asyncio
async def test_health_endpoint(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200


@pytest.mark.asyncio
async def test_api_docs_accessible(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/openapi.json")
        assert resp.status_code == 200
        assert "FlowAI" in resp.text


@pytest.mark.asyncio
async def test_unauthorized_workflow_access(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/workflows")
        assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_node_types_public(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/node-types")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
