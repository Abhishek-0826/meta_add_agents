from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ---- Auth ----
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    org_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- Clients ----
class ClientCreate(BaseModel):
    name: str
    industry: str | None = None
    website: str | None = None
    brand_voice: str | None = None
    default_language: str = "en"


class ClientOut(BaseModel):
    id: UUID
    name: str
    industry: str | None
    website: str | None
    default_language: str
    created_at: datetime

    class Config:
        from_attributes = True


class GuardRailsCreate(BaseModel):
    max_daily_budget: int
    max_lifetime_budget: int
    allowed_objectives: list[str] = []
    blocked_keywords: list[str] = []


# ---- Meta OAuth ----
class MetaConnectionOut(BaseModel):
    id: UUID
    client_id: UUID
    ad_account_id: str | None
    page_id: str | None
    ig_account_id: str | None
    whatsapp_id: str | None
    status: str

    class Config:
        from_attributes = True


class MetaAssetSelection(BaseModel):
    ad_account_id: str
    page_id: str
    ig_account_id: str | None = None
    whatsapp_id: str | None = None


# ---- Briefs / campaign intake (design doc §7.2) ----
class BriefCreate(BaseModel):
    client_id: UUID

    # WHAT
    product: str
    selling_points: str
    offer: str | None = None
    landing_destination: str

    # WHERE
    platform: str  # facebook | instagram | whatsapp
    placement: str = "auto"  # feed | stories | reels | auto
    countries: list[str]
    languages: list[str]

    # WHO TO
    age_range: str = "18-65"
    gender: str = "all"
    audience_description: str | None = None
    exclusions: str | None = None

    # AD TYPE
    objective: str  # awareness | traffic | leads | sales
    format: str = "single_image"
    creative_choice: str = "upload"  # upload | generate
    uploaded_asset_urls: list[str] = []

    # MONEY
    budget_type: str = "daily"  # daily | lifetime
    budget_amount: int
    start_date: str | None = None
    end_date: str | None = None


class BriefOut(BaseModel):
    id: UUID
    client_id: UUID
    payload_jsonb: dict
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Jobs ----
class JobOut(BaseModel):
    id: UUID
    brief_id: UUID
    status: str
    current_node: str | None
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None

    class Config:
        from_attributes = True


# ---- Campaign drafts / approval ----
class CampaignDraftOut(BaseModel):
    id: UUID
    job_id: UUID
    research_jsonb: dict | None
    copy_variants_jsonb: dict | None
    targeting_jsonb: dict | None
    creative_urls: list[str]
    budget: int | None
    approved_by: UUID | None
    approved_at: datetime | None

    class Config:
        from_attributes = True


class DraftEditRequest(BaseModel):
    headline: str | None = None
    primary_text: str | None = None
    description: str | None = None
    cta: str | None = None
    daily_budget_inr: int | None = None


class ActivateRequest(BaseModel):
    confirm_budget_inr: int = Field(description="Client must type the daily budget to confirm — safety check against fat-finger activation")
