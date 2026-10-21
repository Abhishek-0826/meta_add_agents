"""
Compliance Agent.

The Compliance Agent is the final pre-screening gate before
the campaign reaches the Assembly Agent.

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

The Compliance Agent reviews the accumulated campaign state.

It checks:

- Original campaign brief
- Research output
- Strategy output
- Copywriter output
- Translated copy
- Creative information
- Generated/uploaded image information
- Agency blocked keywords
- Restricted categories
- Potential Meta advertising policy issues

If a serious violation is found:

    state["halted"] = True

The Compliance Agent does NOT publish or modify the campaign.
It only performs the pre-screening check.
"""

import logging

from pydantic import BaseModel, Field

from app.agents.state import PipelineState
from app.services.llm_client import generate_structured


logger = logging.getLogger(
    "adpilot.agents.compliance"
)


# ============================================================
# Compliance Output
# ============================================================

class ComplianceOutput(BaseModel):
    """
    Structured response returned by the Compliance Agent.
    """

    passed: bool = Field(
        description=(
            "True only when no compliance violation "
            "has been identified."
        )
    )

    violations: list[str] = Field(
        description=(
            "List of detected advertising policy or "
            "agency rule violations."
        )
    )

    restricted_category_flagged: bool = Field(
        description=(
            "True when the campaign belongs to or "
            "appears to involve a restricted category."
        )
    )

    notes: str = Field(
        description=(
            "Detailed explanation of the compliance "
            "review and any concerns."
        )
    )


# ============================================================
# System Prompt
# ============================================================

SYSTEM_PROMPT = """
You are the Compliance Agent in AdPilot.

You are the final pre-screening gate before an advertising
campaign is assembled for submission to Meta.

Review the COMPLETE campaign information provided to you.

You must inspect:

1. Campaign brief
2. Research Agent output
3. Strategy Agent output
4. Copywriter Agent output
5. Translation Agent output
6. Creative Agent output
7. Image Agent output
8. Agency-specific blocked keywords

============================================================
POLICY AREAS TO CHECK
============================================================

Flag potential violations involving:

- Personal attributes
- Personal health conditions
- Personal financial conditions
- Personal relationship status
- Personal characteristics
- Before/after claims
- Unsubstantiated health claims
- Unsubstantiated income claims
- Unrealistic financial claims
- Misleading claims
- Fake discounts
- Unsupported product claims
- Unsupported guarantees
- Restricted financial services
- Restricted health-related products/services
- Dating
- Politics or social issues
- Alcohol
- Adult products
- Other potentially restricted categories
- Agency-blocked keywords

Examples of problematic personal-attribute language include:

"Are you diabetic?"

"Your diabetes can be cured."

"Are you struggling with debt?"

"Your divorce is ruining your life."

Do not treat ordinary audience descriptions as automatically
violating policy. Distinguish between describing an audience
and directly asserting a sensitive personal attribute about
the person viewing the advertisement.

============================================================
IMAGE REVIEW
============================================================

Also review the Image Agent output.

Check for:

- Misleading visual claims
- Fake product representation
- Unsupported product features
- Fake logos
- Watermarks
- Potentially inappropriate imagery
- Restricted or sensitive imagery
- Visuals that contradict the campaign copy

The image output may contain metadata and a generated prompt.
Use that information as part of the review.

Do not claim that an image violates a visual policy when the
provided information is insufficient to establish that.

============================================================
AGENCY BLOCKED KEYWORDS
============================================================

If a blocked keyword appears in the campaign content,
flag it.

Check the relevant campaign text, including:

- Primary text
- Headlines
- Descriptions
- CTAs
- Translated copy
- Offer
- Creative instructions
- Image prompt

============================================================
DECISION RULE
============================================================

Set:

passed = true

only when no compliance violation has been identified.

Set:

passed = false

when one or more violations are identified.

This is a pre-screening gate.

When uncertain, clearly explain the uncertainty in notes
rather than inventing facts.

Do not invent Meta policy rules that are not supported by
the campaign information.

Return ONLY the structured response required by the schema.
"""


# ============================================================
# Compliance Agent
# ============================================================

def run_compliance_agent(
    state: PipelineState,
) -> PipelineState:
    """
    Run the Compliance Agent against the complete campaign.

    Reads:

    - brief
    - research
    - strategy
    - copy_variants
    - translated_copy
    - creative
    - image
    - guard_rails

    Writes:

    - state["compliance"]

    May halt the pipeline when compliance fails.
    """

    # --------------------------------------------------------
    # Stop if an earlier agent already failed
    # --------------------------------------------------------

    if state.get("halted"):
        logger.warning(
            "Compliance Agent skipped because pipeline is halted"
        )
        return state

    logger.info(
        "Starting Compliance Agent"
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

    translated_copy = state.get(
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

    guard_rails = state.get(
        "guard_rails",
        {},
    )

    blocked_keywords = guard_rails.get(
        "blocked_keywords",
        [],
    )

    brand_voice = state.get(
        "brand_voice",
        "professional",
    )

    # ========================================================
    # BUILD COMPLETE CAMPAIGN FOR REVIEW
    # ========================================================

    user_prompt = f"""
Review the following complete advertising campaign.

============================================================
CAMPAIGN BRIEF
============================================================

{brief}


============================================================
BRAND VOICE
============================================================

{brand_voice}


============================================================
RESEARCH AGENT RESPONSE
============================================================

{research}


============================================================
STRATEGY AGENT RESPONSE
============================================================

{strategy}


============================================================
COPYWRITER AGENT RESPONSE
============================================================

{copy_variants}


============================================================
TRANSLATION AGENT RESPONSE
============================================================

{translated_copy}


============================================================
CREATIVE AGENT RESPONSE
============================================================

{creative}


============================================================
IMAGE AGENT RESPONSE
============================================================

{image}


============================================================
AGENCY BLOCKED KEYWORDS
============================================================

{blocked_keywords}


============================================================
COMPLIANCE TASK
============================================================

Review ALL of the above information.

Check:

1. Ad copy
2. Translated copy
3. Offer and claims
4. Audience language
5. Restricted categories
6. Creative instructions
7. Image-generation information
8. Uploaded/generated asset information
9. Agency blocked keywords

If a violation is found:

- Set passed=false.
- Add the violation to violations.
- Explain the reason in notes.

If no violation is found:

- Set passed=true.
- Return an empty violations list.
- Explain that the campaign passed the pre-screen.

Do not invent facts that are not present in the campaign.
Return ONLY the structured JSON response.
"""

    # ========================================================
    # RUN LLM COMPLIANCE CHECK
    # ========================================================

    try:

        result = generate_structured(
            SYSTEM_PROMPT,
            user_prompt,
            ComplianceOutput,
        )

        payload = result.model_dump()

        # ----------------------------------------------------
        # Store Compliance Agent response
        # ----------------------------------------------------

        state["compliance"] = payload

        # ----------------------------------------------------
        # Compliance failed
        # ----------------------------------------------------

        if not payload["passed"]:

            violations = payload.get(
                "violations",
                [],
            )

            logger.warning(
                "Compliance check failed: %s",
                violations,
            )

            state["halted"] = True

            state["halt_reason"] = (
                "Compliance check failed: "
                f"{violations}"
            )

        # ----------------------------------------------------
        # Compliance passed
        # ----------------------------------------------------

        else:

            logger.info(
                "Compliance check passed successfully"
            )

    # ========================================================
    # ERROR HANDLING
    # ========================================================

    except Exception as e:

        logger.error(
            "Compliance Agent failed: %s",
            e,
        )

        state.setdefault(
            "errors",
            [],
        ).append(
            f"compliance_agent: {e}"
        )

        state["halted"] = True

        state["halt_reason"] = (
            "Compliance Agent failed to produce "
            "valid output"
        )

    # ========================================================
    # UPDATE CURRENT NODE
    # ========================================================

    state["current_node"] = "compliance"

    return state