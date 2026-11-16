"""Spend protection for the public Ask endpoint: a per-visitor rate limit and a daily budget.

Both are in memory, which is enough for one small instance: they reset on restart and
are not shared between processes. Redis is the next step if that stops being true.
"""

import threading
import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, date, datetime

WINDOW_SECONDS = 60.0


class RateLimiter:
    """At most `per_minute` questions per visitor in any sixty seconds."""

    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic) -> None:
        self._per_minute = per_minute
        self._clock = clock
        self._asked: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, visitor: str) -> bool:
        now = self._clock()
        with self._lock:
            self._forget_old(now)
            asked = self._asked.setdefault(visitor, deque())
            if len(asked) >= self._per_minute:
                return False
            asked.append(now)
            return True

    def _forget_old(self, now: float) -> None:
        # Visitors come and go; without this the table grows for as long as the app runs.
        for visitor in list(self._asked):
            asked = self._asked[visitor]
            while asked and now - asked[0] >= WINDOW_SECONDS:
                asked.popleft()
            if not asked:
                del self._asked[visitor]

    def tracked_visitors(self) -> int:
        return len(self._asked)


def utc_today() -> date:
    # The one place the wall clock is read. It decides when the budget resets,
    # never what "today" means for the data: that is AS_OF.
    return datetime.now(UTC).date()


class DailyBudget:
    """Stops the Ask endpoint for the day once the model has cost `limit_usd`.

    A question reserves its worst-case cost before the model is called and settles to
    the real cost afterwards. Checking only what has already been spent would let a
    burst of questions through together and overshoot the limit by all of them.
    """

    def __init__(self, limit_usd: float, today: Callable[[], date] = utc_today) -> None:
        self._limit = limit_usd
        self._today = today
        self._day = today()
        self._spent = 0.0
        self._reserved = 0.0
        self._lock = threading.Lock()

    def _roll_over(self) -> None:
        if self._today() != self._day:
            self._day = self._today()
            self._spent = 0.0

    def reserve(self, estimate_usd: float) -> bool:
        """Hold room for one question, or say there is none left today."""
        with self._lock:
            self._roll_over()
            if self._spent >= self._limit:
                return False
            if self._spent + self._reserved + estimate_usd > self._limit:
                return False
            self._reserved += estimate_usd
            return True

    def settle(self, estimate_usd: float, actual_usd: float) -> None:
        """Release a reservation and record what the question really cost."""
        with self._lock:
            self._roll_over()
            self._reserved = max(0.0, self._reserved - estimate_usd)
            self._spent += actual_usd

    @property
    def spent_usd(self) -> float:
        with self._lock:
            self._roll_over()
            return self._spent
