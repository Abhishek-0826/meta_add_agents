"""
Assembly Agent.

The Assembly Agent is deterministic Python code.

It does NOT use an LLM.

It collects the validated outputs from all previous agents and
constructs the final Meta campaign draft payload.

Pipeline:

    Research
        ↓
    Strategy
        ↓
    Copywriter
        ↓
    Translation
        ↓
    Creative
        ↓
    Image
        ↓
    Compliance
        ↓
    Assembly
        ↓
    Budget Guard

The Assembly Agent is the final transformation layer before
the non-LLM Budget Guard.

The generated campaign is ALWAYS created as PAUSED.

Human review is required before activation.
"""

import logging

from app.agents.state import PipelineState


logger = logging.getLogger(
    "adpilot.agents.assembly"
)


# ============================================================
# Meta Objective Mapping
# ============================================================

OPTIMIZATION_GOAL_BY_OBJECTIVE = {
    "OUTCOME_AWARENESS": "REACH",
    "OUTCOME_TRAFFIC": "LINK_CLICKS",
    "OUTCOME_ENGAGEMENT": "POST_ENGAGEMENT",
    "OUTCOME_LEADS": "LEAD_GENERATION",
    "OUTCOME_SALES": "OFFSITE_CONVERSIONS",
    "OUTCOME_APP_PROMOTION": "APP_INSTALLS",
}


BILLING_EVENT_BY_OBJECTIVE = {
    "OUTCOME_AWARENESS": "IMPRESSIONS",
    "OUTCOME_TRAFFIC": "LINK_CLICKS",
    "OUTCOME_ENGAGEMENT": "IMPRESSIONS",
    "OUTCOME_LEADS": "IMPRESSIONS",
    "OUTCOME_SALES": "IMPRESSIONS",
    "OUTCOME_APP_PROMOTION": "IMPRESSIONS",
}


# ============================================================
# Assembly Agent
# ============================================================

def run_assembly_agent(
    state: PipelineState,
) -> PipelineState:
    """
    Assemble the complete campaign draft.

    Reads:

        brief
        research
        strategy
        copy_variants
        translated_copy
        creative
        image
        compliance

    Writes:

        state["assembled_payload"]

    No LLM is used here.
    """

    # --------------------------------------------------------
    # Stop if an earlier agent failed
    # --------------------------------------------------------

    if state.get("halted"):

        logger.warning(
            "Assembly Agent skipped because pipeline is halted"
        )

        return state

    logger.info(
        "Starting Assembly Agent"
    )

    # ========================================================
    # READ COMPLETE PIPELINE STATE
    # ========================================================

    brief = state.get(
        "brief",
        {},
    )

    research = state.get(
        "research",
        {},
    )

    strategy = state.get(
        "strategy",
        {},
    )

    copy_variants = state.get(
        "copy_variants",
        {},
    )

    translated = state.get(
        "translated_copy",
    )

    creative = state.get(
        "creative",
        {},
    )

    image = state.get(
        "image",
        {},
    )

    compliance = state.get(
        "compliance",
        {},
    )

    # ========================================================
    # SAFETY CHECK
    # ========================================================

    if compliance and not compliance.get(
        "passed",
        False,
    ):

        logger.warning(
            "Assembly blocked because compliance failed"
        )

        state["halted"] = True

        state["halt_reason"] = (
            "Assembly blocked because Compliance Agent failed"
        )

        state["current_node"] = "assembly"

        return state

    # ========================================================
    # OBJECTIVE
    # ========================================================

    objective = strategy.get(
        "objective",
        "OUTCOME_TRAFFIC",
    )

    # ========================================================
    # ACTIVE COPY
    # ========================================================

    # If translation exists, use the translated copy for the
    # human-reviewable active campaign copy.
    #
    # Otherwise use the original copywriter variants.

    if translated:
        active_copy = translated.get(
            "variants",
            [],
        )
    else:
        active_copy = copy_variants.get(
            "variants",
            [],
        )

    # Select first variant as the initial draft.
    #
    # All variants are preserved separately for human review.

    best_variant = (
        active_copy[0]
        if active_copy
        else {}
    )

    # ========================================================
    # BUDGET
    # ========================================================

    daily_budget_inr = strategy.get(
        "proposed_daily_budget_inr"
    )

    lifetime_budget_inr = strategy.get(
        "proposed_lifetime_budget_inr"
    )

    # Convert INR to paise.
    daily_budget_minor_units = (
        int(daily_budget_inr * 100)
        if daily_budget_inr is not None
        else None
    )

    lifetime_budget_minor_units = (
        int(lifetime_budget_inr * 100)
        if lifetime_budget_inr is not None
        else None
    )

    # ========================================================
    # AGE TARGETING
    # ========================================================

    age_range = _parse_age(
        brief.get(
            "age_range",
            "18-65",
        )
    )

    # ========================================================
    # INTEREST TARGETING
    # ========================================================

    interest_names = research.get(
        "interest_names",
        [],
    )

    # These are names, not Meta IDs.
    #
    # Actual Meta interest IDs should be resolved by the
    # Meta integration layer before campaign creation.

    # ========================================================
    # GEO TARGETING
    # ========================================================

    countries = brief.get(
        "countries",
        [],
    )

    # ========================================================
    # PLACEMENTS
    # ========================================================

    placements = strategy.get(
        "placements",
        [],
    )

    # ========================================================
    # CREATIVE ASSETS
    # ========================================================

    uploaded_asset_urls = creative.get(
        "asset_urls",
        [],
    )

    generated_image_url = image.get(
        "image_url"
    )

    image_source = image.get(
        "source"
    )

    # --------------------------------------------------------
    # Combine uploaded/generated assets
    # --------------------------------------------------------

    asset_urls = list(
        uploaded_asset_urls
    )

    if (
        image_source == "ai_generated"
        and generated_image_url
        and generated_image_url not in asset_urls
    ):
        asset_urls.append(
            generated_image_url
        )

    # ========================================================
    # BUILD CREATIVE PAYLOAD
    # ========================================================

    creative_payload = {
        "headline": best_variant.get(
            "headline"
        ),

        "primary_text": best_variant.get(
            "primary_text"
        ),

        "description": best_variant.get(
            "description"
        ),

        "cta": best_variant.get(
            "cta"
        ),

        "asset_urls": asset_urls,

        "uploaded_asset_urls": uploaded_asset_urls,

        "generated_image_url": (
            generated_image_url
            if image_source == "ai_generated"
            else None
        ),

        "image_source": image_source,

        "image_model": image.get(
            "model"
        ),

        "image_aspect_ratio": image.get(
            "aspect_ratio"
        ),

        "placements": placements,

        "required_aspect_ratios": creative.get(
            "required_aspect_ratios",
            {},
        ),

        "link": brief.get(
            "landing_destination"
        ),
    }

    # ========================================================
    # BUILD CAMPAIGN PAYLOAD
    # ========================================================

    campaign_payload = {
        "name": (
            f"{brief.get('product', 'Campaign')} "
            f"— {objective}"
        ),

        "objective": objective,

        # IMPORTANT:
        # Never create campaign as ACTIVE.
        "status": "PAUSED",
    }

    # ========================================================
    # BUILD ADSET PAYLOAD
    # ========================================================

    adset_payload = {
        "name": (
            f"{brief.get('product', 'Campaign')} "
            "— AdSet 1"
        ),

        "daily_budget_minor_units": (
            daily_budget_minor_units
        ),

        "lifetime_budget_minor_units": (
            lifetime_budget_minor_units
        ),

        "optimization_goal": (
            OPTIMIZATION_GOAL_BY_OBJECTIVE.get(
                objective,
                "LINK_CLICKS",
            )
        ),

        "billing_event": (
            BILLING_EVENT_BY_OBJECTIVE.get(
                objective,
                "IMPRESSIONS",
            )
        ),

        "targeting": {
            "geo_locations": {
                "countries": countries,
            },

            "age_min": age_range.get(
                "min",
                18,
            ),

            "age_max": age_range.get(
                "max",
                65,
            ),

            # Names only.
            # Meta IDs are resolved later.
            "interests": interest_names,

            "gender": brief.get(
                "gender",
                "all",
            ),

            "audience_description": brief.get(
                "audience_description",
                "",
            ),
        },

        "placements": placements,

        # IMPORTANT:
        # Ad sets are also created paused.
        "status": "PAUSED",
    }

    # ========================================================
    # BUILD AD PAYLOAD
    # ========================================================

    ad_payload = {
        "name": (
            f"{brief.get('product', 'Campaign')} "
            "— Ad 1"
        ),

        # IMPORTANT:
        # Ads are also created paused.
        "status": "PAUSED",
    }

    # ========================================================
    # FINAL ASSEMBLED PAYLOAD
    # ========================================================

    payload = {
        # ----------------------------------------------------
        # Meta objects
        # ----------------------------------------------------

        "campaign": campaign_payload,

        "adset": adset_payload,

        "creative": creative_payload,

        "ad": ad_payload,

        # ----------------------------------------------------
        # All copy variants for human review
        # ----------------------------------------------------

        "variants_for_review": active_copy,

        # ----------------------------------------------------
        # Original copywriter variants
        # ----------------------------------------------------

        "original_copy_variants": copy_variants.get(
            "variants",
            [],
        ),

        # ----------------------------------------------------
        # Translation information
        # ----------------------------------------------------

        "translated_copy": translated,

        "requires_translation_review": bool(
            translated
        ),

        # ----------------------------------------------------
        # Agent outputs
        #
        # These are kept in the draft so the reviewer can
        # understand how the campaign was constructed.
        # ----------------------------------------------------

        "agent_outputs": {
            "research": research,

            "strategy": strategy,

            "copy_variants": copy_variants,

            "translated_copy": translated,

            "creative": creative,

            "image": image,

            "compliance": compliance,
        },

        # ----------------------------------------------------
        # Review metadata
        # ----------------------------------------------------

        "human_review_required": True,

        "status": "PAUSED",

        # ----------------------------------------------------
        # Source information
        # ----------------------------------------------------

        "source": {
            "product": brief.get(
                "product"
            ),

            "platform": brief.get(
                "platform",
                "meta",
            ),

            "objective": objective,

            "creative_choice": brief.get(
                "creative_choice",
                "upload",
            ),
        },
    }

    # ========================================================
    # SAVE ASSEMBLED PAYLOAD
    # ========================================================

    state["assembled_payload"] = payload

    state["current_node"] = "assembly"

    logger.info(
        "Assembly Agent completed successfully"
    )

    return state


# ============================================================
# Age Parser
# ============================================================

def _parse_age(
    age_range: str,
) -> dict:
    """
    Parse common age-range formats.

    Examples:

        25-40
        18-65
        25+
        30

    Falls back to 18-65 when the value cannot be parsed.
    """

    try:

        age_range = str(
            age_range
        ).strip()

        # ----------------------------------------------------
        # Range: 25-40
        # ----------------------------------------------------

        if "-" in age_range:

            lo, hi = (
                age_range
                .replace("+", "")
                .split("-", 1)
            )

            return {
                "min": int(lo),
                "max": int(hi),
            }

        # ----------------------------------------------------
        # 25+
        # ----------------------------------------------------

        if age_range.endswith("+"):

            lo = age_range[:-1]

            return {
                "min": int(lo),
                "max": 65,
            }

        # ----------------------------------------------------
        # Single age: 30
        # ----------------------------------------------------

        age = int(
            age_range
        )

        return {
            "min": age,
            "max": 65,
        }

    except Exception:  # noqa: BLE001

        return {
            "min": 18,
            "max": 65,
        }