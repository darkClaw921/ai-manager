"""
Seed script for initial data: admin user, default settings, qualification script.

Usage:
    python -m app.db.seed
"""

import asyncio

import bcrypt
import structlog
from sqlalchemy import select

from app.db.session import async_session_factory
from app.logging_config import setup_logging
from app.models.script import QualificationScript
from app.models.settings import SystemSettings
from app.models.user import AdminUser, UserRole

setup_logging()
logger = structlog.get_logger(__name__)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def seed_admin_user(session) -> None:
    """Create default admin user if not exists."""
    result = await session.execute(
        select(AdminUser).where(AdminUser.email == "admin@example.com")
    )
    if result.scalar_one_or_none() is not None:
        logger.info("Admin user already exists, skipping")
        return

    admin = AdminUser(
        email="admin@example.com",
        password_hash=hash_password("admin123"),
        full_name="System Administrator",
        role=UserRole.ADMIN,
        is_active=True,
    )
    session.add(admin)
    logger.info("Created admin user: admin@example.com")


async def seed_system_settings(session) -> None:
    """Create default system settings if not exist."""
    defaults = [
        {
            "key": "llm_provider",
            "value": "anthropic",
            "description": "LLM provider: anthropic, openai, openrouter",
        },
        {
            "key": "ai_model",
            "value": "claude-sonnet-4-5",
            "description": "AI model used for conversations",
        },
        {
            "key": "max_conversation_messages",
            "value": 50,
            "description": "Maximum number of messages loaded as context for AI",
        },
        {
            "key": "qualification_timeout_hours",
            "value": 24,
            "description": "Hours before a qualifying lead is marked as lost",
        },
        {
            "key": "default_greeting",
            "value": "Здравствуйте! Я виртуальный ассистент. Чем могу помочь?",
            "description": "Default greeting message for new conversations",
        },
        {
            "key": "booking_mode",
            "value": "internal",
            "description": "Booking mode: internal, external_link, handoff",
        },
        {
            "key": "anthropic_api_key",
            "value": "",
            "description": "Anthropic API key (used when llm_provider=anthropic)",
        },
        {
            "key": "openai_api_key",
            "value": "",
            "description": "OpenAI API key (used when llm_provider=openai)",
        },
        {
            "key": "openrouter_api_key",
            "value": "",
            "description": "OpenRouter API key (used when llm_provider=openrouter)",
        },
    ]

    for item in defaults:
        result = await session.execute(
            select(SystemSettings).where(
                SystemSettings.key == item["key"],
                SystemSettings.owner_id.is_(None),
            )
        )
        if result.scalar_one_or_none() is not None:
            logger.info("Setting '%s' already exists, skipping", item["key"])
            continue

        setting = SystemSettings(
            key=item["key"],
            value=item["value"],
            description=item["description"],
        )
        session.add(setting)
        logger.info("Created setting: %s", item["key"])


async def seed_qualification_script(session) -> None:
    """Create default qualification script if not exists."""
    result = await session.execute(
        select(QualificationScript).where(QualificationScript.name == "Default Qualification")
    )
    if result.scalar_one_or_none() is not None:
        logger.info("Default qualification script already exists, skipping")
        return

    stages = [
        {
            "stage_id": "NEEDS_DISCOVERY",
            "order": 1,
            "question_prompt": "Расскажите, какую задачу вы хотите решить? Что сейчас не устраивает?",
            "expected_info": "Описание потребности, текущая проблема",
            "follow_ups": [
                "Как давно вы сталкиваетесь с этой проблемой?",
                "Какие решения уже пробовали?",
            ],
            "next_stage": "BUDGET_CHECK",
        },
        {
            "stage_id": "BUDGET_CHECK",
            "order": 2,
            "question_prompt": "Какой бюджет вы рассматриваете для решения этой задачи?",
            "expected_info": "Диапазон бюджета или готовность обсуждать",
            "follow_ups": [
                "Есть ли уже выделенный бюджет на это?",
            ],
            "next_stage": "TIMELINE_CHECK",
        },
        {
            "stage_id": "TIMELINE_CHECK",
            "order": 3,
            "question_prompt": "В какие сроки вы хотели бы начать работу?",
            "expected_info": "Ожидаемые сроки начала / дедлайн",
            "follow_ups": [
                "Есть ли жёсткие дедлайны?",
            ],
            "next_stage": "DECISION_MAKER",
        },
        {
            "stage_id": "DECISION_MAKER",
            "order": 4,
            "question_prompt": "Кто принимает финальное решение по этому вопросу?",
            "expected_info": "Лицо, принимающее решение",
            "follow_ups": [
                "Будут ли ещё участники в принятии решения?",
            ],
            "next_stage": None,
        },
    ]

    script = QualificationScript(
        name="Default Qualification",
        description="Стандартный скрипт квалификации лидов: выявление потребности, бюджет, сроки, ЛПР",
        stages=stages,
        is_active=True,
    )
    session.add(script)
    logger.info("Created default qualification script with 4 stages")


async def run_seed() -> None:
    """Run all seed operations."""
    logger.info("Starting seed...")

    async with async_session_factory() as session:
        async with session.begin():
            await seed_admin_user(session)
            await seed_system_settings(session)
            await seed_qualification_script(session)

    logger.info("Seed completed successfully")


if __name__ == "__main__":
    asyncio.run(run_seed())
