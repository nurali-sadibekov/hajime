"""Pure domain logic (no GUI): tasks, belt ranks and the Pomodoro state machine."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from .config import BELTS


@dataclass
class Task:
    title: str
    done: bool = False


@dataclass
class Board:
    """A named, independent to-do list with its own belt progress."""

    name: str
    tasks: list[Task] = field(default_factory=list)


def completion(tasks: list[Task]) -> float:
    """Fraction of completed tasks in ``[0, 1]``."""
    return sum(t.done for t in tasks) / len(tasks) if tasks else 0.0


def belt_rank(fraction: float) -> int:
    """Map a completion fraction to a belt index; only 100% earns the last belt."""
    if fraction >= 1:
        return len(BELTS) - 1
    return min(int(max(0.0, fraction) * (len(BELTS) - 1)), len(BELTS) - 2)


WORK, BREAK = "work", "break"


class Pomodoro:
    """Drift-free work/break timer driven by an injectable monotonic clock."""

    def __init__(
        self, work: int, rest: int, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._durations = {WORK: work, BREAK: rest}
        self._clock = clock
        self.mode = WORK
        self.running = False
        self._left = float(work)
        self._last = 0.0
        self._credited = 0

    @property
    def duration(self) -> int:
        return self._durations[self.mode]

    @property
    def remaining(self) -> int:
        return max(0, math.ceil(self._left))

    def start(self) -> None:
        if not self.running:
            self.running = True
            self._last = self._clock()

    def pause(self) -> int:
        """Stop the clock; returns focus seconds accrued since the last tick."""
        worked, _ = self.tick()
        self.running = False
        return worked

    def reset(self) -> int:
        worked = self.pause()
        self._begin(self.mode)
        return worked

    def switch(self, mode: str) -> int:
        """Jump to ``mode`` with a fresh countdown; returns unsaved focus seconds."""
        if mode not in self._durations:
            raise ValueError(f"unknown mode: {mode!r}")
        worked = self.pause()
        self._begin(mode)
        return worked

    def tick(self) -> tuple[int, bool]:
        """Advance time. Returns ``(focus_seconds_earned, phase_finished)``."""
        if not self.running:
            return 0, False
        now = self._clock()
        self._left -= max(0.0, now - self._last)
        self._last = now
        finished = self._left <= 0
        elapsed = self.duration if finished else int(self.duration - self._left)
        earned = elapsed - self._credited
        self._credited = elapsed
        was_work = self.mode == WORK
        if finished:
            self.running = False
            self._begin(BREAK if was_work else WORK)
        return (earned if was_work else 0), finished

    def _begin(self, mode: str) -> None:
        self.mode = mode
        self._left = float(self._durations[mode])
        self._credited = 0
