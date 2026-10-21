from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.client import Client
from app.models.guard_rails import GuardRails
from app.models.user import User
from app.schemas.schemas import ClientCreate, ClientOut, GuardRailsCreate

router = APIRouter(prefix="/api/clients", tags=["clients"])


@router.post("", response_model=ClientOut)
def create_client(payload: ClientCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Onboarding Step 1 (design doc §7.1)."""
    client = Client(org_id=user.org_id, **payload.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("", response_model=list[ClientOut])
def list_clients(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Client).filter(Client.org_id == user.org_id).all()


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    client = db.query(Client).filter(Client.id == client_id, Client.org_id == user.org_id).one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.put("/{client_id}/guard-rails")
def set_guard_rails(client_id: UUID, payload: GuardRailsCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Onboarding Step 4: guard rails set by the agency (design doc §7.1).
    approval_required is intentionally NOT a field here — it is always True in v1
    and is not exposed as something an operator can turn off."""
    client = db.query(Client).filter(Client.id == client_id, Client.org_id == user.org_id).one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    from app.agents.budget_guard import MAX_DAILY_BUDGET_INR, MAX_CAMPAIGN_LIFETIME_INR
    if payload.max_daily_budget > MAX_DAILY_BUDGET_INR:
        raise HTTPException(status_code=400, detail=f"max_daily_budget cannot exceed system ceiling of {MAX_DAILY_BUDGET_INR}")
    if payload.max_lifetime_budget > MAX_CAMPAIGN_LIFETIME_INR:
        raise HTTPException(status_code=400, detail=f"max_lifetime_budget cannot exceed system ceiling of {MAX_CAMPAIGN_LIFETIME_INR}")

    existing = db.query(GuardRails).filter(GuardRails.client_id == client_id).one_or_none()
    if existing:
        for k, v in payload.model_dump().items():
            setattr(existing, k, v)
    else:
        existing = GuardRails(client_id=client_id, **payload.model_dump())
        db.add(existing)
    db.commit()
    return {"ok": True}
