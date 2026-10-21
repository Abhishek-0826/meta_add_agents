import uuid
from datetime import date as date_type

from sqlalchemy import Integer, Float, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InsightsDaily(Base):
    """Daily performance rollup, pulled by the analytics sync job (design doc §11)."""

    __tablename__ = "insights_daily"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meta_object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("meta_objects.id"), nullable=False)
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    spend: Mapped[float] = mapped_column(Float, default=0.0)
    conversions: Mapped[int] = mapped_column(Integer, default=0)
    ctr: Mapped[float] = mapped_column(Float, default=0.0)
    cpc: Mapped[float] = mapped_column(Float, default=0.0)
    cpm: Mapped[float] = mapped_column(Float, default=0.0)
