import enum
import uuid

from sqlalchemy import Enum, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class LeadStatus(str, enum.Enum):
    NEW = "new"
    QUALIFYING = "qualifying"
    QUALIFIED = "qualified"
    BOOKED = "booked"
    HANDED_OFF = "handed_off"
    LOST = "lost"


class Lead(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "leads"

    channel_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("channels.id"))
    external_id: Mapped[str | None] = mapped_column(String(255), index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255))
    company: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus, values_callable=lambda e: [x.value for x in e]),
        default=LeadStatus.NEW,
        index=True,
    )
    qualification_stage: Mapped[str | None] = mapped_column(String(100))
    qualification_data: Mapped[dict | None] = mapped_column(JSON, default=dict)
    interest_score: Mapped[int] = mapped_column(default=0)
    source: Mapped[str | None] = mapped_column(String(255))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict)

    # Relationships
    channel = relationship("Channel", lazy="selectin")
    conversations = relationship("Conversation", back_populates="lead", lazy="selectin")
