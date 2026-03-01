import uuid

from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class QualificationScript(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "qualification_scripts"

    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    stages: Mapped[dict | None] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(default=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=True, index=True
    )

    score_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    owner = relationship("AdminUser")
    faq_items = relationship("FAQItem", back_populates="qualification_script")
    objection_scripts = relationship("ObjectionScript", back_populates="qualification_script")


class FAQItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "faq_items"

    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(255))
    keywords: Mapped[list[str] | None] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(default=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    qualification_script_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("qualification_scripts.id", ondelete="SET NULL"), nullable=True, index=True
    )

    owner = relationship("AdminUser")
    qualification_script = relationship("QualificationScript", back_populates="faq_items")


class ObjectionScript(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "objection_scripts"

    objection_pattern: Mapped[str] = mapped_column(Text)
    response_template: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(255))
    priority: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    qualification_script_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("qualification_scripts.id", ondelete="SET NULL"), nullable=True, index=True
    )

    owner = relationship("AdminUser")
    qualification_script = relationship("QualificationScript", back_populates="objection_scripts")
