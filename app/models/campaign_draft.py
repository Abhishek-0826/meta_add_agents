import uuid
from datetime import datetime

from sqlalchemy import Integer, DateTime, ForeignKey, ARRAY, String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CampaignDraft(Base):
    """Everything the agent pipeline produced, before anything touches Meta."""

    __tablename__ = "campaign_drafts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)

    research_jsonb: Mapped[dict] = mapped_column(JSONB, nullable=True)
    copy_variants_jsonb: Mapped[dict] = mapped_column(JSONB, nullable=True)
    targeting_jsonb: Mapped[dict] = mapped_column(JSONB, nullable=True)
    creative_urls: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    budget: Mapped[int] = mapped_column(Integer, nullable=True)  # daily budget, minor units of INR (paise) or whole INR

    approved_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
