"""
RQ tasks. Campaign generation takes minutes (multiple LLM calls) — it cannot
live inside an HTTP request, so the API just enqueues a job_id and returns
immediately (design doc §5, §10 Milestone 3-4).
"""
import logging
from datetime import datetime, timezone
from uuid import UUID

from app.agents.graph import get_pipeline
from app.agents.state import PipelineState
from app.database import SessionLocal
from app.models.brief import Brief
from app.models.client import Client
from app.models.guard_rails import GuardRails
from app.models.job import Job, JobStatus
from app.models.campaign_draft import CampaignDraft
from app.models.meta_connection import MetaConnection
from app.models.meta_object import MetaObject
from app.services import idempotency
from app.services.encryption import decrypt_token
from app.services.meta_client import MetaClient, MetaAPIError

logger = logging.getLogger("adpilot.worker")


def run_pipeline_job(job_id: str) -> None:
    """Entry point enqueued by POST /api/briefs. Runs the full LangGraph pipeline
    and, if it completes without halting, persists a CampaignDraft awaiting review."""
    db = SessionLocal()
    try:
        job = db.get(Job, UUID(job_id))
        if job is None:
            logger.error("Job %s not found", job_id)
            return

        job.status = JobStatus.running
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        brief = db.get(Brief, job.brief_id)
        client = db.get(Client, brief.client_id)
        guard_rails = db.query(GuardRails).filter(GuardRails.client_id == client.id).one_or_none()

        initial_state: PipelineState = {
            "job_id": job_id,
            "client_id": str(client.id),
            "brief": brief.payload_jsonb,
            "brand_voice": client.brand_voice or "",
            "default_language": client.default_language or "en",
            "guard_rails": {
                "max_daily_budget": guard_rails.max_daily_budget,
                "max_lifetime_budget": guard_rails.max_lifetime_budget,
                "blocked_keywords": guard_rails.blocked_keywords,
            } if guard_rails else {},
            "errors": [],
        }

        pipeline = get_pipeline()
        final_state: PipelineState = pipeline.invoke(initial_state)

        # Checkpoint the final state regardless of outcome.
        job.langgraph_checkpoint_jsonb = dict(final_state)
        job.current_node = final_state.get("current_node")

        if final_state.get("halted"):
            job.status = JobStatus.failed
            job.error = final_state.get("halt_reason", "Pipeline halted for an unspecified reason")
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            logger.warning("Job %s halted: %s", job_id, job.error)
            return

        payload = final_state["assembled_payload"]
        draft = CampaignDraft(
            job_id=job.id,
            research_jsonb=final_state.get("research"),
            copy_variants_jsonb={
                "english": final_state.get("copy_variants"),
                "translated": final_state.get("translated_copy"),
            },
            targeting_jsonb=payload["adset"]["targeting"],
            creative_urls=payload["creative"].get("asset_urls", []),
            budget=payload["adset"].get("daily_budget_minor_units"),
        )
        db.add(draft)

        job.status = JobStatus.awaiting_review
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Job %s completed — draft %s awaiting human review", job_id, draft.id)

    except Exception as e:  # noqa: BLE001 - worker must never crash silently
        logger.exception("Job %s failed with an unhandled exception", job_id)
        job = db.get(Job, UUID(job_id))
        if job:
            job.status = JobStatus.failed
            job.error = str(e)
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()


def publish_draft_to_meta(draft_id: str) -> None:
    """
    Called after human approval (POST /api/campaigns/{draft_id}/approve).
    Creates Campaign -> AdSet -> Creative -> Ad on Meta, ALWAYS as PAUSED,
    using the idempotency table so a retry after a crash never duplicates
    an object (design doc §8).
    """
    db = SessionLocal()
    try:
        draft = db.get(CampaignDraft, UUID(draft_id))
        job = db.get(Job, draft.job_id)
        brief = db.get(Brief, job.brief_id)
        connection = (
            db.query(MetaConnection)
            .filter(MetaConnection.client_id == brief.client_id, MetaConnection.status == "connected")
            .one_or_none()
        )
        if connection is None:
            raise MetaAPIError("No connected Meta account for this client")

        token = decrypt_token(connection.access_token_encrypted)
        meta = MetaClient(access_token=token, ad_account_id=connection.ad_account_id)

        campaign_obj = idempotency.get_or_create(
            db, draft.id, "campaign",
            lambda: meta.create_campaign(
                name=f"AdPilot Campaign {draft.id}",
                objective=brief.payload_jsonb.get("objective", "OUTCOME_TRAFFIC"),
                idempotency_key=str(draft.id),
            ),
        )

        adset_obj = idempotency.get_or_create(
            db, draft.id, "adset",
            lambda: meta.create_ad_set(
                campaign_id=campaign_obj.meta_id,
                name=f"AdPilot AdSet {draft.id}",
                daily_budget_minor_units=draft.budget,
                targeting=draft.targeting_jsonb,
                optimization_goal="LINK_CLICKS",
                billing_event="IMPRESSIONS",
            ),
        )

        creative_obj = idempotency.get_or_create(
            db, draft.id, "creative",
            lambda: meta.create_ad_creative(
                name=f"AdPilot Creative {draft.id}",
                page_id=connection.page_id,
                message=(draft.copy_variants_jsonb or {}).get("english", {}).get("variants", [{}])[0].get("primary_text", ""),
                link=brief.payload_jsonb.get("landing_destination", ""),
                image_hash=None,
                headline=(draft.copy_variants_jsonb or {}).get("english", {}).get("variants", [{}])[0].get("headline", ""),
                description=(draft.copy_variants_jsonb or {}).get("english", {}).get("variants", [{}])[0].get("description", ""),
            ),
        )

        idempotency.get_or_create(
            db, draft.id, "ad",
            lambda: meta.create_ad(
                name=f"AdPilot Ad {draft.id}",
                adset_id=adset_obj.meta_id,
                creative_id=creative_obj.meta_id,
            ),
        )

        logger.info("Draft %s published to Meta as PAUSED", draft_id)

    except Exception:
        logger.exception("Failed to publish draft %s to Meta", draft_id)
        raise
    finally:
        db.close()


def activate_campaign(draft_id: str, user_id: str) -> None:
    """The ONLY function in the codebase allowed to set status=ACTIVE, and
    only ever called from the explicit 'Go Live' route after human confirmation."""
    db = SessionLocal()
    try:
        draft = db.get(CampaignDraft, UUID(draft_id))
        job = db.get(Job, draft.job_id)
        brief = db.get(Brief, job.brief_id)
        connection = (
            db.query(MetaConnection)
            .filter(MetaConnection.client_id == brief.client_id, MetaConnection.status == "connected")
            .one_or_none()
        )
        token = decrypt_token(connection.access_token_encrypted)
        meta = MetaClient(access_token=token, ad_account_id=connection.ad_account_id)

        campaign_obj = idempotency.get_existing(db, draft.id, "campaign")
        if campaign_obj is None:
            raise MetaAPIError("Campaign has not been created on Meta yet — approve the draft first")

        meta.activate("campaign", campaign_obj.meta_id)
        campaign_obj.status = "ACTIVE"
        campaign_obj.activated_at = datetime.now(timezone.utc)
        campaign_obj.activated_by = UUID(user_id)
        db.commit()
        logger.info("Campaign for draft %s ACTIVATED by user %s", draft_id, user_id)
    finally:
        db.close()
