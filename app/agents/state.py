"""
Shared Pipeline State for AdPilot.

Every agent receives this same state object.

Each agent:
    1. Reads the required information from previous agents.
    2. Performs its task.
    3. Stores its result in its own state field.
    4. Returns the updated state.

Pipeline:

    Brief
      ↓
    Research Agent
      ↓
    Strategy Agent
      ↓
    Copywriter Agent
      ↓
    Translation Agent
      ↓
    Creative Agent
      ↓
    Image Agent
      ↓
    Compliance Agent
      ↓
    Assembly Agent
      ↓
    Budget Guard
      ↓
    END
"""

from typing import Any, TypedDict


class PipelineState(TypedDict, total=False):

    # ============================================================
    # CAMPAIGN / JOB INFORMATION
    # ============================================================

    # Unique job ID
    job_id: str

    # Client ID
    client_id: str

    # Original campaign brief submitted by the user
    brief: dict[str, Any]


    # ============================================================
    # CLIENT / BRAND INFORMATION
    # ============================================================

    # Brand tone and writing style
    brand_voice: str

    # Default/source language
    default_language: str

    # Safety and budget restrictions
    guard_rails: dict[str, Any]


    # ============================================================
    # 1. RESEARCH AGENT OUTPUT
    # ============================================================

    """
    Research Agent receives:

        brief
        brand_voice
        default_language

    Research Agent produces:

        research

    Later agents can access:

        state["research"]
    """

    research: dict[str, Any]


    # ============================================================
    # 2. STRATEGY AGENT OUTPUT
    # ============================================================

    """
    Strategy Agent receives:

        brief
        research
        brand_voice
        guard_rails

    Strategy Agent produces:

        strategy

    Later agents can access:

        state["strategy"]
    """

    strategy: dict[str, Any]


    # ============================================================
    # 3. COPYWRITER AGENT OUTPUT
    # ============================================================

    """
    Copywriter Agent receives:

        brief
        research
        strategy
        brand_voice

    Copywriter Agent produces:

        copy_variants

    Later agents can access:

        state["copy_variants"]
    """

    copy_variants: dict[str, Any]


    # ============================================================
    # 4. TRANSLATION AGENT OUTPUT
    # ============================================================

    """
    Translation Agent is conditional.

    It receives:

        brief
        copy_variants
        strategy
        default_language

    It produces:

        translated_copy

    If translation is not required, the pipeline can skip this
    agent and continue directly to Creative Agent.
    """

    translated_copy: dict[str, Any]


    # ============================================================
    # 5. CREATIVE AGENT OUTPUT
    # ============================================================

    """
    Creative Agent receives previous campaign information:

        brief
        research
        strategy
        copy_variants
        translated_copy

    It produces:

        creative

    Later agents can access:

        state["creative"]
    """

    creative: dict[str, Any]


    # ============================================================
    # 6. IMAGE AGENT OUTPUT
    # ============================================================

    """
    Image Agent receives information from the previous agents.

    It can use:

        brief
        research
        strategy
        copy_variants
        translated_copy
        creative

    It produces:

        image

    Example:

        {
            "success": True,
            "model": "...",
            "filename": "...",
            "image_url": "...",
            "path": "...",
            "prompt": "..."
        }
    """

    image: dict[str, Any]


    # ============================================================
    # 7. COMPLIANCE AGENT OUTPUT
    # ============================================================

    """
    Compliance Agent receives the generated campaign information.

    It can inspect:

        brief
        research
        strategy
        copy_variants
        translated_copy
        creative
        image

    It produces:

        compliance
    """

    compliance: dict[str, Any]


    # ============================================================
    # 8. ASSEMBLY AGENT OUTPUT
    # ============================================================

    """
    Assembly Agent receives the approved campaign information.

    It can use:

        brief
        research
        strategy
        copy_variants
        translated_copy
        creative
        image
        compliance

    It produces the final deterministic payload:

        assembled_payload
    """

    assembled_payload: dict[str, Any]


    # ============================================================
    # PIPELINE CONTROL
    # ============================================================

    # Name of the currently executing node
    current_node: str

    # True when the pipeline must stop
    halted: bool

    # Human-readable reason for stopping
    halt_reason: str

    # List of errors encountered during the pipeline
    errors: list[str]