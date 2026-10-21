from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.brief import Brief
from app.models.client import Client
from app.models.job import Job
from app.models.user import User
from app.schemas.schemas import JobOut

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The frontend polls this while the pipeline runs (design doc §5: 'the UI can poll and show live status')."""
    job = (
        db.query(Job)
        .join(Brief, Job.brief_id == Brief.id)
        .join(Client, Brief.client_id == Client.id)
        .filter(Job.id == job_id, Client.org_id == user.org_id)
        .one_or_none()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
