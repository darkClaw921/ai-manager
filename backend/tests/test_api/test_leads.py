"""Integration tests for leads API endpoints."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from jose import jwt

from app.models.base import Base
from app.models.channel import Channel, ChannelType
from app.models.lead import Lead, LeadStatus
from app.models.user import AdminUser, UserRole
from tests.conftest import TestSessionLocal, test_engine


# ── Helpers ─────────────────────────────────────────────────────────────

def _make_token(user_id: uuid.UUID) -> str:
    """Create a test JWT access token (matches test-secret-key from conftest mock)."""
    payload = {
        "sub": str(user_id),
        "role": "admin",
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, "test-secret-key", algorithm="HS256")


async def _setup_tables() -> None:
    """Ensure tables exist in the test DB."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _create_admin(email: str = "leads_admin@test.com") -> uuid.UUID:
    """Insert an admin user; return their ID."""
    import bcrypt

    user_id = uuid.uuid4()
    await _setup_tables()
    async with TestSessionLocal() as session:
        password_hash = bcrypt.hashpw(b"testpass", bcrypt.gensalt()).decode()
        user = AdminUser(
            id=user_id,
            email=email,
            password_hash=password_hash,
            full_name="Test Admin",
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(user)
        await session.commit()
    return user_id


async def _create_channel_and_lead(
    channel_name: str = "Test Channel",
    lead_name: str = "API Lead",
    lead_status: LeadStatus = LeadStatus.NEW,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Create a channel + lead; return (lead_id, channel_id)."""
    await _setup_tables()
    channel_id = uuid.uuid4()
    lead_id = uuid.uuid4()
    async with TestSessionLocal() as session:
        channel = Channel(
            id=channel_id,
            name=channel_name,
            type=ChannelType.WEB_WIDGET,
            is_active=True,
            config={},
        )
        lead = Lead(
            id=lead_id,
            channel_id=channel_id,
            external_id=str(uuid.uuid4()),
            name=lead_name,
            status=lead_status,
            qualification_stage="initial",
            qualification_data={},
            interest_score=0,
        )
        session.add(channel)
        session.add(lead)
        await session.commit()
    return lead_id, channel_id


# ── Tests ────────────────────────────────────────────────────────────────


class TestLeadsListEndpoint:
    """Tests for GET /api/v1/leads."""

    async def test_list_unauthorized(self, client: AsyncClient):
        """Return 401/403 when no auth token provided."""
        response = await client.get("/api/v1/leads")
        assert response.status_code in (401, 403)

    async def test_list_empty(self, client: AsyncClient, app):
        """Return empty paginated list when no leads exist."""
        user_id = await _create_admin("list_empty@test.com")
        headers = {"Authorization": f"Bearer {_make_token(user_id)}"}

        response = await client.get("/api/v1/leads", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []
        assert data["page"] == 1

    async def test_list_with_lead(self, client: AsyncClient, app):
        """Return lead when one exists."""
        user_id = await _create_admin("list_lead@test.com")
        await _create_channel_and_lead(lead_name="Found Lead")
        headers = {"Authorization": f"Bearer {_make_token(user_id)}"}

        response = await client.get("/api/v1/leads", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        names = [item["name"] for item in data["items"]]
        assert "Found Lead" in names

    async def test_list_pagination(self, client: AsyncClient, app):
        """Pagination returns correct items and total."""
        user_id = await _create_admin("list_pag@test.com")
        await _setup_tables()
        channel_id = uuid.uuid4()
        async with TestSessionLocal() as session:
            session.add(Channel(
                id=channel_id, name="Pag Chan",
                type=ChannelType.WEB_WIDGET, is_active=True, config={},
            ))
            for i in range(5):
                session.add(Lead(
                    id=uuid.uuid4(), channel_id=channel_id,
                    external_id=f"pag_{i}_{uuid.uuid4()}", name=f"PagLead{i}",
                    status=LeadStatus.NEW, qualification_stage="initial",
                    qualification_data={}, interest_score=0,
                ))
            await session.commit()

        headers = {"Authorization": f"Bearer {_make_token(user_id)}"}
        response = await client.get(
            "/api/v1/leads", headers=headers,
            params={"page": 1, "page_size": 2},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] >= 5

    async def test_list_filter_by_status(self, client: AsyncClient, app):
        """Filter by status returns only matching leads."""
        user_id = await _create_admin("list_filter@test.com")
        await _create_channel_and_lead(lead_name="NewLead", lead_status=LeadStatus.NEW)

        headers = {"Authorization": f"Bearer {_make_token(user_id)}"}
        response = await client.get(
            "/api/v1/leads", headers=headers, params={"status": "new"},
        )
        assert response.status_code == 200
        assert response.json()["total"] >= 1

        response = await client.get(
            "/api/v1/leads", headers=headers, params={"status": "handed_off"},
        )
        assert response.status_code == 200
        data = response.json()
        # No handed_off leads were created in this test
        for item in data["items"]:
            assert item["status"] == "handed_off"


class TestLeadsGetEndpoint:
    """Tests for GET /api/v1/leads/{lead_id}."""

    async def test_get_lead(self, client: AsyncClient, app):
        """Get lead by ID returns correct data."""
        user_id = await _create_admin("get_lead@test.com")
        lead_id, _ = await _create_channel_and_lead(lead_name="Get Me")
        headers = {"Authorization": f"Bearer {_make_token(user_id)}"}

        response = await client.get(f"/api/v1/leads/{lead_id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(lead_id)
        assert data["name"] == "Get Me"

    async def test_get_lead_not_found(self, client: AsyncClient, app):
        """Return 404 for nonexistent lead ID."""
        user_id = await _create_admin("get_404@test.com")
        headers = {"Authorization": f"Bearer {_make_token(user_id)}"}

        response = await client.get(f"/api/v1/leads/{uuid.uuid4()}", headers=headers)
        assert response.status_code == 404

    async def test_get_lead_unauthorized(self, client: AsyncClient, app):
        """Return 401/403 without auth token."""
        lead_id, _ = await _create_channel_and_lead()
        response = await client.get(f"/api/v1/leads/{lead_id}")
        assert response.status_code in (401, 403)


class TestLeadsUpdateEndpoint:
    """Tests for PUT /api/v1/leads/{lead_id}."""

    async def test_update_lead_name(self, client: AsyncClient, app):
        """Update lead name."""
        user_id = await _create_admin("upd_name@test.com")
        lead_id, _ = await _create_channel_and_lead(lead_name="Old Name")
        headers = {"Authorization": f"Bearer {_make_token(user_id)}"}

        response = await client.put(
            f"/api/v1/leads/{lead_id}",
            headers=headers,
            json={"name": "New Name"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "New Name"

    async def test_update_lead_status(self, client: AsyncClient, app):
        """Update lead status."""
        user_id = await _create_admin("upd_status@test.com")
        lead_id, _ = await _create_channel_and_lead()
        headers = {"Authorization": f"Bearer {_make_token(user_id)}"}

        response = await client.put(
            f"/api/v1/leads/{lead_id}",
            headers=headers,
            json={"status": "qualifying"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "qualifying"

    async def test_update_lead_not_found(self, client: AsyncClient, app):
        """Return 404 for nonexistent lead ID."""
        user_id = await _create_admin("upd_404@test.com")
        headers = {"Authorization": f"Bearer {_make_token(user_id)}"}

        response = await client.put(
            f"/api/v1/leads/{uuid.uuid4()}",
            headers=headers,
            json={"name": "X"},
        )
        assert response.status_code == 404


class TestLeadsDeleteEndpoint:
    """Tests for DELETE /api/v1/leads/{lead_id}."""

    async def test_delete_lead(self, client: AsyncClient, app):
        """Delete lead returns 204 and lead is gone."""
        user_id = await _create_admin("del_lead@test.com")
        lead_id, _ = await _create_channel_and_lead(lead_name="Delete Me")
        headers = {"Authorization": f"Bearer {_make_token(user_id)}"}

        response = await client.delete(f"/api/v1/leads/{lead_id}", headers=headers)
        assert response.status_code == 204

        response = await client.get(f"/api/v1/leads/{lead_id}", headers=headers)
        assert response.status_code == 404

    async def test_delete_lead_not_found(self, client: AsyncClient, app):
        """Return 404 when deleting nonexistent lead."""
        user_id = await _create_admin("del_404@test.com")
        headers = {"Authorization": f"Bearer {_make_token(user_id)}"}

        response = await client.delete(
            f"/api/v1/leads/{uuid.uuid4()}", headers=headers
        )
        assert response.status_code == 404
