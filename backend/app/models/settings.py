import uuid

from sqlalchemy import ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin


class SystemSettings(UUIDMixin, Base):
    __tablename__ = "system_settings"
    __table_args__ = (
        UniqueConstraint("key", "owner_id", name="uq_settings_key_owner"),
    )

    key: Mapped[str] = mapped_column(String(255), index=True)
    value: Mapped[dict | None] = mapped_column(JSON)
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=True, index=True
    )

    owner = relationship("AdminUser")
