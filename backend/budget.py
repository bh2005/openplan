"""Kosten- und Budget-Berechnung (reine Logik, ohne DB/HTTP).

Begriffe
--------
* Plankosten eines Vorgangs = Personalkosten (Dauer × Tagessatz × Zuordnung %) + feste Kosten
  (Planposten). Alles wird mit den Projekt-Kursen in die Projektwährung umgerechnet.
* BAC  = Budget at Completion  (Basisplan-Kosten, sonst aktuelle Plankosten)
* PV   = Planned Value  (Plankosten, die bis zum Stichtag angefallen sein sollten)
* EV   = Earned Value   (BAC × Fortschritt %)
* AC   = Actual Cost    (gebuchte Ist-Kosten)
* CPI = EV/AC, SPI = EV/PV, CV = EV−AC, SV = EV−PV, EAC = BAC/CPI, ETC = EAC−AC, VAC = BAC−EAC
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

Key = Tuple[Optional[int], Optional[int]]  # (Kostenstelle, Kostenart)


class Fx:
    """Währungsumrechnung in die Projektwährung."""

    def __init__(self, base: str, rates: Dict[str, float]):
        self.base = base
        self.rates = dict(rates)

    def known(self, cur: Optional[str]) -> bool:
        return not cur or cur == self.base or cur in self.rates

    def rate(self, cur: Optional[str]) -> float:
        if not cur or cur == self.base:
            return 1.0
        if cur not in self.rates:
            raise ValueError("Kein Kurs für Währung %s hinterlegt" % cur)
        return self.rates[cur]

    def to_base(self, amount: float, cur: Optional[str]) -> float:
        return amount * self.rate(cur)


def plan_lines(tasks: List[Dict[str, Any]], assignments: List[Dict[str, Any]], resources: Dict[int, Dict[str, Any]],
               items: List[Dict[str, Any]], fx: Fx) -> List[Dict[str, Any]]:
    """Plankosten-Zeilen je Blatt-Vorgang: {task_id, cc, ct, amount, kind}."""
    leaves = {t["id"]: t for t in tasks if not t["summary"]}
    out: List[Dict[str, Any]] = []
    for a in assignments:
        t, r = leaves.get(a["task_id"]), resources.get(a["resource_id"])
        if not t or not r or not r.get("cost_rate") or t["duration"] <= 0:
            continue
        amt = fx.to_base(r["cost_rate"] * t["duration"] * a["units"] / 100.0, r.get("currency") or None)
        out.append({"task_id": t["id"], "cc": r.get("cost_center_id"), "ct": r.get("cost_type_id"),
                    "amount": amt, "kind": "labor"})
    for it in items:
        if it["task_id"] in leaves:
            out.append({"task_id": it["task_id"], "cc": it.get("cost_center_id"), "ct": it.get("cost_type_id"),
                        "amount": fx.to_base(it["amount"], it.get("currency") or None), "kind": "item"})
    return out


def _days(start: date, finish: date, is_working) -> List[date]:
    out, d = [], start
    while d <= finish:
        if is_working(d):
            out.append(d)
        d += timedelta(days=1)
    return out or [finish]  # Meilenstein / Randfälle: ein Tag


def _spread(total: float, start: str, finish: str, is_working) -> Dict[date, float]:
    ds = _days(date.fromisoformat(start), date.fromisoformat(finish), is_working)
    return {d: total / len(ds) for d in ds}


def compute(tasks: List[Dict[str, Any]], lines: List[Dict[str, Any]], actuals: List[Dict[str, Any]],
            budget_lines: List[Dict[str, Any]], cost_centers: List[Dict[str, Any]], cost_types: List[Dict[str, Any]],
            is_working, status: date) -> Dict[str, Any]:
    leaves = [t for t in tasks if not t["summary"]]
    plan_by_task: Dict[int, float] = defaultdict(float)
    for ln in lines:
        plan_by_task[ln["task_id"]] += ln["amount"]
    actual_by_task: Dict[int, float] = defaultdict(float)
    for a in actuals:
        if a.get("task_id") is not None:
            actual_by_task[a["task_id"]] += a["amount_base"]

    # BAC je Blatt: Basisplan-Kosten, falls vorhanden – sonst aktueller Plan
    bac: Dict[int, float] = {}
    pv_by_date: Dict[date, float] = defaultdict(float)
    plan_by_date: Dict[date, float] = defaultdict(float)
    for t in leaves:
        cur = plan_by_task.get(t["id"], 0.0)
        use_base = t.get("baseline_cost") is not None and t.get("baseline_start") and t.get("baseline_finish")
        b = t["baseline_cost"] if use_base else cur
        bac[t["id"]] = b
        if b:
            s, f = (t["baseline_start"], t["baseline_finish"]) if use_base else (t["start"], t["finish"])
            for d, v in _spread(b, s, f, is_working).items():
                pv_by_date[d] += v
        if cur:
            for d, v in _spread(cur, t["start"], t["finish"], is_working).items():
                plan_by_date[d] += v

    BAC = sum(bac.values())
    PLAN = sum(plan_by_task.values())
    PV = sum(v for d, v in pv_by_date.items() if d <= status)
    EV = sum(bac[t["id"]] * min(max(t["percent"], 0), 100) / 100.0 for t in leaves)
    AC = sum(a["amount_base"] for a in actuals)
    CPI = EV / AC if AC > 0 else None
    SPI = EV / PV if PV > 0 else None
    EAC = BAC / CPI if CPI and CPI > 0 else (AC + (BAC - EV) if AC > 0 else BAC)
    total_budget = next((b["amount"] for b in budget_lines if b["cost_center_id"] is None and b["cost_type_id"] is None), None)

    # Einzelwerte je Vorgang inkl. Sammelvorgang-Summen
    by_id = {t["id"]: t for t in tasks}
    per_task: Dict[int, Dict[str, float]] = {t["id"]: {"plan": 0.0, "bac": 0.0, "actual": 0.0, "ev": 0.0} for t in tasks}
    for t in leaves:
        v = per_task[t["id"]]
        v["plan"], v["bac"], v["actual"] = plan_by_task.get(t["id"], 0.0), bac[t["id"]], actual_by_task.get(t["id"], 0.0)
        v["ev"] = bac[t["id"]] * min(max(t["percent"], 0), 100) / 100.0
    for a_id, val in actual_by_task.items():
        if a_id in by_id and by_id[a_id]["summary"]:  # Ist direkt auf Sammelvorgang gebucht
            per_task[a_id]["actual"] += val
    for t in reversed(tasks):  # tasks in Outline-Reihenfolge -> Kinder stehen nach Eltern
        pid = t["parent_id"]
        if pid in per_task:
            for k in ("plan", "bac", "actual", "ev"):
                per_task[pid][k] += per_task[t["id"]][k]

    # Aufschlüsselung nach Kostenstelle / Kostenart / Matrix
    plan_m: Dict[Key, float] = defaultdict(float)
    for ln in lines:
        plan_m[(ln["cc"], ln["ct"])] += ln["amount"]
    act_m: Dict[Key, float] = defaultdict(float)
    for a in actuals:
        act_m[(a.get("cost_center_id"), a.get("cost_type_id"))] += a["amount_base"]
    bud_m: Dict[Key, float] = {(b["cost_center_id"], b["cost_type_id"]): b["amount"] for b in budget_lines}

    def group(axis: int, master: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        rows = []
        ids: List[Optional[int]] = [m["id"] for m in master] + [None]
        for gid in ids:
            plan = sum(v for k, v in plan_m.items() if k[axis] == gid)
            act = sum(v for k, v in act_m.items() if k[axis] == gid)
            bud = bud_m.get((gid, None) if axis == 0 else (None, gid))
            if gid is None and not plan and not act:
                continue
            m = next((x for x in master if x["id"] == gid), None)
            rows.append({"id": gid, "code": m["code"] if m else "", "name": m["name"] if m else "nicht zugeordnet",
                         "budget": bud, "plan": plan, "actual": act})
        return rows

    keys = sorted(set(plan_m) | set(act_m) | {k for k in bud_m if k[0] is not None and k[1] is not None},
                  key=lambda k: (k[0] is None, k[0] or 0, k[1] is None, k[1] or 0))
    matrix = [{"cost_center_id": k[0], "cost_type_id": k[1], "plan": plan_m.get(k, 0.0), "actual": act_m.get(k, 0.0),
               "budget": bud_m.get(k)} for k in keys]

    # Verlauf (kumuliert, monatlich)
    ac_by_month: Dict[str, float] = defaultdict(float)
    for a in actuals:
        ac_by_month[a["booking_date"][:7]] += a["amount_base"]
    pv_by_month: Dict[str, float] = defaultdict(float)
    for d, v in pv_by_date.items():
        pv_by_month[d.isoformat()[:7]] += v
    months = sorted(set(pv_by_month) | set(ac_by_month) | {status.isoformat()[:7]})
    series, pv_c, ac_c = [], 0.0, 0.0
    if months:
        y, m = map(int, months[0].split("-"))
        ey, em = map(int, months[-1].split("-"))
        while (y, m) <= (ey, em):
            key = "%04d-%02d" % (y, m)
            pv_c += pv_by_month.get(key, 0.0)
            ac_c += ac_by_month.get(key, 0.0)
            series.append({"month": key, "pv": pv_c, "ac": ac_c if key <= status.isoformat()[:7] or ac_by_month.get(key) else None})
            m += 1
            if m > 12:
                y, m = y + 1, 1

    return {
        "status_date": status.isoformat(),
        "summary": {"budget": total_budget, "bac": BAC, "plan": PLAN, "pv": PV, "ev": EV, "ac": AC,
                    "cpi": CPI, "spi": SPI, "cv": EV - AC, "sv": EV - PV, "eac": EAC, "etc": max(EAC - AC, 0.0),
                    "vac": BAC - EAC, "remaining_budget": (total_budget - AC) if total_budget is not None else None,
                    "plan_over_budget": bool(total_budget is not None and PLAN > total_budget + 0.005),
                    "actual_over_budget": bool(total_budget is not None and AC > total_budget + 0.005)},
        "by_cost_center": group(0, cost_centers),
        "by_cost_type": group(1, cost_types),
        "matrix": matrix,
        "per_task": {str(k): v for k, v in per_task.items()},
        "series": series,
    }


def parse_amount(s: str) -> float:
    """'1.234,56' / '1,234.56' / '-12,5' / '1234.5' -> float (SAP-/Excel-tauglich; Minus nachgestellt erlaubt)."""
    t = str(s).strip().replace(" ", "").replace(" ", "")
    neg = False
    if t.endswith("-"):
        neg, t = True, t[:-1]
    if t.startswith("(") and t.endswith(")"):
        neg, t = True, t[1:-1]
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    elif "," in t:
        t = t.replace(",", ".")
    elif t.count(".") > 1:
        t = t.replace(".", "")
    v = float(t)
    return -v if neg else v
