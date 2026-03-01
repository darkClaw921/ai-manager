import enum
import uuid

from sqlalchemy import Enum, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class ChannelType(str, enum.Enum):
    TELEGRAM = "telegram"
    WEB_WIDGET = "web_widget"


class Channel(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "channels"

    type: Mapped[ChannelType] = mapped_column(
        Enum(ChannelType, values_callable=lambda e: [x.value for x in e]),
    )
    name: Mapped[str] = mapped_column(String(255))
    config: Mapped[dict | None] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(default=True)
    qualification_script_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("qualification_scripts.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )

    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=True, index=True
    )

    qualification_script = relationship("QualificationScript", lazy="selectin")
    owner = relationship("AdminUser", back_populates="channels")
