"""
Talks to your FastAPI backend. Routes below come from the backend files you shared.
DEMO_MODE=1 runs everything with fake data and no backend.
"""
import base64
import json
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

import requests
import streamlit as st

BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1"
TIMEOUT = 180

E = {
    "login": "/api/auth/login",
    "signup": "/api/auth/signup",
    "clients": "/api/clients",
    "meta_start": "/api/meta/oauth/start",
    "meta_assets": "/api/meta/assets",
    "meta_conn": "/api/meta/connection/{id}",
    "briefs": "/api/briefs",
    "job": "/api/jobs/{id}",
    "drafts": "/api/campaigns",              # GET ?job_id=...  (backend dev must add this)
    "draft": "/api/campaigns/{id}",
    "approve": "/api/campaigns/{id}/approve",
    "activate": "/api/campaigns/{id}/activate",
    "image": "/api/image/generate",
}


class ApiError(Exception):
    def __init__(self, msg, status=None):
        super().__init__(msg)
        self.status = status


def _headers(token):
    return {"Authorization": f"Bearer {token}"} if token and token != "demo" else {}


def _detail(r):
    try:
        d = r.json().get("detail", r.text)
    except ValueError:
        return r.text
    if isinstance(d, list):  # FastAPI validation errors
        return "; ".join(f"{'.'.join(map(str, i.get('loc', [])[1:]))}: {i.get('msg')}" for i in d)
    return d


def _request(method, path, token=None, **kw):
    try:
        r = requests.request(method, BASE_URL + path, headers=_headers(token), timeout=TIMEOUT, **kw)
    except requests.RequestException as e:
        raise ApiError(f"Can't reach the backend at {BASE_URL}. Is uvicorn running? ({e})")
    if r.status_code >= 400:
        raise ApiError(f"{r.status_code}: {_detail(r)}", r.status_code)
    return r.json() if r.content else None


# ------------------------------------------------------------------ demo -----
def _demo():
    return st.session_state.setdefault("demo", {
        "clients": [{"id": "demo-client", "name": "Demo Import Export",
                     "website": "https://example.com", "industry": "Import-export"}],
        "drafts": {},
    })


def _demo_image(product: str) -> str:
    name = escape(product[:28])
    return (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 640 800'>"
        "<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='#1877F2'/>"
        "<stop offset='1' stop-color='#0B3D91'/></linearGradient></defs><rect width='640' height='800' fill='url(#g)'/>"
        f"<text x='320' y='380' font-size='34' fill='white' text-anchor='middle' font-family='sans-serif' "
        f"font-weight='700'>{name}</text><text x='320' y='430' font-size='20' fill='#cfe0ff' text-anchor='middle' "
        "font-family='sans-serif'>Demo preview - not AI generated</text></svg>"
    )


# ------------------------------------------------------------------ media ----
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif")


def media_urls(value):
    """Turn backend image paths into URLs Streamlit can show."""
    if isinstance(value, str):
        value = [value]
    out = []
    for v in value or []:
        if not isinstance(v, str) or not v:
            continue
        v = v.replace("\\", "/")
        if v.startswith(("<svg", "http://", "https://", "data:")):
            out.append(v)
        elif "static/" in v:
            out.append(f"{BASE_URL}/{v[v.index('static/'):]}")
        elif "/" not in v and v.lower().endswith(IMG_EXT):
            out.append(f"{BASE_URL}/static/generated/{v}")
        else:
            out.append(f"{BASE_URL}/{v.lstrip('/')}")
    return out


def images_from_result(result):
    """The image agent's response shape isn't known, so look in the usual places."""
    if not isinstance(result, dict):
        return media_urls(result) if isinstance(result, (str, list)) else []
    for key in ("image_url", "url", "image_urls", "images", "image_path", "path", "file_path", "filename", "file"):
        if result.get(key):
            return media_urls(result[key])
    for key in ("image_base64", "b64_json", "base64"):
        if result.get(key):
            return [base64.b64decode(result[key])]
    return []


# ------------------------------------------------------------------ auth -----
def login(email, password):
    if DEMO_MODE:
        return "demo"
    return _request("POST", E["login"], data={"username": email, "password": password})["access_token"]


def signup(email, password, org_name):
    if DEMO_MODE:
        return "demo"
    return _request("POST", E["signup"], json={"email": email, "password": password, "org_name": org_name})["access_token"]


# --------------------------------------------------------------- clients -----
def list_clients(token):
    return _demo()["clients"] if DEMO_MODE else _request("GET", E["clients"], token)


def create_client(token, name, website, industry):
    body = {"name": name, "website": website or None, "industry": industry or None}
    if DEMO_MODE:
        c = {"id": str(uuid.uuid4()), **body}
        _demo()["clients"].append(c)
        return c
    return _request("POST", E["clients"], token, json=body)


def get_connection(client_id, token):
    if DEMO_MODE:
        return {"status": "connected", "ad_account_id": "act_demo", "page_id": "demo", "ig_account_id": "demo"}
    try:
        return _request("GET", E["meta_conn"].format(id=client_id), token)
    except ApiError as e:
        if e.status == 404:
            return None
        raise


def meta_oauth_url(client_id, token):
    if DEMO_MODE:
        return "https://www.facebook.com"
    return _request("GET", E["meta_start"], token, params={"client_id": client_id})["oauth_url"]


def save_assets(client_id, token, ad_account_id, page_id, ig_account_id):
    if DEMO_MODE:
        return
    _request("POST", E["meta_assets"], token, params={"client_id": client_id},
             json={"ad_account_id": ad_account_id, "page_id": page_id, "ig_account_id": ig_account_id or None})


# ----------------------------------------------------------------- image -----
def preview_image(form, token):
    if DEMO_MODE:
        return [_demo_image(form["product"])]
    place = "Feed" if form["placement"] == "auto" else form["placement"].title()
    body = {
        "product": form["product"],
        "audience": form["audience"] or "General audience",
        "objective": form["objective"].title(),
        "tone": form["tone"],
        "instructions": form["instructions"],
        "placement": f"{form['platform'].title()} {place}",
    }
    return images_from_result(_request("POST", E["image"], token, json=body))


# ---------------------------------------------------------------- brief ------
def create_brief(form, client_id, token):
    now = datetime.now(timezone.utc).isoformat()
    if DEMO_MODE:
        jid = str(uuid.uuid4())
        _demo()["drafts"][jid] = {
            "id": jid, "job_id": jid, "research_jsonb": {"note": "demo data"},
            "copy_variants_jsonb": {"english": {"variants": [{
                "headline": f"Meet {form['product'][:40]}",
                "primary_text": f"Demo copy in a {form['tone'].lower()} tone.",
                "description": "Demo description", "cta": "Learn more"}]}},
            "targeting_jsonb": {"countries": form["countries"], "age_range": form["age_range"]},
            "creative_urls": [_demo_image(form["product"])],
            "budget": int(form["daily_budget"]) * 100, "approved_by": None, "approved_at": None,
        }
        return {"id": jid, "brief_id": jid, "status": "completed", "current_node": None,
                "error": None, "finished_at": now}
    today = date.today()
    # BriefCreate has no "tone" field, so tone rides along inside selling_points.
    selling = (form["instructions"] or form["product"]) + f"\nTone: {form['tone']}"
    payload = {
        "client_id": client_id,
        "product": form["product"],
        "selling_points": selling,
        "landing_destination": form["landing"],
        "platform": form["platform"],
        "placement": form["placement"],
        "countries": form["countries"],
        "languages": form["languages"],
        "age_range": form["age_range"],
        "gender": form["gender"],
        "audience_description": form["audience"] or None,
        "objective": form["objective"],
        "format": "single_image",
        "creative_choice": "generate",
        "uploaded_asset_urls": [],
        "budget_type": "daily",
        "budget_amount": int(form["daily_budget"]),
        "start_date": today.isoformat(),
        "end_date": (today + timedelta(days=form["duration_days"])).isoformat(),
    }
    return _request("POST", E["briefs"], token, json=payload)


def get_job(job_id, token):
    if DEMO_MODE:
        return {"id": job_id, "status": "completed", "current_node": None, "error": None,
                "finished_at": datetime.now(timezone.utc).isoformat()}
    return _request("GET", E["job"].format(id=job_id), token)


def find_draft_by_job(job_id, token):
    if DEMO_MODE:
        return _demo()["drafts"].get(job_id)
    try:
        items = _request("GET", E["drafts"], token, params={"job_id": job_id})
    except ApiError as e:
        if e.status in (404, 405, 422):
            raise ApiError("The backend can't look up a campaign by job yet. Ask your backend dev to add "
                           "GET /api/campaigns?job_id=... (code is in my message).", e.status)
        raise
    return items[0] if items else None


def get_draft(draft_id, token):
    if DEMO_MODE:
        return _demo()["drafts"][draft_id]
    return _request("GET", E["draft"].format(id=draft_id), token)


def approve(draft_id, token):
    """Creates the ad on Meta as PAUSED. Nothing spends money."""
    if DEMO_MODE:
        d = _demo()["drafts"][draft_id]
        d["approved_by"], d["approved_at"] = "demo", datetime.now(timezone.utc).isoformat()
        return {"ok": True, "message": "Demo only: nothing was sent to Meta."}
    return _request("POST", E["approve"].format(id=draft_id), token)


def activate(draft_id, confirm_budget_inr, token):
    """Makes the ad live. This spends real money."""
    if DEMO_MODE:
        return {"ok": True, "message": "Demo only: nothing went live."}
    return _request("POST", E["activate"].format(id=draft_id), token,
                    json={"confirm_budget_inr": int(confirm_budget_inr)})


# ---------------------------------------------------- local history file -----
_HIST = Path(__file__).with_name("history.json")


def load_history():
    try:
        return json.loads(_HIST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _save_history(items):
    _HIST.write_text(json.dumps(items, indent=2), encoding="utf-8")


def add_history(entry):
    _save_history([entry] + load_history())


def update_history(job_id, **fields):
    items = load_history()
    for it in items:
        if it.get("job_id") == job_id:
            it.update(fields)
    _save_history(items)


def clear_history():
    _save_history([])