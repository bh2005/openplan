import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from cpm import CycleError, DepIn, TaskIn, find_cycle, schedule  # noqa: E402

MON = date(2026, 10, 12)  # Montag


def run(tasks, deps=(), holidays=()):
    return schedule(list(tasks), list(deps), MON, holidays=holidays)


def test_single_task_dates():
    r = run([TaskIn(1, duration=5)])
    assert r.tasks[1].start == date(2026, 10, 12)
    assert r.tasks[1].finish == date(2026, 10, 16)


def test_weekend_is_skipped():
    r = run([TaskIn(1, duration=6)])
    assert r.tasks[1].finish == date(2026, 10, 19)  # Mo der Folgewoche


def test_start_on_weekend_moves_to_monday():
    r = schedule([TaskIn(1, duration=1)], [], date(2026, 10, 17))
    assert r.tasks[1].start == date(2026, 10, 19)


def test_fs_chain_and_lag():
    r = run([TaskIn(1, duration=2), TaskIn(2, duration=3)], [DepIn(1, 2, "FS", 1)])
    assert r.tasks[2].start == date(2026, 10, 15)  # Mo,Di + 1 Lag -> Do
    assert r.tasks[2].finish == date(2026, 10, 19)


def test_negative_lag_overlap():
    r = run([TaskIn(1, duration=4), TaskIn(2, duration=2)], [DepIn(1, 2, "FS", -1)])
    assert r.tasks[2].start == date(2026, 10, 15)


def test_ss_ff_sf():
    ts = [TaskIn(1, duration=5), TaskIn(2, duration=2), TaskIn(3, duration=2), TaskIn(4, duration=2)]
    r = run(ts, [DepIn(1, 2, "SS", 2), DepIn(1, 3, "FF", 0), DepIn(1, 4, "SF", 4)])
    assert r.tasks[2].start == date(2026, 10, 14)
    assert r.tasks[3].finish == r.tasks[1].finish == date(2026, 10, 16)
    # SF mit Lag 4: Ende (exkl.) von 4 >= Start von 1 + 4 Tage -> letzter Tag Do 15.10.
    assert r.tasks[4].finish == date(2026, 10, 15)


def test_milestone_at_end_of_predecessor():
    r = run([TaskIn(1, duration=3), TaskIn(2, duration=0)], [DepIn(1, 2)])
    assert r.tasks[2].start == r.tasks[2].finish == date(2026, 10, 14)


def test_snet_constraint():
    r = run([TaskIn(1, duration=1, constraint="SNET", constraint_date=date(2026, 10, 21))])
    assert r.tasks[1].start == date(2026, 10, 21)


def test_mso_ignores_predecessors():
    r = run([TaskIn(1, duration=5), TaskIn(2, duration=1, constraint="MSO",
                                           constraint_date=date(2026, 10, 13))],
            [DepIn(1, 2)])
    assert r.tasks[2].start == date(2026, 10, 13)


def test_holiday_skipped():
    r = run([TaskIn(1, duration=3)], holidays=[date(2026, 10, 13)])
    assert r.tasks[1].finish == date(2026, 10, 15)


def test_critical_path_and_float():
    # 1(3) -> 3(2) ;  2(1) -> 3   ==> 2 hat Puffer 2
    ts = [TaskIn(1, duration=3), TaskIn(2, duration=1), TaskIn(3, duration=2)]
    r = run(ts, [DepIn(1, 3), DepIn(2, 3)])
    assert r.tasks[1].critical and r.tasks[3].critical
    assert not r.tasks[2].critical
    assert r.tasks[2].total_float == 2
    assert r.critical_path == [1, 3]


def test_free_float_vs_total_float():
    # 1(3) -> 3(2) ; 2(1) -> 3 ; 4(1) -> 5(1) und 3 endet das Projekt, 5 hat eigenen Puffer
    ts = [TaskIn(1, duration=3), TaskIn(2, duration=1), TaskIn(3, duration=2), TaskIn(4, duration=1), TaskIn(5, duration=1)]
    r = run(ts, [DepIn(1, 3), DepIn(2, 3), DepIn(4, 5)])
    assert (r.tasks[2].total_float, r.tasks[2].free_float) == (2, 2)      # direkt vor 3: frei = gesamt
    assert (r.tasks[4].total_float, r.tasks[4].free_float) == (3, 0)      # 4 darf nur rutschen, bis 5 verschoben würde
    assert (r.tasks[5].total_float, r.tasks[5].free_float) == (3, 3)      # Ende ohne Nachfolger: bis zum Projektende
    assert r.tasks[1].free_float == 0 and r.tasks[3].free_float == 0     # kritisch


def test_summary_float_is_min_of_children():
    ts = [TaskIn(1, duration=1),
          TaskIn(2, parent_id=1, position=0, duration=3), TaskIn(3, parent_id=1, position=1, duration=1),
          TaskIn(4, duration=3)]
    r = run(ts, [DepIn(2, 4)])
    assert r.tasks[3].total_float == 5 and r.tasks[2].total_float == 0
    assert r.tasks[1].total_float == 0 and r.tasks[1].free_float is None


def test_summary_rollup_and_progress():
    ts = [TaskIn(1, duration=1),
          TaskIn(2, parent_id=1, position=0, duration=2, percent=100),
          TaskIn(3, parent_id=1, position=1, duration=2, percent=0)]
    r = run(ts, [DepIn(2, 3)])
    s = r.tasks[1]
    assert s.summary and s.start == date(2026, 10, 12) and s.finish == date(2026, 10, 15)
    assert s.percent == 50.0 and s.duration == 4


def test_dependency_on_summary_expands_to_leaves():
    ts = [TaskIn(1, duration=2),
          TaskIn(2, duration=1),  # Sammelvorgang (hat Kinder)
          TaskIn(3, parent_id=2, duration=2), TaskIn(4, parent_id=2, duration=1)]
    r = run(ts, [DepIn(1, 2)])
    assert r.tasks[3].start == r.tasks[4].start == date(2026, 10, 14)


def test_cycle_detected():
    ts = [TaskIn(1), TaskIn(2)]
    deps = [DepIn(1, 2), DepIn(2, 1)]
    assert find_cycle(ts, deps) == [1, 2]
    with pytest.raises(CycleError):
        run(ts, deps)


def test_no_cycle():
    assert find_cycle([TaskIn(1), TaskIn(2)], [DepIn(1, 2)]) is None
