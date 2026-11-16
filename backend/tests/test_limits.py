from datetime import date

from app.limits import DailyBudget, RateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_rate_limit_allows_the_configured_number_per_minute() -> None:
    limiter = RateLimiter(per_minute=3, clock=FakeClock())

    assert [limiter.allow("visitor-a") for _ in range(4)] == [True, True, True, False]


def test_rate_limit_is_per_visitor() -> None:
    limiter = RateLimiter(per_minute=1, clock=FakeClock())

    assert limiter.allow("visitor-a") is True
    assert limiter.allow("visitor-a") is False
    assert limiter.allow("visitor-b") is True


def test_rate_limit_recovers_after_a_minute() -> None:
    clock = FakeClock()
    limiter = RateLimiter(per_minute=1, clock=clock)

    assert limiter.allow("visitor-a") is True
    clock.now += 59
    assert limiter.allow("visitor-a") is False
    clock.now += 2
    assert limiter.allow("visitor-a") is True


def test_rate_limit_forgets_visitors_who_left() -> None:
    clock = FakeClock()
    limiter = RateLimiter(per_minute=5, clock=clock)

    for index in range(100):
        limiter.allow(f"visitor-{index}")
    clock.now += 61
    limiter.allow("someone-new")

    assert limiter.tracked_visitors() == 1


TODAY = date(2026, 11, 16)


def test_budget_stops_at_the_limit() -> None:
    budget = DailyBudget(limit_usd=1.0, today=lambda: TODAY)

    assert budget.reserve(0.1) is True
    budget.settle(0.1, actual_usd=0.6)
    assert budget.reserve(0.1) is True
    budget.settle(0.1, actual_usd=0.4)

    assert budget.reserve(0.0) is False
    assert budget.spent_usd == 1.0


def test_a_burst_cannot_overshoot_because_each_question_reserves_its_worst_case() -> None:
    budget = DailyBudget(limit_usd=1.0, today=lambda: TODAY)

    # Three questions arrive together, each could cost up to 0.4.
    assert [budget.reserve(0.4) for _ in range(3)] == [True, True, False]

    # The first two finish cheaply, which frees the room they were holding.
    budget.settle(0.4, actual_usd=0.05)
    budget.settle(0.4, actual_usd=0.05)
    assert budget.reserve(0.4) is True
    assert budget.spent_usd == 0.1


def test_spend_is_recorded_even_when_the_question_failed() -> None:
    budget = DailyBudget(limit_usd=1.0, today=lambda: TODAY)
    budget.reserve(0.4)

    budget.settle(0.4, actual_usd=0.3)

    assert budget.spent_usd == 0.3


def test_budget_resets_the_next_day() -> None:
    day = [TODAY]
    budget = DailyBudget(limit_usd=1.0, today=lambda: day[0])
    budget.reserve(0.1)
    budget.settle(0.1, actual_usd=5.0)
    assert budget.reserve(0.1) is False

    day[0] = date(2026, 11, 17)

    assert budget.reserve(0.1) is True
    assert budget.spent_usd == 0.0


def test_a_zero_budget_never_has_room() -> None:
    assert DailyBudget(limit_usd=0.0, today=lambda: TODAY).reserve(0.0) is False
