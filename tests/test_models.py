from hajime.models import BREAK, WORK, Pomodoro, Task, belt_rank, completion


def test_completion():
    assert completion([]) == 0.0
    assert completion([Task("a", True), Task("b")]) == 0.5


def test_belt_rank_bounds():
    assert belt_rank(0) == 0
    assert belt_rank(0.99) == 5
    assert belt_rank(1) == 6
    assert belt_rank(-1) == 0


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_pomodoro_credits_work_and_switches():
    clock = FakeClock()
    timer = Pomodoro(10, 3, clock)
    timer.start()
    clock.now = 4.4
    assert timer.tick() == (4, False)
    assert timer.remaining == 6
    clock.now = 100
    assert timer.tick() == (6, True)
    assert (timer.mode, timer.running, timer.remaining) == (BREAK, False, 3)


def test_break_earns_no_focus_and_returns_to_work():
    clock = FakeClock()
    timer = Pomodoro(10, 3, clock)
    timer.start()
    clock.now = 10
    timer.tick()
    timer.start()
    clock.now = 20
    assert timer.tick() == (0, True)
    assert timer.mode == WORK


def test_pause_and_reset():
    clock = FakeClock()
    timer = Pomodoro(10, 3, clock)
    timer.start()
    clock.now = 3
    assert timer.pause() == 3
    clock.now = 50  # paused time must not count
    assert timer.tick() == (0, False)
    assert timer.remaining == 7
    timer.start()
    clock.now = 52
    assert timer.reset() == 2
    assert timer.remaining == 10


def test_switch_modes():
    clock = FakeClock()
    timer = Pomodoro(10, 3, clock)
    timer.start()
    clock.now = 4
    assert timer.switch(BREAK) == 4  # work done so far is returned, not lost
    assert (timer.mode, timer.running, timer.remaining) == (BREAK, False, 3)
    assert timer.switch(WORK) == 0
    assert timer.remaining == 10


def test_switch_rejects_unknown_mode():
    import pytest

    with pytest.raises(ValueError):
        Pomodoro(10, 3).switch("nap")
