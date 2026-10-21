import uuid

from sqlalchemy import Integer, ForeignKey, ARRAY, String, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class GuardRails(Base):
    """
    Agency-configurable ceilings for a client. These are UPPER BOUNDS that
    still get clamped by the hard-coded, non-configurable constants in
    app/agents/budget_guard.py — an agency can only set guard rails tighter
    than the system-wide ceiling, never looser.
    """

    __tablename__ = "guard_rails"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, unique=True)

    max_daily_budget: Mapped[int] = mapped_column(Integer, nullable=False)
    max_lifetime_budget: Mapped[int] = mapped_column(Integer, nullable=False)
    allowed_objectives: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    blocked_keywords: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # always True in v1
