"""Tests for LeadService."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead, LeadStatus
from app.services.lead_service import LeadService


class TestLeadServiceGetOrCreate:
    """Tests for LeadService.get_or_create_lead()."""

    @pytest.mark.asyncio
    async def test_creates_new_lead(self, db_session: AsyncSession, channel_factory):
        channel = await channel_factory()
        service = LeadService(db_session=db_session)

        lead = await service.get_or_create_lead(
            channel_id=channel.id,
            external_id="ext_123",
            name="Test",
        )

        assert lead is not None
        assert lead.external_id == "ext_123"
        assert lead.name == "Test"
        assert lead.status == LeadStatus.NEW
        assert lead.qualification_stage == "initial"

    @pytest.mark.asyncio
    async def test_returns_existing_lead_idempotent(self, db_session: AsyncSession, channel_factory):
        channel = await channel_factory()
        service = LeadService(db_session=db_session)

        lead1 = await service.get_or_create_lead(
            channel_id=channel.id,
            external_id="ext_123",
        )
        lead2 = await service.get_or_create_lead(
            channel_id=channel.id,
            external_id="ext_123",
        )

        assert lead1.id == lead2.id

    @pytest.mark.asyncio
    async def test_different_external_ids_create_different_leads(
        self, db_session: AsyncSession, channel_factory
    ):
        channel = await channel_factory()
        service = LeadService(db_session=db_session)

        lead1 = await service.get_or_create_lead(channel_id=channel.id, external_id="a")
        lead2 = await service.get_or_create_lead(channel_id=channel.id, external_id="b")

        assert lead1.id != lead2.id


class TestLeadServiceCRUD:
    """Tests for LeadService CRUD operations."""

    @pytest.mark.asyncio
    async def test_get_lead(self, db_session: AsyncSession, lead_factory):
        lead = await lead_factory(name="Found Lead")
        service = LeadService(db_session=db_session)

        result = await service.get_lead(lead.id)
        assert result is not None
        assert result.name == "Found Lead"

    @pytest.mark.asyncio
    async def test_get_lead_not_found(self, db_session: AsyncSession):
        service = LeadService(db_session=db_session)
        result = await service.get_lead(uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_update_lead(self, db_session: AsyncSession, lead_factory):
        lead = await lead_factory(name="Original")
        service = LeadService(db_session=db_session)

        updated = await service.update_lead(lead.id, name="Updated", phone="+7999999")
        assert updated is not None
        assert updated.name == "Updated"
        assert updated.phone == "+7999999"

    @pytest.mark.asyncio
    async def test_update_lead_not_found(self, db_session: AsyncSession):
        service = LeadService(db_session=db_session)
        result = await service.update_lead(uuid.uuid4(), name="X")
        assert result is None


class TestLeadServiceQualification:
    """Tests for LeadService.update_qualification()."""

    @pytest.mark.asyncio
    async def test_update_qualification_basic(self, db_session: AsyncSession, lead_factory):
        lead = await lead_factory(status=LeadStatus.NEW)
        service = LeadService(db_session=db_session)

        result = await service.update_qualification(
            lead_id=lead.id,
            stage="needs_discovery",
            data={"needs_discovery": True},
            score=25,
        )

        assert result is not None
        assert result.qualification_stage == "needs_discovery"
        assert result.interest_score == 25
        assert result.status == LeadStatus.QUALIFYING

    @pytest.mark.asyncio
    async def test_auto_status_qualifying(self, db_session: AsyncSession, lead_factory):
        lead = await lead_factory(status=LeadStatus.NEW)
        service = LeadService(db_session=db_session)

        for stage in ["needs_discovery", "budget_check", "timeline_check", "decision_maker"]:
            result = await service.update_qualification(
                lead_id=lead.id, stage=stage, data={}, score=0,
            )
            assert result.status == LeadStatus.QUALIFYING

    @pytest.mark.asyncio
    async def test_auto_status_qualified(self, db_session: AsyncSession, lead_factory):
        lead = await lead_factory(status=LeadStatus.QUALIFYING)
        service = LeadService(db_session=db_session)

        result = await service.update_qualification(
            lead_id=lead.id, stage="qualified", data={}, score=100,
        )
        assert result.status == LeadStatus.QUALIFIED

    @pytest.mark.asyncio
    async def test_update_qualification_not_found(self, db_session: AsyncSession):
        service = LeadService(db_session=db_session)
        result = await service.update_qualification(
            lead_id=uuid.uuid4(), stage="initial", data={}, score=0,
        )
        assert result is None


class TestLeadServiceList:
    """Tests for LeadService.list_leads()."""

    @pytest.mark.asyncio
    async def test_list_empty(self, db_session: AsyncSession):
        service = LeadService(db_session=db_session)
        result = await service.list_leads()
        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_list_with_leads(self, db_session: AsyncSession, lead_factory):
        await lead_factory(name="Lead 1")
        await lead_factory(name="Lead 2")
        service = LeadService(db_session=db_session)

        result = await service.list_leads()
        assert result.total == 2

    @pytest.mark.asyncio
    async def test_list_with_status_filter(self, db_session: AsyncSession, lead_factory):
        await lead_factory(status=LeadStatus.NEW)
        await lead_factory(status=LeadStatus.QUALIFIED)
        service = LeadService(db_session=db_session)

        result = await service.list_leads(filters={"status": LeadStatus.NEW})
        assert result.total == 1

    @pytest.mark.asyncio
    async def test_list_pagination(self, db_session: AsyncSession, lead_factory):
        for i in range(5):
            await lead_factory(name=f"Lead {i}")
        service = LeadService(db_session=db_session)

        result = await service.list_leads(offset=0, limit=2)
        assert len(result.items) == 2
        assert result.total == 5
