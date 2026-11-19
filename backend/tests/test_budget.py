import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from budget import Fx, compute, parse_amount, plan_lines  # noqa: E402


def wk(d):
    return d.weekday() < 5


def T(id, start, finish, dur, pct=0, parent=None, summary=False, **kw):
    return {"id": id, "parent_id": parent, "summary": summary, "start": start, "finish": finish, "duration": dur,
            "percent": pct, "baseline_start": None, "baseline_finish": None, "baseline_cost": None, **kw}


def test_plan_lines_labor_items_and_fx():
    fx = Fx("EUR", {"USD": 0.5})
    tasks = [T(1, "2026-10-12", "2026-10-16", 5)]
    res = {1: {"cost_rate": 100, "currency": "", "cost_center_id": 7, "cost_type_id": 3},
           2: {"cost_rate": 200, "currency": "USD", "cost_center_id": None, "cost_type_id": None}}
    asg = [{"task_id": 1, "resource_id": 1, "units": 50}, {"task_id": 1, "resource_id": 2, "units": 100}]
    items = [{"task_id": 1, "amount": 1000, "currency": "USD", "cost_center_id": 7, "cost_type_id": 9}]
    lines = plan_lines(tasks, asg, res, items, fx)
    assert [round(x["amount"], 2) for x in lines] == [250.0, 500.0, 500.0]  # 100*5*.5 ; 200*5*.5(USD) ; 1000*.5
    assert lines[0]["cc"] == 7 and lines[0]["ct"] == 3 and lines[2]["kind"] == "item"


def test_unknown_currency_raises():
    with pytest.raises(ValueError):
        Fx("EUR", {}).to_base(10, "GBP")


def test_evm_metrics_and_forecast():
    tasks = [T(1, "2026-10-12", "2026-10-16", 5, pct=50), T(2, "2026-10-19", "2026-10-23", 5, pct=0)]
    lines = [{"task_id": 1, "cc": 1, "ct": 1, "amount": 1000.0, "kind": "item"},
             {"task_id": 2, "cc": 1, "ct": 1, "amount": 1000.0, "kind": "item"}]
    acts = [{"task_id": 1, "booking_date": "2026-10-14", "amount_base": 800.0, "cost_center_id": 1, "cost_type_id": 1}]
    cc = [{"id": 1, "code": "K1", "name": "IT"}]
    ct = [{"id": 1, "code": "A1", "name": "Personal"}]
    bud = [{"cost_center_id": None, "cost_type_id": None, "amount": 1800.0}]
    r = compute(tasks, lines, acts, bud, cc, ct, wk, date(2026, 10, 16))
    s = r["summary"]
    assert s["bac"] == 2000 and s["plan"] == 2000 and s["pv"] == 1000 and s["ev"] == 500 and s["ac"] == 800
    assert s["cv"] == -300 and s["sv"] == -500
    assert s["cpi"] == pytest.approx(0.625) and s["spi"] == pytest.approx(0.5)
    assert s["eac"] == pytest.approx(3200) and s["etc"] == pytest.approx(2400)
    assert s["plan_over_budget"] is True and s["actual_over_budget"] is False
    assert s["remaining_budget"] == 1000
    row = r["by_cost_center"][0]
    assert (row["plan"], row["actual"]) == (2000, 800)
    assert r["per_task"]["1"]["actual"] == 800


def test_baseline_cost_is_used_for_bac_and_pv():
    t = T(1, "2026-10-19", "2026-10-23", 5, pct=100, baseline_start="2026-10-12", baseline_finish="2026-10-16",
          baseline_cost=500.0)
    lines = [{"task_id": 1, "cc": None, "ct": None, "amount": 900.0, "kind": "item"}]
    r = compute([t], lines, [], [], [], [], wk, date(2026, 10, 16))
    s = r["summary"]
    assert s["bac"] == 500 and s["plan"] == 900 and s["pv"] == 500 and s["ev"] == 500


def test_summary_rollup_and_series():
    tasks = [T(1, "2026-10-12", "2026-11-06", 20, summary=True),
             T(2, "2026-10-12", "2026-10-30", 15, parent=1), T(3, "2026-11-02", "2026-11-06", 5, parent=1)]
    lines = [{"task_id": 2, "cc": None, "ct": None, "amount": 1500.0, "kind": "item"},
             {"task_id": 3, "cc": None, "ct": None, "amount": 500.0, "kind": "item"}]
    r = compute(tasks, lines, [], [], [], [], wk, date(2026, 10, 31))
    assert r["per_task"]["1"]["plan"] == 2000
    assert [p["month"] for p in r["series"]] == ["2026-10", "2026-11"]
    assert r["series"][0]["pv"] == pytest.approx(1500) and r["series"][1]["pv"] == pytest.approx(2000)


@pytest.mark.parametrize("raw,exp", [("1.234,56", 1234.56), ("1,234.56", 1234.56), ("-12,5", -12.5), ("12,5-", -12.5),
                                      ("1234.5", 1234.5), ("(100)", -100), ("1.234.567", 1234567.0), ("0,99", 0.99)])
def test_parse_amount(raw, exp):
    assert parse_amount(raw) == pytest.approx(exp)
