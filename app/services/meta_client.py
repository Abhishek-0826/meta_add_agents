"""
Thin wrapper around Meta's official facebook_business SDK (design doc §3.1, §3.4).

Design rules baked in here, not left to callers:
  - Every Campaign/AdSet/Ad this wrapper creates is forced to status=PAUSED.
  - Rate-limit headers (x-business-use-case-usage) are parsed and we back off
    at 75% usage (design doc §10 Milestone 1, §13 Risk Register).
  - Interest targeting is resolved through Meta's targeting search API —
    an LLM-suggested interest NAME is never trusted as an interest ID.
"""
import logging
import time
from typing import Any

from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign
from facebook_business.adobjects.adset import AdSet
from facebook_business.adobjects.adcreative import AdCreative
from facebook_business.adobjects.ad import Ad
from facebook_business.exceptions import FacebookRequestError

from app.config import get_settings

logger = logging.getLogger("adpilot.meta")
settings = get_settings()

RATE_LIMIT_BACKOFF_THRESHOLD = 0.75  # back off at 75% of the rate limit window


class MetaAPIError(Exception):
    pass


class MetaClient:
    """One instance per request/job, scoped to a single client's access token."""

    def __init__(self, access_token: str, ad_account_id: str):
        self.ad_account_id = ad_account_id
        self.api = FacebookAdsApi.init(
            app_id=settings.META_APP_ID,
            app_secret=settings.META_APP_SECRET,
            access_token=access_token,
            api_version=settings.META_API_VERSION,
        )
        self.account = AdAccount(f"act_{ad_account_id.lstrip('act_')}")

    # ---- rate limiting -------------------------------------------------

    def _check_backoff(self, headers: dict) -> None:
        usage_header = headers.get("x-business-use-case-usage") or headers.get("x-ad-account-usage")
        if not usage_header:
            return
        try:
            import json as _json
            usage = _json.loads(usage_header)
            pct = max(
                v.get("call_count", 0) for entries in usage.values() for v in entries
            ) if isinstance(usage, dict) else 0
            if pct >= RATE_LIMIT_BACKOFF_THRESHOLD * 100:
                logger.warning("Meta rate limit at %s%% — backing off 5s", pct)
                time.sleep(5)
        except Exception:  # noqa: BLE001 - header parsing is best-effort
            pass

    # ---- targeting resolution -------------------------------------------

    def resolve_interests(self, interest_names: list[str]) -> list[dict]:
        """
        Turn LLM-suggested interest names into real Meta interest IDs via the
        targeting search endpoint. Never trust an LLM-generated interest ID.
        """
        resolved = []
        for name in interest_names:
            try:
                results = self.account.get_ad_account_targeting_search(
                    params={"q": name, "type": "adinterest", "limit": 1}
                )
                if results:
                    r = results[0]
                    resolved.append({"id": r["id"], "name": r["name"]})
            except FacebookRequestError as e:
                logger.warning("Interest resolution failed for %r: %s", name, e)
        return resolved

    # ---- object creation (ALWAYS PAUSED) --------------------------------

    def create_campaign(self, name: str, objective: str, idempotency_key: str) -> dict:
        params = {
            Campaign.Field.name: name,
            Campaign.Field.objective: objective,
            Campaign.Field.status: Campaign.Status.paused,  # NEVER configurable
            Campaign.Field.special_ad_categories: [],
        }
        try:
            campaign = self.account.create_campaign(params=params)
            return {"id": campaign["id"], "status": "PAUSED"}
        except FacebookRequestError as e:
            raise MetaAPIError(f"Campaign creation failed: {e}") from e

    def create_ad_set(self, campaign_id: str, name: str, daily_budget_minor_units: int,
                       targeting: dict, optimization_goal: str, billing_event: str) -> dict:
        params = {
            AdSet.Field.name: name,
            AdSet.Field.campaign_id: campaign_id,
            AdSet.Field.daily_budget: daily_budget_minor_units,
            AdSet.Field.billing_event: billing_event,
            AdSet.Field.optimization_goal: optimization_goal,
            AdSet.Field.targeting: targeting,
            AdSet.Field.status: AdSet.Status.paused,  # NEVER configurable
        }
        try:
            adset = self.account.create_ad_set(params=params)
            return {"id": adset["id"], "status": "PAUSED"}
        except FacebookRequestError as e:
            raise MetaAPIError(f"Ad set creation failed: {e}") from e

    def create_ad_creative(self, name: str, page_id: str, message: str, link: str,
                            image_hash: str | None, headline: str, description: str) -> dict:
        link_data: dict[str, Any] = {
            "message": message,
            "link": link,
            "name": headline,
            "description": description,
        }
        if image_hash:
            link_data["image_hash"] = image_hash

        params = {
            AdCreative.Field.name: name,
            AdCreative.Field.object_story_spec: {
                "page_id": page_id,
                "link_data": link_data,
            },
        }
        try:
            creative = self.account.create_ad_creative(params=params)
            return {"id": creative["id"]}
        except FacebookRequestError as e:
            raise MetaAPIError(f"Ad creative creation failed: {e}") from e

    def create_ad(self, name: str, adset_id: str, creative_id: str) -> dict:
        params = {
            Ad.Field.name: name,
            Ad.Field.adset_id: adset_id,
            Ad.Field.creative: {"creative_id": creative_id},
            Ad.Field.status: Ad.Status.paused,  # NEVER configurable
        }
        try:
            ad = self.account.create_ad(params=params)
            return {"id": ad["id"], "status": "PAUSED"}
        except FacebookRequestError as e:
            raise MetaAPIError(f"Ad creation failed: {e}") from e

    # ---- activation (separate, deliberate) ------------------------------

    def activate(self, object_type: str, meta_id: str) -> dict:
        """The ONLY place in the codebase that sets status=ACTIVE. Called
        exclusively from the /activate route after explicit human confirmation."""
        obj_map = {"campaign": Campaign, "adset": AdSet, "ad": Ad}
        obj_cls = obj_map[object_type]
        obj = obj_cls(meta_id)
        try:
            obj.api_update(params={obj_cls.Field.status: obj_cls.Status.active})
            return {"id": meta_id, "status": "ACTIVE"}
        except FacebookRequestError as e:
            raise MetaAPIError(f"Activation failed: {e}") from e

    # ---- insights ---------------------------------------------------------

    def get_insights(self, object_id: str, date_preset: str = "yesterday") -> list[dict]:
        from facebook_business.adobjects.adsinsights import AdsInsights
        obj = Campaign(object_id)
        fields = [
            AdsInsights.Field.impressions, AdsInsights.Field.clicks, AdsInsights.Field.spend,
            AdsInsights.Field.ctr, AdsInsights.Field.cpc, AdsInsights.Field.cpm,
        ]
        try:
            insights = obj.get_insights(fields=fields, params={"date_preset": date_preset})
            return [dict(i) for i in insights]
        except FacebookRequestError as e:
            raise MetaAPIError(f"Insights fetch failed: {e}") from e
