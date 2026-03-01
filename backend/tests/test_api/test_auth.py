"""Integration tests for auth API endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from unittest.mock import patch, MagicMock

from app.models.user import UserRole


class TestLoginEndpoint:
    """Tests for POST /api/v1/auth/login."""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, app):
        """Test successful login with valid credentials."""
        # Create test user via direct DB access
        from app.models.user import AdminUser
        import bcrypt
        import uuid
        from tests.conftest import TestSessionLocal, test_engine
        from app.models.base import Base

        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with TestSessionLocal() as session:
            password_hash = bcrypt.hashpw(
                b"testpass123", bcrypt.gensalt()
            ).decode("utf-8")
            user = AdminUser(
                id=uuid.uuid4(),
                email="login@test.com",
                password_hash=password_hash,
                full_name="Login Test",
                role=UserRole.ADMIN,
                is_active=True,
            )
            session.add(user)
            await session.commit()

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "login@test.com", "password": "testpass123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "login@test.com"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, app):
        """Test login failure with wrong password."""
        from app.models.user import AdminUser
        import bcrypt
        import uuid
        from tests.conftest import TestSessionLocal, test_engine
        from app.models.base import Base

        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with TestSessionLocal() as session:
            password_hash = bcrypt.hashpw(
                b"correctpass", bcrypt.gensalt()
            ).decode("utf-8")
            user = AdminUser(
                id=uuid.uuid4(),
                email="wrong@test.com",
                password_hash=password_hash,
                full_name="Wrong Pass",
                role=UserRole.ADMIN,
                is_active=True,
            )
            session.add(user)
            await session.commit()

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "wrong@test.com", "password": "wrongpass"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login with email that does not exist."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@test.com", "password": "anypass"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_validation_error(self, client: AsyncClient):
        """Test login with missing required fields."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@test.com"},
        )

        assert response.status_code == 422


class TestRefreshEndpoint:
    """Tests for POST /api/v1/auth/refresh."""

    @pytest.mark.asyncio
    async def test_refresh_with_invalid_token(self, client: AsyncClient):
        """Test refresh with an invalid token."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_with_access_token_fails(self, client: AsyncClient):
        """Test refresh with an access token (wrong type) fails."""
        from app.services.auth_service import create_access_token
        token = create_access_token("fake-user-id", "admin")

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": token},
        )

        assert response.status_code == 401
