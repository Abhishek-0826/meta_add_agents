"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organisations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("plan", sa.String(50), nullable=False, server_default="free"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organisations.id"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("owner", "operator", "client", name="userrole"), nullable=False, server_default="operator"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organisations.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("industry", sa.String(255), nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("brand_voice", sa.Text, nullable=True),
        sa.Column("default_language", sa.String(20), nullable=False, server_default="en"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "meta_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("ad_account_id", sa.String(64), nullable=True),
        sa.Column("page_id", sa.String(64), nullable=True),
        sa.Column("ig_account_id", sa.String(64), nullable=True),
        sa.Column("whatsapp_id", sa.String(64), nullable=True),
        sa.Column("business_id", sa.String(64), nullable=True),
        sa.Column("access_token_encrypted", sa.Text, nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
    )
    op.create_index("ix_meta_connections_client_id", "meta_connections", ["client_id"])

    op.create_table(
        "guard_rails",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False, unique=True),
        sa.Column("max_daily_budget", sa.Integer, nullable=False),
        sa.Column("max_lifetime_budget", sa.Integer, nullable=False),
        sa.Column("allowed_objectives", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("blocked_keywords", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("approval_required", sa.Boolean, nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "briefs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("payload_jsonb", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brief_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("briefs.id"), nullable=False),
        sa.Column("status", sa.Enum("queued", "running", "awaiting_review", "failed", "completed", name="jobstatus"), nullable=False, server_default="queued"),
        sa.Column("current_node", sa.String(100), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("langgraph_checkpoint_jsonb", postgresql.JSONB, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "campaign_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("research_jsonb", postgresql.JSONB, nullable=True),
        sa.Column("copy_variants_jsonb", postgresql.JSONB, nullable=True),
        sa.Column("targeting_jsonb", postgresql.JSONB, nullable=True),
        sa.Column("creative_urls", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("budget", sa.Integer, nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "meta_objects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaign_drafts.id"), nullable=False),
        sa.Column("object_type", sa.String(30), nullable=False),
        sa.Column("meta_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="PAUSED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_meta_objects_meta_id", "meta_objects", ["meta_id"])
    op.create_index("ix_meta_objects_draft_type", "meta_objects", ["draft_id", "object_type"], unique=True)

    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organisations.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity", sa.String(100), nullable=False),
        sa.Column("before", postgresql.JSONB, nullable=True),
        sa.Column("after", postgresql.JSONB, nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "insights_daily",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("meta_object_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("meta_objects.id"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("impressions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("clicks", sa.Integer, nullable=False, server_default="0"),
        sa.Column("spend", sa.Float, nullable=False, server_default="0"),
        sa.Column("conversions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ctr", sa.Float, nullable=False, server_default="0"),
        sa.Column("cpc", sa.Float, nullable=False, server_default="0"),
        sa.Column("cpm", sa.Float, nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("insights_daily")
    op.drop_table("audit_log")
    op.drop_table("meta_objects")
    op.drop_table("campaign_drafts")
    op.drop_table("jobs")
    op.drop_table("briefs")
    op.drop_table("guard_rails")
    op.drop_table("meta_connections")
    op.drop_table("clients")
    op.drop_table("users")
    op.drop_table("organisations")
    op.execute("DROP TYPE IF EXISTS jobstatus")
    op.execute("DROP TYPE IF EXISTS userrole")
