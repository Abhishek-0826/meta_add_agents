"""
Strategy Agent.

The Strategy Agent receives:

    - Original campaign brief
    - Research Agent output
    - Brand context
    - Guard rails

It converts the research and campaign requirements into a
Meta advertising strategy.

The result is stored in:

    state["strategy"]

The next agent, Copywriter Agent, can then read:

    state["strategy"]

Pipeline position:

    Research Agent
          ↓
    Strategy Agent
          ↓
    Copywriter Agent
"""


import logging
from typing import Literal

from pydantic import BaseModel, Field

from app.agents.state import PipelineState
from app.services.llm_client import generate_structured


logger = logging.getLogger(
    "adpilot.agents.strategy"
)


# ============================================================
# META CAMPAIGN OBJECTIVES
# ============================================================

MetaObjective = Literal[
    "OUTCOME_AWARENESS",
    "OUTCOME_TRAFFIC",
    "OUTCOME_ENGAGEMENT",
    "OUTCOME_LEADS",
    "OUTCOME_SALES",
    "OUTCOME_APP_PROMOTION",
]


# ============================================================
# STRATEGY OUTPUT
# ============================================================

class StrategyOutput(BaseModel):

    objective: MetaObjective

    placements: list[str] = Field(
        description=(
            "Recommended Meta placements, for example "
            "['facebook_feed', 'instagram_feed', "
            "'instagram_stories']"
        )
    )

    proposed_daily_budget_inr: int = Field(
        description=(
            "Advisory daily budget in INR. "
            "Budget Guard has final authority."
        )
    )

    proposed_lifetime_budget_inr: int | None = Field(
        default=None,
        description=(
            "Optional advisory lifetime budget in INR. "
            "Budget Guard has final authority."
        )
    )

    schedule_notes: str = Field(
        description=(
            "Recommended campaign schedule and "
            "budget timing considerations."
        )
    )


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are the Strategy Agent in AdPilot, an AI-powered Meta
advertising campaign pipeline.

Your job is to convert the campaign brief and the Research
Agent's findings into a practical Meta advertising strategy.

You must:

1. Select exactly one Meta campaign objective from the
   allowed objective enum.

2. Recommend suitable Meta placements.

3. Propose a reasonable daily budget.

4. Optionally propose a lifetime budget.

5. Provide scheduling recommendations.

IMPORTANT:

- The Research Agent output is an input to your decision.
- Use the research findings when selecting the strategy.
- Respect the user's requested campaign objective when it
  is compatible with the campaign.
- Respect the user's requested platform and placement.
- The proposed budget is ADVISORY ONLY.
- Do not attempt to bypass budget restrictions.
- Budget Guard is a separate non-LLM hard safety check.
- Do not invent information that is not present in the brief
  or research.
"""


# ============================================================
# STRATEGY AGENT
# ============================================================

def run_strategy_agent(
    state: PipelineState,
) -> PipelineState:

    # ========================================================
    # STOP IF PREVIOUS AGENT FAILED
    # ========================================================

    if state.get("halted"):

        logger.warning(
            "Strategy Agent skipped because pipeline is halted"
        )

        return state


    logger.info(
        "Starting Strategy Agent"
    )


    # ========================================================
    # READ CAMPAIGN BRIEF
    # ========================================================

    brief = state.get(
        "brief",
        {},
    )


    # ========================================================
    # READ RESEARCH AGENT RESPONSE
    # ========================================================

    research = state.get(
        "research",
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

    guard_rails = state.get(
        "guard_rails",
        {},
    )


    # ========================================================
    # BUILD USER PROMPT
    # ========================================================

    user_prompt = f"""
Create a Meta advertising strategy using BOTH the original
campaign brief and the Research Agent's findings.

============================================================
CAMPAIGN BRIEF
============================================================

Product/service:
{brief.get("product", "Not provided")}

Key selling points:
{brief.get("selling_points", "Not provided")}

Industry:
{brief.get("industry", "unspecified")}

User requested objective:
{brief.get("objective", "Not provided")}

Format:
{brief.get("format", "Not provided")}

Platform:
{brief.get("platform", "Not provided")}

Placement preference:
{brief.get("placement", "auto")}

Target countries:
{brief.get("countries", [])}

Target languages:
{brief.get("languages", [])}

Audience:
{brief.get("audience_description", "Not provided")}

Age range:
{brief.get("age_range", "unspecified")}

Gender:
{brief.get("gender", "all")}

Exclusions:
{brief.get("exclusions", "none")}

Budget type:
{brief.get("budget_type", "Not provided")}

Budget amount:
{brief.get("budget_amount", "Not provided")}


============================================================
RESEARCH AGENT OUTPUT
============================================================

{research}


============================================================
BRAND CONTEXT
============================================================

Brand voice:
{brand_voice}

Default language:
{default_language}


============================================================
BUDGET GUARD RAILS
============================================================

{guard_rails}


============================================================
TASK
============================================================

Use the Research Agent output to create the campaign
strategy.

Return ONLY the structured response required by the schema.
"""


    # ========================================================
    # GENERATE STRATEGY
    # ========================================================

    try:

        result = generate_structured(
            SYSTEM_PROMPT,
            user_prompt,
            StrategyOutput,
        )


        # ====================================================
        # SAVE STRATEGY RESPONSE
        # ====================================================

        state["strategy"] = (
            result.model_dump()
        )


        logger.info(
            "Strategy Agent completed successfully"
        )


    except Exception as e:

        logger.error(
            "Strategy Agent failed: %s",
            e,
        )


        # ====================================================
        # SAVE ERROR
        # ====================================================

        state.setdefault(
            "errors",
            [],
        ).append(
            f"strategy_agent: {e}"
        )


        # ====================================================
        # STOP PIPELINE
        # ====================================================

        state["halted"] = True

        state["halt_reason"] = (
            "Strategy agent failed to produce valid output"
        )


    # ========================================================
    # UPDATE CURRENT NODE
    # ========================================================

    state["current_node"] = "strategy"


    # ========================================================
    # RETURN COMPLETE STATE
    # ========================================================

    return state