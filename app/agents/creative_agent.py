"""
Creative Agent.

The Creative Agent prepares the visual creative requirements for the
Image Agent or selects the client's uploaded asset.

Pipeline flow:

    Research
        ↓
    Strategy
        ↓
    Copywriter
        ↓
    Translation
        ↓
    Creative Agent
        ↓
    Image Agent
        ↓
    Compliance
        ↓
    Assembly

Responsibilities:

- Read outputs from previous agents.
- Determine the required creative format.
- Enforce Meta placement aspect ratios.
- Prefer uploaded assets when the client provides them.
- Prepare detailed creative instructions for the Image Agent.
- Pass all relevant campaign context forward through PipelineState.

The Creative Agent does NOT directly generate images.
The Image Agent handles AI image generation.
"""

import logging

from app.agents.state import PipelineState

logger = logging.getLogger("adpilot.agents.creative")


# Meta placement aspect ratios
ASPECT_RATIOS = {
    "feed": "1:1",
    "facebook_feed": "1:1",
    "instagram_feed": "1:1",

    "stories": "9:16",
    "instagram_stories": "9:16",
    "facebook_stories": "9:16",

    "reels": "9:16",
    "instagram_reels": "9:16",
    "facebook_reels": "9:16",

    "link": "1.91:1",
    "link_ad": "1.91:1",
}


def _required_aspect_ratio(placement: str) -> str:
    """
    Return the required aspect ratio for a Meta placement.
    """

    return ASPECT_RATIOS.get(
        placement.lower(),
        "1:1",
    )


def run_creative_agent(state: PipelineState) -> PipelineState:
    """
    Run the Creative Agent.

    Reads:

    - brief
    - research
    - strategy
    - copy_variants
    - translated_copy
    - brand_voice

    Writes:

    - state["creative"]

    The Image Agent will later read this creative output.
    """

    if state.get("halted"):
        logger.warning(
            "Creative Agent skipped because pipeline is halted"
        )
        return state

    logger.info("Starting Creative Agent")

    # ---------------------------------------------------------
    # READ ORIGINAL CAMPAIGN BRIEF
    # ---------------------------------------------------------

    brief = state.get("brief", {})

    # ---------------------------------------------------------
    # READ ALL PREVIOUS AGENT OUTPUTS
    # ---------------------------------------------------------

    research = state.get("research", {})

    strategy = state.get("strategy", {})

    copy_variants = state.get(
        "copy_variants",
        {},
    )

    translated_copy = state.get(
        "translated_copy"
    )

    brand_voice = state.get(
        "brand_voice",
        "friendly, clear, professional",
    )

    # ---------------------------------------------------------
    # CREATIVE PREFERENCE
    # ---------------------------------------------------------

    creative_choice = brief.get(
        "creative_choice",
        "upload",
    )

    uploaded_assets = (
        brief.get("uploaded_asset_urls")
        or []
    )

    # ---------------------------------------------------------
    # PLACEMENTS
    # ---------------------------------------------------------

    placements = strategy.get(
        "placements",
        ["feed"],
    )

    if not placements:
        placements = ["feed"]

    # Calculate required aspect ratios
    required_ratios = {
        placement: _required_aspect_ratio(placement)
        for placement in placements
    }

    # ---------------------------------------------------------
    # COMMON CREATIVE CONTEXT
    # ---------------------------------------------------------

    creative_context = {
        "product": brief.get(
            "product",
            "",
        ),

        "selling_points": brief.get(
            "selling_points",
            "",
        ),

        "offer": brief.get(
            "offer",
            "",
        ),

        "objective": strategy.get(
            "objective",
            brief.get("objective", "sales"),
        ),

        "audience": brief.get(
            "audience_description",
            "General audience",
        ),

        "countries": brief.get(
            "countries",
            [],
        ),

        "languages": brief.get(
            "languages",
            [],
        ),

        "brand_voice": brand_voice,

        "placements": placements,

        "required_aspect_ratios": required_ratios,

        # Previous agent responses
        "research": research,

        "strategy": strategy,

        "copy_variants": copy_variants,

        "translated_copy": translated_copy,
    }

    # ---------------------------------------------------------
    # OPTION 1: CLIENT UPLOADED CREATIVE
    # ---------------------------------------------------------

    if creative_choice == "upload":

        if not uploaded_assets:

            logger.error(
                "Creative choice is upload but no assets were provided"
            )

            state.setdefault(
                "errors",
                [],
            ).append(
                "creative_agent: creative_choice=upload "
                "but no uploaded assets were provided"
            )

            state["halted"] = True

            state["halt_reason"] = (
                "No uploaded creative assets provided"
            )

            state["current_node"] = "creative"

            return state

        logger.info(
            "Using %s uploaded creative asset(s)",
            len(uploaded_assets),
        )

        state["creative"] = {
            "source": "upload",

            "asset_urls": uploaded_assets,

            "required_aspect_ratios": required_ratios,

            "placements": placements,

            "creative_context": creative_context,

            "image_generation_required": False,

            "instructions": (
                "Use the client-provided creative assets. "
                "Do not generate a replacement image unless "
                "explicitly requested."
            ),
        }

    # ---------------------------------------------------------
    # OPTION 2: AI GENERATED CREATIVE
    # ---------------------------------------------------------

    elif creative_choice == "generate":

        logger.info(
            "AI creative generation requested"
        )

        # The Image Agent will use this information
        # to generate the actual image.
        state["creative"] = {
            "source": "generate",

            "asset_urls": [],

            "required_aspect_ratios": required_ratios,

            "placements": placements,

            "creative_context": creative_context,

            "image_generation_required": True,

            "instructions": (
                "Generate a professional Meta advertising "
                "creative based on the campaign brief, "
                "research, strategy, copywriting and "
                "translation outputs."
            ),

            "image_prompt_context": {
                "product": brief.get(
                    "product",
                    "",
                ),

                "selling_points": brief.get(
                    "selling_points",
                    "",
                ),

                "offer": brief.get(
                    "offer",
                    "",
                ),

                "audience": brief.get(
                    "audience_description",
                    "General audience",
                ),

                "objective": strategy.get(
                    "objective",
                    brief.get(
                        "objective",
                        "sales",
                    ),
                ),

                "brand_voice": brand_voice,

                "research": research,

                "strategy": strategy,

                "copy_variants": copy_variants,

                "translated_copy": translated_copy,

                "placements": placements,

                "required_aspect_ratios": required_ratios,
            },
        }

    # ---------------------------------------------------------
    # INVALID CREATIVE OPTION
    # ---------------------------------------------------------

    else:

        logger.error(
            "Unknown creative_choice: %s",
            creative_choice,
        )

        state.setdefault(
            "errors",
            [],
        ).append(
            f"creative_agent: unsupported creative_choice "
            f"'{creative_choice}'. Expected 'upload' or 'generate'."
        )

        state["halted"] = True

        state["halt_reason"] = (
            f"Unsupported creative choice: {creative_choice}"
        )

        state["current_node"] = "creative"

        return state

    # ---------------------------------------------------------
    # FINISH
    # ---------------------------------------------------------

    state["current_node"] = "creative"

    logger.info(
        "Creative Agent completed successfully: source=%s",
        state["creative"].get("source"),
    )

    return state