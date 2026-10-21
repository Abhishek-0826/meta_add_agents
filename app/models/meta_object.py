import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MetaObject(Base):
    """
    THE IDEMPOTENCY BACKBONE (design doc §8).

    We write the Meta ID the instant the API returns it, before doing
    anything else. On retry we check this table first, so a crash between
    creating a Campaign and creating its Ad Set never produces a duplicate
    campaign. object_type in {campaign, adset, creative, ad}.
    """

    __tablename__ = "meta_objects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    draft_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("campaign_drafts.id"), nullable=False)
    object_type: Mapped[str] = mapped_column(String(30), nullable=False)
    meta_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="PAUSED", nullable=False)  # ALWAYS created PAUSED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
