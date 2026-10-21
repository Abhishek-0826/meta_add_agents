"""
Translation Agent.

The Translation Agent is conditional.

It runs only when the target language/locale differs from
the campaign's source/default language.

Input:
    - Original campaign brief
    - Strategy Agent output
    - Copywriter Agent output
    - Brand voice

Output:
    - Translated/localized ad copy
    - Target locale
    - Mandatory human-review flag

The result is stored in:

    state["translated_copy"]

IMPORTANT:
    Translated copy ALWAYS requires human review.

    The LLM cannot disable the human-review requirement.
"""


import logging

from pydantic import BaseModel, Field

from app.agents.state import PipelineState
from app.services.llm_client import generate_structured


logger = logging.getLogger(
    "adpilot.agents.translation"
)


# ============================================================
# TRANSLATED COPY VARIANT
# ============================================================

class TranslatedVariant(BaseModel):

    primary_text: str

    headline: str

    description: str

    cta: str


# ============================================================
# TRANSLATION OUTPUT
# ============================================================

class TranslationOutput(BaseModel):

    variants: list[TranslatedVariant] = Field(
        description=(
            "Translated/localized versions of all "
            "source copy variants."
        )
    )

    target_locale: str = Field(
        description=(
            "Target language or locale used for "
            "the translation."
        )
    )

    requires_human_review: bool = True


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are the Translation Agent in AdPilot.

Your job is to translate and localize Meta advertising
copy for the requested target locale.

You receive:

1. Original campaign brief.
2. Strategy Agent output.
3. Copywriter Agent output.
4. Brand voice.

IMPORTANT:

- Preserve the original persuasive intent.
- Preserve the meaning of the offer.
- Preserve the product/service information.
- Preserve the CTA intent.
- Do not invent claims.
- Do not invent discounts.
- Do not add product features.
- Do not translate literally when that creates unnatural
  advertising language.
- Use natural commercial language for the target locale.
- Preserve the brand voice.

For Arabic:

- Use Modern Standard Arabic (MSA) by default.
- If the campaign brief specifies a dialect, follow it.
- Be careful with commercial register and regional wording.

The translated copy will ALWAYS require human review
before publication.

Return only the structured response required by the schema.
"""


# ============================================================
# SHOULD TRANSLATE
# ============================================================

def should_translate(
    state: PipelineState,
) -> bool:

    brief = state.get(
        "brief",
        {},
    )

    target_locales = (
        brief.get("languages") or []
    )

    source_locale = state.get(
        "default_language",
        "en",
    )

    return any(
        locale != source_locale
        for locale in target_locales
    )


# ============================================================
# TRANSLATION AGENT
# ============================================================

def run_translation_agent(
    state: PipelineState,
) -> PipelineState:

    # ========================================================
    # STOP IF PREVIOUS AGENT FAILED
    # ========================================================

    if state.get("halted"):

        logger.warning(
            "Translation Agent skipped because "
            "pipeline is halted"
        )

        return state


    logger.info(
        "Starting Translation Agent"
    )


    # ========================================================
    # CHECK WHETHER TRANSLATION IS REQUIRED
    # ========================================================

    if not should_translate(state):

        logger.info(
            "Translation not required"
        )

        # Keep this as None because there is no
        # translated copy when source and target
        # languages are the same.
        state["translated_copy"] = None

        state["current_node"] = (
            "translation_skipped"
        )

        return state


    # ========================================================
    # READ CAMPAIGN BRIEF
    # ========================================================

    brief = state.get(
        "brief",
        {},
    )


    # ========================================================
    # READ COPYWRITER OUTPUT
    # ========================================================

    copy_variants = state.get(
        "copy_variants",
        {},
    )


    # ========================================================
    # READ STRATEGY OUTPUT
    # ========================================================

    strategy = state.get(
        "strategy",
        {},
    )


    # ========================================================
    # READ BRAND CONTEXT
    # ========================================================

    brand_voice = state.get(
        "brand_voice",
        "friendly, clear, professional",
    )


    # ========================================================
    # SOURCE LANGUAGE
    # ========================================================

    source_locale = state.get(
        "default_language",
        "en",
    )


    # ========================================================
    # FIND TARGET LOCALE
    # ========================================================

    target_locales = (
        brief.get("languages") or []
    )

    target_locale = next(
        (
            locale
            for locale in target_locales
            if locale != source_locale
        ),
        None,
    )


    # ========================================================
    # SAFETY CHECK
    # ========================================================

    if not target_locale:

        logger.warning(
            "Translation requested but no target locale "
            "was found"
        )

        state["translated_copy"] = None

        state["current_node"] = (
            "translation_skipped"
        )

        return state


    # ========================================================
    # BUILD USER PROMPT
    # ========================================================

    user_prompt = f"""
Translate and localize the following Meta advertising
campaign.

============================================================
CAMPAIGN BRIEF
============================================================

Product/service:
{brief.get("product", "Not provided")}

Key selling points:
{brief.get("selling_points", "Not provided")}

Offer:
{brief.get("offer", "none")}

Industry:
{brief.get("industry", "unspecified")}

Target countries:
{brief.get("countries", [])}

Target languages:
{brief.get("languages", [])}

Audience:
{brief.get("audience_description", "Not provided")}

============================================================
SOURCE LANGUAGE
============================================================

{source_locale}


============================================================
TARGET LOCALE
============================================================

{target_locale}


============================================================
BRAND VOICE
============================================================

{brand_voice}


============================================================
STRATEGY AGENT RESPONSE
============================================================

{strategy}


============================================================
COPYWRITER AGENT RESPONSE
============================================================

{copy_variants}


============================================================
TASK
============================================================

Translate and localize ALL copywriter variants into:

{target_locale}

Preserve:

- Product meaning
- Selling points
- Offer
- Persuasive intent
- CTA intent
- Brand voice
- Advertising purpose

Do not add unsupported claims.

The translated copy will require human review before
publication.

Return ONLY the structured JSON response.
"""


    # ========================================================
    # GENERATE TRANSLATION
    # ========================================================

    try:

        result = generate_structured(
            SYSTEM_PROMPT,
            user_prompt,
            TranslationOutput,
        )


        # ====================================================
        # CONVERT PYDANTIC RESULT
        # ====================================================

        payload = result.model_dump()


        # ====================================================
        # FORCE HUMAN REVIEW
        # ====================================================

        # Never trust the LLM to change this value.
        payload["requires_human_review"] = True


        # ====================================================
        # SAVE TRANSLATION RESPONSE
        # ====================================================

        state["translated_copy"] = payload


        logger.info(
            "Translation Agent completed successfully "
            "for locale=%s",
            target_locale,
        )


    except Exception as e:

        logger.error(
            "Translation Agent failed: %s",
            e,
        )


        # ====================================================
        # SAVE ERROR
        # ====================================================

        state.setdefault(
            "errors",
            [],
        ).append(
            f"translation_agent: {e}"
        )


        # ====================================================
        # STOP PIPELINE
        # ====================================================

        state["halted"] = True

        state["halt_reason"] = (
            "Translation agent failed to produce valid output"
        )


    # ========================================================
    # UPDATE CURRENT NODE
    # ========================================================

    state["current_node"] = (
        "translation"
    )


    # ========================================================
    # RETURN COMPLETE STATE
    # ========================================================

    return state