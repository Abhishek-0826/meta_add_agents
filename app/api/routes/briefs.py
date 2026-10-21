from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from redis import Redis
from rq import Queue
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.brief import Brief
from app.models.client import Client
from app.models.job import Job, JobStatus
from app.models.user import User
from app.schemas.schemas import BriefCreate, BriefOut, JobOut

router = APIRouter(prefix="/api/briefs", tags=["briefs"])
settings = get_settings()


def _queue() -> Queue:
    redis_conn = Redis.from_url(settings.REDIS_URL)
    return Queue("adpilot", connection=redis_conn)


@router.post("", response_model=JobOut)
def submit_brief(payload: BriefCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    The intake form (design doc §7.2). Returns a job_id immediately — the
    heavy lifting (multiple LLM calls) happens async in the RQ worker. The
    API layer never blocks on the pipeline.
    """
    client = db.query(Client).filter(Client.id == payload.client_id, Client.org_id == user.org_id).one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    brief = Brief(client_id=client.id, created_by=user.id, payload_jsonb=payload.model_dump(mode="json"))
    db.add(brief)
    db.flush()

    job = Job(brief_id=brief.id, status=JobStatus.queued)
    db.add(job)
    db.commit()
    db.refresh(job)

    _queue().enqueue("app.worker.tasks.run_pipeline_job", str(job.id), job_timeout=600)

    return job


@router.get("/{brief_id}", response_model=BriefOut)
def get_brief(brief_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    brief = db.query(Brief).join(Client).filter(Brief.id == brief_id, Client.org_id == user.org_id).one_or_none()
    if not brief:
        raise HTTPException(status_code=404, detail="Brief not found")
    return brief
