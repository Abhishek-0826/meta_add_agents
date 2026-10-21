import pytest

from app.agents.budget_guard import check_budget, assert_status_is_paused, BudgetGuardViolation, MAX_DAILY_BUDGET_INR


def test_budget_within_ceiling_passes():
    check_budget(daily_budget=1000, lifetime_budget=10000)  # should not raise


def test_budget_exceeding_ceiling_raises():
    with pytest.raises(BudgetGuardViolation):
        check_budget(daily_budget=MAX_DAILY_BUDGET_INR + 1, lifetime_budget=None)


def test_zero_or_negative_budget_raises():
    with pytest.raises(BudgetGuardViolation):
        check_budget(daily_budget=0, lifetime_budget=None)
    with pytest.raises(BudgetGuardViolation):
        check_budget(daily_budget=-500, lifetime_budget=None)


def test_guard_rails_can_only_tighten_not_loosen():
    """A client-level guard rail set ABOVE the system ceiling must not let more spend through."""
    with pytest.raises(BudgetGuardViolation):
        check_budget(
            daily_budget=MAX_DAILY_BUDGET_INR + 1,
            lifetime_budget=None,
            guard_rails={"max_daily_budget": MAX_DAILY_BUDGET_INR * 10},  # attempted loosening
        )


def test_guard_rails_tighter_than_system_ceiling_is_enforced():
    with pytest.raises(BudgetGuardViolation):
        check_budget(daily_budget=2000, lifetime_budget=None, guard_rails={"max_daily_budget": 1000})


def test_only_paused_status_allowed_on_create():
    assert_status_is_paused("PAUSED")  # should not raise
    with pytest.raises(BudgetGuardViolation):
        assert_status_is_paused("ACTIVE")
