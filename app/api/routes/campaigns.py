"""
Design doc §7.3: The two-step separation is deliberate.
  1. APPROVE -> CREATE PAUSED   validates everything against Meta's real API
     (targeting resolves, creative uploads, policy passes) while spending nothing.
  2. ACTIVATE CAMPAIGN          a single, isolated, deliberate action, gated on
     the human typing the budget back to confirm.
"""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from redis import Redis
from rq import Queue
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.brief import Brief
from app.models.campaign_draft import CampaignDraft
from app.models.client import Client
from app.models.job import Job
from app.models.user import User
from app.schemas.schemas import ActivateRequest, CampaignDraftOut, DraftEditRequest

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])
settings = get_settings()


def _queue() -> Queue:
    redis_conn = Redis.from_url(settings.REDIS_URL)
    return Queue("adpilot", connection=redis_conn)


def _load_draft_for_org(draft_id: UUID, db: Session, org_id: UUID) -> CampaignDraft:
    draft = (
        db.query(CampaignDraft)
        .join(Job, CampaignDraft.job_id == Job.id)
        .join(Brief, Job.brief_id == Brief.id)
        .join(Client, Brief.client_id == Client.id)
        .filter(CampaignDraft.id == draft_id, Client.org_id == org_id)
        .one_or_none()
    )
    if not draft:
        raise HTTPException(status_code=404, detail="Campaign draft not found")
    return draft


@router.get("/{draft_id}", response_model=CampaignDraftOut)
def get_draft(draft_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _load_draft_for_org(draft_id, db, user.org_id)


@router.patch("/{draft_id}", response_model=CampaignDraftOut)
def edit_draft(draft_id: UUID, payload: DraftEditRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The approval-screen [Regenerate] / inline-edit affordances (design doc §7.3)."""
    draft = _load_draft_for_org(draft_id, db, user.org_id)

    if draft.copy_variants_jsonb and payload.headline is not None:
        variants = draft.copy_variants_jsonb.get("english", {}).get("variants", [])
        if variants:
            variants[0]["headline"] = payload.headline
    if payload.daily_budget_inr is not None:
        from app.agents.budget_guard import check_budget, BudgetGuardViolation
        try:
            check_budget(payload.daily_budget_inr, None)
        except BudgetGuardViolation as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        draft.budget = payload.daily_budget_inr * 100  # paise

    db.commit()
    db.refresh(draft)
    return draft


@router.post("/{draft_id}/approve")
def approve_draft(draft_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Step 1 of 2. Publishes Campaign/AdSet/Creative/Ad to Meta as PAUSED.
    Nothing spends money at this step — it only proves the payload is valid
    against Meta's real API.
    """
    draft = _load_draft_for_org(draft_id, db, user.org_id)
    draft.approved_by = user.id
    draft.approved_at = datetime.now(timezone.utc)
    db.add(AuditLog(org_id=user.org_id, user_id=user.id, action="approve_draft", entity=f"campaign_draft:{draft_id}",
                     before=None, after={"approved_at": draft.approved_at.isoformat()}))
    db.commit()

    _queue().enqueue("app.worker.tasks.publish_draft_to_meta", str(draft_id), job_timeout=300)

    return {"ok": True, "message": "Publishing to Meta as PAUSED — poll GET /api/campaigns/{id} for status"}


@router.post("/{draft_id}/activate")
def activate_draft(draft_id: UUID, payload: ActivateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Step 2 of 2. THE ONLY route in the entire system that results in a live,
    spending ad. Requires the human to type the daily budget back as an
    explicit confirmation (design doc §7.3 approval screen mockup).
    """
    draft = _load_draft_for_org(draft_id, db, user.org_id)

    if draft.approved_by is None:
        raise HTTPException(status_code=400, detail="Draft has not been approved / published to Meta yet")

    expected_budget_inr = (draft.budget or 0) // 100
    if payload.confirm_budget_inr != expected_budget_inr:
        raise HTTPException(
            status_code=400,
            detail=f"Budget confirmation mismatch: expected {expected_budget_inr}, got {payload.confirm_budget_inr}. "
                   f"Type the exact daily budget shown on the approval screen to activate.",
        )

    db.add(AuditLog(org_id=user.org_id, user_id=user.id, action="activate_campaign", entity=f"campaign_draft:{draft_id}",
                     before={"status": "PAUSED"}, after={"status": "ACTIVE", "confirmed_budget": payload.confirm_budget_inr}))
    db.commit()

    _queue().enqueue("app.worker.tasks.activate_campaign", str(draft_id), str(user.id), job_timeout=120)

    return {"ok": True, "message": "Activation requested — campaign will go live shortly"}
