import enum
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Enum, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    awaiting_review = "awaiting_review"
    failed = "failed"
    completed = "completed"


class Job(Base):
    """
    One run of the agent pipeline for one brief. `current_node` and
    `langgraph_checkpoint_jsonb` let a crashed worker resume mid-pipeline
    instead of restarting from Research.
    """

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brief_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("briefs.id"), nullable=False)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.queued, nullable=False)
    current_node: Mapped[str] = mapped_column(String(100), nullable=True)
    error: Mapped[str] = mapped_column(Text, nullable=True)
    langgraph_checkpoint_jsonb: Mapped[dict] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
