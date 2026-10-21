"""
Research Agent.

The Research Agent is the first LLM agent in the AdPilot pipeline.

Input:
    - Campaign brief
    - Brand voice
    - Default language
    - Guard rails

Output:
    - Structured audience research

The result is stored in:

    state["research"]

The next agent, Strategy Agent, can then read:

    state["research"]
"""

import logging

from pydantic import BaseModel, Field

from app.agents.state import PipelineState
from app.services.llm_client import generate_structured


logger = logging.getLogger(
    "adpilot.agents.research"
)


# ============================================================
# RESEARCH OUTPUT SCHEMA
# ============================================================

class ResearchOutput(BaseModel):

    age_range: str = Field(
        description="Target age range, for example '25-45'"
    )

    gender_skew: str = Field(
        description=(
            "Gender distribution preference. "
            "Allowed values: 'all', 'male_leaning', "
            "or 'female_leaning'"
        )
    )

    interest_names: list[str] = Field(
        description=(
            "Candidate Meta interest names in plain English. "
            "Do NOT provide Meta interest IDs."
        )
    )

    behavioural_segments: list[str] = Field(
        description=(
            "Relevant audience behavioural segments"
        )
    )

    competitor_positioning: str = Field(
        description=(
            "Competitor and market positioning observations"
        )
    )

    seasonal_notes: str = Field(
        description=(
            "Seasonal considerations relevant to the "
            "target location and industry"
        )
    )


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are the Research Agent in AdPilot, an AI-powered Meta
advertising campaign pipeline.

Your job is to analyze the campaign brief and produce
structured audience research.

You must provide:

1. Appropriate target age range.
2. Gender skew.
3. Candidate Meta interest names.
4. Relevant behavioural segments.
5. Competitor positioning observations.
6. Seasonal considerations.

IMPORTANT:

- Interest names must be plain English names.
- NEVER invent Meta interest IDs.
- NEVER provide fake Meta interest IDs.
- Real Meta interest IDs will be resolved separately
  using the Meta targeting search API.
- Base your research only on the information available
  in the campaign brief.
- Keep the recommendations relevant to the target
  countries and audience.
"""


# ============================================================
# RESEARCH AGENT
# ============================================================

def run_research_agent(
    state: PipelineState,
) -> PipelineState:

    logger.info(
        "Starting Research Agent"
    )

    # ========================================================
    # READ CAMPAIGN BRIEF
    # ========================================================

    brief = state.get(
        "brief",
        {},
    )

    # ========================================================
    # READ CLIENT CONTEXT
    # ========================================================

    brand_voice = state.get(
        "brand_voice",
        "professional",
    )

    default_language = state.get(
        "default_language",
        "en",
    )

    # ========================================================
    # BUILD USER PROMPT
    # ========================================================

    user_prompt = f"""
Analyze the following campaign.

Campaign information:

Product/service:
{brief.get("product", "Not provided")}

Key selling points:
{brief.get("selling_points", "Not provided")}

Industry:
{brief.get("industry", "unspecified")}

Target countries:
{brief.get("countries", [])}

Target languages:
{brief.get("languages", [])}

Stated audience:
{brief.get("audience_description", "none provided")}

Age range preference:
{brief.get("age_range", "unspecified")}

Gender preference:
{brief.get("gender", "all")}

Exclusions:
{brief.get("exclusions", "none")}

Brand voice:
{brand_voice}

Default language:
{default_language}

Produce structured audience research for the campaign.
"""


    # ========================================================
    # GENERATE RESEARCH
    # ========================================================

    try:

        result = generate_structured(
            SYSTEM_PROMPT,
            user_prompt,
            ResearchOutput,
        )

        # ====================================================
        # SAVE RESEARCH RESPONSE TO SHARED STATE
        # ====================================================

        state["research"] = (
            result.model_dump()
        )

        logger.info(
            "Research Agent completed successfully"
        )

    except Exception as e:

        logger.error(
            "Research Agent failed: %s",
            e,
        )

        # ----------------------------------------------------
        # Save error
        # ----------------------------------------------------

        state.setdefault(
            "errors",
            [],
        ).append(
            f"research_agent: {e}"
        )

        # ----------------------------------------------------
        # Stop pipeline
        # ----------------------------------------------------

        state["halted"] = True

        state["halt_reason"] = (
            "Research agent failed to produce valid output"
        )

    # ========================================================
    # CURRENT NODE
    # ========================================================

    state["current_node"] = "research"

    # ========================================================
    # RETURN COMPLETE STATE
    # ========================================================

    return state