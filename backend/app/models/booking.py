import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class BookingStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class BookingMode(str, enum.Enum):
    INTERNAL = "internal"
    EXTERNAL_LINK = "external_link"
    HANDOFF = "handoff"


class Booking(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "bookings"

    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id"), index=True)
    manager_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admin_users.id"))
    scheduled_at: Mapped[datetime] = mapped_column()
    duration_minutes: Mapped[int] = mapped_column(default=30)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, values_callable=lambda e: [x.value for x in e]),
        default=BookingStatus.PENDING,
    )
    meeting_link: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    lead = relationship("Lead", lazy="selectin")
    manager = relationship("AdminUser", lazy="selectin")


class BookingSettings(UUIDMixin, Base):
    __tablename__ = "booking_settings"

    manager_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("admin_users.id"), unique=True)
    available_days: Mapped[dict | None] = mapped_column(JSON, default=list)
    available_hours: Mapped[dict | None] = mapped_column(JSON, default=dict)
    slot_duration: Mapped[int] = mapped_column(default=30)
    timezone: Mapped[str] = mapped_column(String(100), default="Europe/Moscow")
    booking_link: Mapped[str | None] = mapped_column(String(500))
    booking_mode: Mapped[BookingMode] = mapped_column(
        Enum(BookingMode, values_callable=lambda e: [x.value for x in e]),
        default=BookingMode.INTERNAL,
    )

    # Relationships
    manager = relationship("AdminUser", lazy="selectin")
