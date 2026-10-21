"""
Design doc §11 scheduled jobs: Insights sync, daily 06:00 IST — pulls
yesterday's performance for every active meta_object and stores it in
insights_daily. Exposed here both as a manual-trigger route and as the
function the cron/scheduler calls.
"""
import logging
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import SessionLocal, get_db
from app.models.brief import Brief
from app.models.campaign_draft import CampaignDraft
from app.models.client import Client
from app.models.insights_daily import InsightsDaily
from app.models.job import Job
from app.models.meta_connection import MetaConnection
from app.models.meta_object import MetaObject
from app.models.user import User
from app.services.encryption import decrypt_token
from app.services.meta_client import MetaClient, MetaAPIError

logger = logging.getLogger("adpilot.insights")
router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.get("/{meta_object_id}")
def get_insights(meta_object_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (
        db.query(InsightsDaily)
        .filter(InsightsDaily.meta_object_id == meta_object_id)
        .order_by(InsightsDaily.date.desc())
        .limit(30)
        .all()
    )
    return rows


@router.post("/sync")
def trigger_sync(user: User = Depends(get_current_user)):
    """Manual trigger for the scheduled job below — useful for testing without waiting for cron."""
    sync_all_insights()
    return {"ok": True}


def sync_all_insights() -> None:
    """Called by the scheduled job (design doc §11: 'Insights sync, Daily 06:00 IST')."""
    db = SessionLocal()
    try:
        active_campaigns = db.query(MetaObject).filter(MetaObject.object_type == "campaign", MetaObject.status == "ACTIVE").all()
        for meta_obj in active_campaigns:
            try:
                draft = db.get(CampaignDraft, meta_obj.draft_id)
                job = db.get(Job, draft.job_id)
                brief = db.get(Brief, job.brief_id)
                connection = (
                    db.query(MetaConnection)
                    .filter(MetaConnection.client_id == brief.client_id, MetaConnection.status == "connected")
                    .one_or_none()
                )
                if not connection:
                    continue

                token = decrypt_token(connection.access_token_encrypted)
                meta = MetaClient(access_token=token, ad_account_id=connection.ad_account_id)
                insights = meta.get_insights(meta_obj.meta_id, date_preset="yesterday")

                for row in insights:
                    record = InsightsDaily(
                        meta_object_id=meta_obj.id,
                        date=date.today(),
                        impressions=int(row.get("impressions", 0)),
                        clicks=int(row.get("clicks", 0)),
                        spend=float(row.get("spend", 0.0)),
                        ctr=float(row.get("ctr", 0.0)),
                        cpc=float(row.get("cpc", 0.0)),
                        cpm=float(row.get("cpm", 0.0)),
                    )
                    db.add(record)
                db.commit()
            except MetaAPIError as e:
                logger.warning("Insights sync failed for meta_object %s: %s", meta_obj.id, e)
                db.rollback()
    finally:
        db.close()
