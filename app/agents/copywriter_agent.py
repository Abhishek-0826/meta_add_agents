"""
Copywriter Agent.

The Copywriter Agent receives:

    - Original campaign brief
    - Research Agent output
    - Strategy Agent output
    - Client brand voice

It generates exactly 3 variants of:

    - Primary text
    - Headline
    - Description
    - CTA

The generated result is stored in:

    state["copy_variants"]

Pipeline position:

    Research
        ↓
    Strategy
        ↓
    Copywriter
        ↓
    Translation
"""


import logging

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)

from app.agents.state import PipelineState
from app.services.llm_client import generate_structured


logger = logging.getLogger(
    "adpilot.agents.copywriter"
)


# ============================================================
# META COPY LIMITS
# ============================================================

HEADLINE_MAX = 40

PRIMARY_TEXT_SOFT_MAX = 125


# ============================================================
# COPY VARIANT
# ============================================================

class CopyVariant(BaseModel):

    primary_text: str

    headline: str

    description: str

    cta: str

    @field_validator("headline")
    @classmethod
    def headline_length(
        cls,
        value: str,
    ) -> str:

        if len(value) >= HEADLINE_MAX:

            raise ValueError(
                f"headline is {len(value)} chars, "
                f"must be under {HEADLINE_MAX}"
            )

        return value


# ============================================================
# COPY OUTPUT
# ============================================================

class CopyOutput(BaseModel):

    variants: list[CopyVariant] = Field(
        min_length=3,
        max_length=3,
    )


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = f"""
You are the Copywriter Agent in AdPilot.

You create advertising copy for Meta campaigns.

The campaign information comes from:

1. Original campaign brief.
2. Research Agent.
3. Strategy Agent.
4. Client brand voice.

Use ALL of this information when writing the copy.

Generate exactly 3 distinct advertising copy variants.

Each variant must contain:

- primary_text
- headline
- description
- cta

COPY RULES:

1. Generate exactly 3 variants.

2. Every headline MUST be under {HEADLINE_MAX}
   characters.

3. Primary text should be concise and ideally fit within
   approximately {PRIMARY_TEXT_SOFT_MAX} visible characters
   before the user expands "See more".

4. Keep the copy relevant to the product/service.

5. Use the Research Agent's audience insights.

6. Follow the Strategy Agent's selected campaign objective.

7. Respect the client's brand voice.

8. Do not invent product features.

9. Do not invent discounts or offers.

10. Use the actual offer from the campaign brief when one
    exists.

11. CTA must be a standard Meta-style call-to-action label.

Examples:

- Shop Now
- Learn More
- Sign Up
- Send Message
- Get Offer
- Book Now
- Contact Us

12. Keep the three variants meaningfully different.

13. Do not use fake claims.

14. Do not use unnecessary hashtags.

15. Do not return markdown.

Return only the structured JSON response required
by the schema.
"""


# ============================================================
# COPYWRITER AGENT
# ============================================================

def run_copywriter_agent(
    state: PipelineState,
) -> PipelineState:

    # ========================================================
    # STOP IF PREVIOUS AGENT FAILED
    # ========================================================

    if state.get("halted"):

        logger.warning(
            "Copywriter Agent skipped because "
            "pipeline is halted"
        )

        return state


    logger.info(
        "Starting Copywriter Agent"
    )


    # ========================================================
    # READ CAMPAIGN BRIEF
    # ========================================================

    brief = state.get(
        "brief",
        {},
    )


    # ========================================================
    # READ RESEARCH AGENT OUTPUT
    # ========================================================

    research = state.get(
        "research",
        {},
    )


    # ========================================================
    # READ STRATEGY AGENT OUTPUT
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
        "friendly, clear, no jargon",
    )


    # ========================================================
    # BUILD USER PROMPT
    # ========================================================

    user_prompt = f"""
Create exactly 3 Meta advertising copy variants using
the campaign information below.

============================================================
ORIGINAL CAMPAIGN BRIEF
============================================================

Product/service:
{brief.get("product", "Not provided")}

Key selling points:
{brief.get("selling_points", "Not provided")}

Offer:
{brief.get("offer", "none")}

Industry:
{brief.get("industry", "unspecified")}

Audience:
{brief.get("audience_description", "Not provided")}

Target countries:
{brief.get("countries", [])}

Target languages:
{brief.get("languages", [])}

Age range:
{brief.get("age_range", "unspecified")}

Gender:
{brief.get("gender", "all")}

Exclusions:
{brief.get("exclusions", "none")}

Landing destination:
{brief.get("landing_destination", "Not provided")}


============================================================
RESEARCH AGENT RESPONSE
============================================================

{research}


============================================================
STRATEGY AGENT RESPONSE
============================================================

{strategy}


============================================================
BRAND VOICE
============================================================

{brand_voice}


============================================================
TASK
============================================================

Create exactly 3 distinct Meta ad copy variants.

The copy must:

- Match the research findings.
- Follow the campaign strategy.
- Match the brand voice.
- Use the actual product information.
- Use the actual offer if provided.
- Respect the headline character limit.
- Keep primary text concise.
- Use a suitable CTA.

Return ONLY the structured JSON response.
"""


    # ========================================================
    # GENERATE COPY
    # ========================================================

    try:

        result = generate_structured(
            SYSTEM_PROMPT,
            user_prompt,
            CopyOutput,
        )


        # ====================================================
        # SAVE COPYWRITER RESPONSE
        # ====================================================

        state["copy_variants"] = (
            result.model_dump()
        )


        logger.info(
            "Copywriter Agent completed successfully"
        )


    except Exception as e:

        logger.error(
            "Copywriter Agent failed: %s",
            e,
        )


        # ====================================================
        # SAVE ERROR
        # ====================================================

        state.setdefault(
            "errors",
            [],
        ).append(
            f"copywriter_agent: {e}"
        )


        # ====================================================
        # STOP PIPELINE
        # ====================================================

        state["halted"] = True

        state["halt_reason"] = (
            "Copywriter agent failed to produce valid output"
        )


    # ========================================================
    # UPDATE CURRENT NODE
    # ========================================================

    state["current_node"] = (
        "copywriter"
    )


    # ========================================================
    # RETURN COMPLETE STATE
    # ========================================================

    return state