import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Text, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MetaConnection(Base):
    """
    Per-client Meta asset linkage. THE CRITICAL TABLE for multi-tenant.

    access_token_encrypted is a Fernet-encrypted long-lived token, obtained
    via OAuth for THIS client's own ad account — never a shared System User
    token once we have more than one client (see design doc §7.1).
    """

    __tablename__ = "meta_connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)

    ad_account_id: Mapped[str] = mapped_column(String(64), nullable=True)   # act_XXXXXXXXX
    page_id: Mapped[str] = mapped_column(String(64), nullable=True)
    ig_account_id: Mapped[str] = mapped_column(String(64), nullable=True)
    whatsapp_id: Mapped[str] = mapped_column(String(64), nullable=True)
    business_id: Mapped[str] = mapped_column(String(64), nullable=True)

    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    status: Mapped[str] = mapped_column(String(30), default="pending")  # pending|connected|expired|revoked
