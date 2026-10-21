"""
Budget Guard.

THE SINGLE MOST IMPORTANT SAFETY MODULE IN THE CODEBASE.

This module is plain deterministic Python.

NO LLM is used here.

The Budget Guard:

- Cannot be prompt-injected.
- Cannot be overridden by campaign input.
- Cannot silently reduce/clamp an invalid budget.
- Cannot allow an ACTIVE object to be created.
- Cannot allow a budget above the configured ceiling.
- Requires human approval before activation.

Pipeline position:

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
    BUDGET GUARD
        ↓
    Human Review
        ↓
    Explicit Activation

IMPORTANT:

If the Budget Guard raises BudgetGuardViolation,
the caller MUST halt the pipeline.

The guard does not "fix" bad values.
A bad value is treated as an upstream error.
"""

from typing import Any

from app.config import get_settings


# ============================================================
# Configuration
# ============================================================

settings = get_settings()


# Hard maximum daily budget per ad set.
MAX_DAILY_BUDGET_INR = (
    settings.MAX_DAILY_BUDGET_INR
)


# Hard maximum campaign lifetime budget.
MAX_CAMPAIGN_LIFETIME_INR = (
    settings.MAX_CAMPAIGN_LIFETIME_INR
)


# Meta objects MUST be created paused.
#
# This is intentionally hard-coded.
ALLOWED_STATUS_ON_CREATE = "PAUSED"


# Human approval is mandatory.
#
# This must never be controlled by an API request.
REQUIRE_HUMAN_APPROVAL = True


# ============================================================
# Exception
# ============================================================

class BudgetGuardViolation(Exception):
    """
    Raised whenever a campaign violates a Budget Guard rule.
    """

    def __init__(
        self,
        reason: str,
    ):
        self.reason = reason
        super().__init__(reason)


# ============================================================
# Helper: Guard Rail Limits
# ============================================================

def _get_effective_ceilings(
    guard_rails: dict[str, Any] | None,
) -> tuple[int, int]:
    """
    Calculate the effective budget ceilings.

    Client/agency guard rails may TIGHTEN the global limits.

    They can NEVER increase the global limits.

    Example:

        Global daily limit = 5000
        Client daily limit = 3000

        Effective limit = 3000

    But:

        Global daily limit = 5000
        Client daily limit = 10000

        Effective limit = 5000
    """

    ceiling_daily = (
        MAX_DAILY_BUDGET_INR
    )

    ceiling_lifetime = (
        MAX_CAMPAIGN_LIFETIME_INR
    )

    if guard_rails:

        requested_daily = guard_rails.get(
            "max_daily_budget"
        )

        requested_lifetime = guard_rails.get(
            "max_lifetime_budget"
        )

        if requested_daily is not None:

            ceiling_daily = min(
                ceiling_daily,
                int(requested_daily),
            )

        if requested_lifetime is not None:

            ceiling_lifetime = min(
                ceiling_lifetime,
                int(requested_lifetime),
            )

    return (
        ceiling_daily,
        ceiling_lifetime,
    )


# ============================================================
# Budget Validation
# ============================================================

def check_budget(
    daily_budget: int | float | None,
    lifetime_budget: int | float | None,
    guard_rails: dict[str, Any] | None = None,
) -> None:
    """
    Validate campaign budget.

    Raises BudgetGuardViolation when:

    - Daily budget is missing.
    - Daily budget is invalid.
    - Daily budget is zero/negative.
    - Daily budget exceeds the hard ceiling.
    - Lifetime budget is invalid.
    - Lifetime budget is negative.
    - Lifetime budget exceeds the hard ceiling.

    IMPORTANT:

    This function NEVER clamps a budget.

    Invalid:

        7000 → 5000

    is NOT allowed.

    Instead:

        7000 → HALT
    """

    ceiling_daily, ceiling_lifetime = (
        _get_effective_ceilings(
            guard_rails
        )
    )

    # ========================================================
    # Daily Budget
    # ========================================================

    if daily_budget is None:

        raise BudgetGuardViolation(
            "Daily budget is missing"
        )

    # Reject booleans because bool is technically an int in Python.
    if isinstance(
        daily_budget,
        bool,
    ):

        raise BudgetGuardViolation(
            "Daily budget must be a numeric INR amount"
        )

    try:

        daily_budget = float(
            daily_budget
        )

    except (
        TypeError,
        ValueError,
    ):

        raise BudgetGuardViolation(
            f"Daily budget must be numeric, "
            f"got {daily_budget!r}"
        )

    if daily_budget <= 0:

        raise BudgetGuardViolation(
            "Daily budget must be positive, "
            f"got {daily_budget}"
        )

    if daily_budget > ceiling_daily:

        raise BudgetGuardViolation(
            f"Daily budget {daily_budget} INR "
            f"exceeds ceiling {ceiling_daily} INR"
        )

    # ========================================================
    # Lifetime Budget
    # ========================================================

    if lifetime_budget is not None:

        if isinstance(
            lifetime_budget,
            bool,
        ):

            raise BudgetGuardViolation(
                "Lifetime budget must be a numeric INR amount"
            )

        try:

            lifetime_budget = float(
                lifetime_budget
            )

        except (
            TypeError,
            ValueError,
        ):

            raise BudgetGuardViolation(
                f"Lifetime budget must be numeric, "
                f"got {lifetime_budget!r}"
            )

        if lifetime_budget <= 0:

            raise BudgetGuardViolation(
                "Lifetime budget must be positive, "
                f"got {lifetime_budget}"
            )

        if lifetime_budget > ceiling_lifetime:

            raise BudgetGuardViolation(
                f"Lifetime budget {lifetime_budget} INR "
                f"exceeds ceiling {ceiling_lifetime} INR"
            )


# ============================================================
# Status Validation
# ============================================================

def assert_status_is_paused(
    status: str,
) -> None:
    """
    Ensure a Meta object is created as PAUSED.

    ACTIVE is never allowed at creation time.
    """

    if status != ALLOWED_STATUS_ON_CREATE:

        raise BudgetGuardViolation(
            f"Attempted to create a Meta object "
            f"with status={status!r}. "
            f"Only {ALLOWED_STATUS_ON_CREATE!r} "
            f"is permitted at creation time."
        )


# ============================================================
# Validate Final Assembly Payload
# ============================================================

def validate_assembled_payload(
    payload: dict[str, Any],
) -> None:
    """
    Validate the final payload produced by the Assembly Agent.

    This is an additional safety layer.

    It ensures that even if an upstream agent produces an
    unexpected payload, the final Meta payload cannot bypass
    the Budget Guard.
    """

    if not payload:

        raise BudgetGuardViolation(
            "Assembled campaign payload is empty"
        )

    # ========================================================
    # Required Meta Objects
    # ========================================================

    campaign = payload.get(
        "campaign"
    )

    adset = payload.get(
        "adset"
    )

    ad = payload.get(
        "ad"
    )

    if not isinstance(
        campaign,
        dict,
    ):

        raise BudgetGuardViolation(
            "Assembled payload is missing campaign object"
        )

    if not isinstance(
        adset,
        dict,
    ):

        raise BudgetGuardViolation(
            "Assembled payload is missing adset object"
        )

    if not isinstance(
        ad,
        dict,
    ):

        raise BudgetGuardViolation(
            "Assembled payload is missing ad object"
        )

    # ========================================================
    # Campaign Status
    # ========================================================

    assert_status_is_paused(
        campaign.get(
            "status"
        )
    )

    # ========================================================
    # Ad Set Status
    # ========================================================

    assert_status_is_paused(
        adset.get(
            "status"
        )
    )

    # ========================================================
    # Ad Status
    # ========================================================

    assert_status_is_paused(
        ad.get(
            "status"
        )
    )

    # ========================================================
    # Human Approval
    # ========================================================

    if REQUIRE_HUMAN_APPROVAL:

        if payload.get(
            "human_review_required"
        ) is not True:

            raise BudgetGuardViolation(
                "Human approval is mandatory before "
                "campaign activation"
            )

    # ========================================================
    # Final Payload Status
    # ========================================================

    if payload.get(
        "status"
    ) != ALLOWED_STATUS_ON_CREATE:

        raise BudgetGuardViolation(
            "Final assembled payload must have "
            f"status={ALLOWED_STATUS_ON_CREATE!r}"
        )


# ============================================================
# Full Budget Guard
# ============================================================

def run_budget_guard(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Run the complete Budget Guard against PipelineState.

    This function is intended to be used as the final
    deterministic node in the LangGraph pipeline.

    It validates:

        1. Strategy budget
        2. Final assembled payload
        3. Campaign status
        4. AdSet status
        5. Ad status
        6. Human-review requirement

    If validation fails:

        state["halted"] = True

    No values are silently changed.
    """

    # --------------------------------------------------------
    # If pipeline already halted, do nothing.
    # --------------------------------------------------------

    if state.get(
        "halted"
    ):

        return state

    # ========================================================
    # Read State
    # ========================================================

    strategy = state.get(
        "strategy",
        {},
    )

    guard_rails = state.get(
        "guard_rails",
        {},
    )

    assembled_payload = state.get(
        "assembled_payload",
        {},
    )

    # ========================================================
    # Read Proposed Budget
    # ========================================================

    daily_budget = strategy.get(
        "proposed_daily_budget_inr"
    )

    lifetime_budget = strategy.get(
        "proposed_lifetime_budget_inr"
    )

    # ========================================================
    # Validate Budget
    # ========================================================

    try:

        check_budget(
            daily_budget=daily_budget,
            lifetime_budget=lifetime_budget,
            guard_rails=guard_rails,
        )

        # ====================================================
        # Validate Final Assembly Payload
        # ====================================================

        validate_assembled_payload(
            assembled_payload
        )

    except BudgetGuardViolation as e:

        state["halted"] = True

        state["halt_reason"] = (
            f"Budget Guard: {e.reason}"
        )

        state.setdefault(
            "errors",
            [],
        ).append(
            f"budget_guard: {e.reason}"
        )

        state["current_node"] = (
            "budget_guard"
        )

        return state

    # ========================================================
    # Guard Passed
    # ========================================================

    state["budget_guard"] = {
        "passed": True,
        "daily_budget_inr": daily_budget,
        "lifetime_budget_inr": lifetime_budget,
        "max_daily_budget_inr": MAX_DAILY_BUDGET_INR,
        "max_campaign_lifetime_inr": (
            MAX_CAMPAIGN_LIFETIME_INR
        ),
        "human_approval_required": (
            REQUIRE_HUMAN_APPROVAL
        ),
        "status_on_create": (
            ALLOWED_STATUS_ON_CREATE
        ),
    }

    state["current_node"] = (
        "budget_guard"
    )

    return state