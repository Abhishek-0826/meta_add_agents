"""
Onboarding Step 2-3 (design doc §7.1): per-client Meta OAuth. We use OAuth
per client, NOT a single System User token — a System User token only works
for ad accounts we own, so the moment we serve a second client, that client
must authorise our app against their own account.
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.client import Client
from app.models.meta_connection import MetaConnection
from app.models.user import User
from app.schemas.schemas import MetaAssetSelection, MetaConnectionOut
from app.services.encryption import encrypt_token

router = APIRouter(prefix="/api/meta", tags=["meta-oauth"])
settings = get_settings()

GRAPH_BASE = f"https://graph.facebook.com/{settings.META_API_VERSION}"
OAUTH_SCOPES = "ads_management,pages_manage_ads,business_management"


@router.get("/oauth/start")
def start_oauth(client_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Returns the Meta OAuth dialog URL the frontend should redirect the user to."""
    client = db.query(Client).filter(Client.id == client_id, Client.org_id == user.org_id).one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    url = (
        "https://www.facebook.com/v21.0/dialog/oauth"
        f"?client_id={settings.META_APP_ID}"
        f"&redirect_uri={settings.META_OAUTH_REDIRECT_URI}"
        f"&state={client_id}"
        f"&scope={OAUTH_SCOPES}"
    )
    return {"oauth_url": url}


@router.get("/oauth/callback")
async def oauth_callback(code: str, state: str, db: Session = Depends(get_db)):
    """
    Meta redirects here after the client grants access. We exchange the short-lived
    code for a token, then exchange THAT for a long-lived token (~60 days), and
    store it encrypted. state carries the client_id we started the flow for.
    """
    client_id = UUID(state)

    async with httpx.AsyncClient() as http:
        # Step 1: exchange code for short-lived token
        resp = await http.get(f"{GRAPH_BASE}/oauth/access_token", params={
            "client_id": settings.META_APP_ID,
            "client_secret": settings.META_APP_SECRET,
            "redirect_uri": settings.META_OAUTH_REDIRECT_URI,
            "code": code,
        })
        resp.raise_for_status()
        short_lived_token = resp.json()["access_token"]

        # Step 2: exchange for long-lived token (~60 days)
        resp = await http.get(f"{GRAPH_BASE}/oauth/access_token", params={
            "grant_type": "fb_exchange_token",
            "client_id": settings.META_APP_ID,
            "client_secret": settings.META_APP_SECRET,
            "fb_exchange_token": short_lived_token,
        })
        resp.raise_for_status()
        data = resp.json()
        long_lived_token = data["access_token"]
        expires_in = data.get("expires_in", 60 * 24 * 3600)

    connection = db.query(MetaConnection).filter(MetaConnection.client_id == client_id).one_or_none()
    if connection is None:
        connection = MetaConnection(client_id=client_id)
        db.add(connection)

    connection.access_token_encrypted = encrypt_token(long_lived_token)
    connection.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    connection.scopes = OAUTH_SCOPES.split(",")
    connection.status = "pending"  # becomes 'connected' once assets are selected
    db.commit()

    return {"ok": True, "message": "Token stored. Now call POST /api/meta/assets to select ad account/page."}


@router.post("/assets", response_model=MetaConnectionOut)
def select_assets(client_id: UUID, payload: MetaAssetSelection, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Onboarding Step 3: client picks which Ad Account / Page / IG / WhatsApp to use."""
    connection = db.query(MetaConnection).filter(MetaConnection.client_id == client_id).one_or_none()
    if connection is None:
        raise HTTPException(status_code=404, detail="No Meta OAuth connection started for this client yet")

    connection.ad_account_id = payload.ad_account_id
    connection.page_id = payload.page_id
    connection.ig_account_id = payload.ig_account_id
    connection.whatsapp_id = payload.whatsapp_id
    connection.status = "connected"
    db.commit()
    db.refresh(connection)
    return connection


@router.get("/connection/{client_id}", response_model=MetaConnectionOut)
def get_connection(client_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    connection = db.query(MetaConnection).filter(MetaConnection.client_id == client_id).one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="No Meta connection for this client")
    return connection
