"""Terminplanungs-Engine (Critical Path Method) für OpenPlan.

Reine Python-Logik ohne DB-/HTTP-Abhängigkeiten, damit sie isoliert testbar ist.

Modell
------
* Alle Rechnungen laufen auf **Arbeitstag-Indizes** (Index 0 = erster Arbeitstag ab
  Projektstart) mit *exklusivem* Ende: ``end = start + dauer``.
* Vorgänge mit Kindern sind Sammelvorgänge: Start/Ende/Fortschritt werden aus den
  Kindern berechnet. Abhängigkeiten an Sammelvorgängen werden auf deren
  Blatt-Vorgänge expandiert.
* Meilensteine (Dauer 0) liegen am *Ende* eines Arbeitstages (wie in MS Project):
  Anzeige-Datum = Arbeitstag ``start - 1``.
* Verknüpfungstypen: FS, SS, FF, SF mit Verzögerung (Lag) in Arbeitstagen.
* Constraints: ASAP (Standard), SNET (Start frühestens), MSO (Start fest),
  FNLT (Ende spätestens, wirkt nur auf die Rückwärtsrechnung / Puffer).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Set, Tuple

DEP_TYPES = ("FS", "SS", "FF", "SF")
CONSTRAINTS = ("ASAP", "SNET", "MSO", "FNLT")


class CycleError(ValueError):
    """Abhängigkeiten enthalten einen Zyklus."""

    def __init__(self, task_ids: List[int]):
        super().__init__("Zyklische Abhängigkeit zwischen Vorgängen: %s" % task_ids)
        self.task_ids = task_ids


class Calendar:
    """Arbeitstag-Kalender. ``work_days``: Wochentage 0=Mo … 6=So."""

    def __init__(self, origin: date, work_days: Iterable[int] = (0, 1, 2, 3, 4),
                 holidays: Iterable[date] = ()):
        self.work_days = frozenset(work_days) or frozenset({0, 1, 2, 3, 4})
        self.holidays = frozenset(holidays)
        # Origin auf den ersten Arbeitstag schieben
        while not self.is_working(origin):
            origin += timedelta(days=1)
        self.origin = origin
        self._days: List[date] = [origin]  # Index -> Datum

    def is_working(self, d: date) -> bool:
        return d.weekday() in self.work_days and d not in self.holidays

    def _extend_to(self, idx: int) -> None:
        while len(self._days) <= idx:
            d = self._days[-1] + timedelta(days=1)
            while not self.is_working(d):
                d += timedelta(days=1)
            self._days.append(d)

    def to_date(self, idx: int) -> date:
        if idx < 0:
            idx = 0
        self._extend_to(idx)
        return self._days[idx]

    def to_idx(self, d: date) -> int:
        """Datum -> Index; Nicht-Arbeitstage rutschen auf den nächsten Arbeitstag."""
        if d <= self.origin:
            return 0
        # Überschlag: höchstens (d - origin) Arbeitstage
        self._extend_to(min((d - self.origin).days, 100000))
        lo, hi = 0, len(self._days) - 1
        while lo < hi:  # erstes Element >= d
            mid = (lo + hi) // 2
            if self._days[mid] < d:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def idx_end_of_day(self, d: date) -> int:
        """Exklusives Ende, wenn etwas am *Ende* des Tages ``d`` passiert."""
        if d < self.origin:
            return 0
        i = self.to_idx(d)
        # d ist Nicht-Arbeitstag -> to_idx liefert nächsten Arbeitstag; das Ende des
        # vorherigen Arbeitstags ist dann i selbst (exklusiv).
        return i + 1 if self.to_date(i) == d else i


@dataclass
class TaskIn:
    id: int
    parent_id: Optional[int] = None
    position: int = 0
    duration: int = 1              # Arbeitstage; 0 = Meilenstein
    percent: float = 0.0
    constraint: str = "ASAP"
    constraint_date: Optional[date] = None


@dataclass
class DepIn:
    pred_id: int
    succ_id: int
    type: str = "FS"
    lag: int = 0                   # Arbeitstage, darf negativ sein


@dataclass
class TaskOut:
    id: int
    summary: bool
    start: date
    finish: date                   # inklusive (letzter Arbeitstag / Meilenstein-Tag)
    duration: int
    percent: float
    total_float: Optional[int] = None   # Gesamtpuffer in Arbeitstagen (Sammelvorgang: kleinster Puffer der Teilvorgänge)
    free_float: Optional[int] = None    # freier Puffer: so viele Arbeitstage darf der Vorgang rutschen, ohne einen Nachfolger zu verschieben (nur Blätter)
    critical: bool = False
    # interne Indizes (für Debugging/Tests)
    es: int = 0
    ef: int = 0


@dataclass
class Result:
    tasks: Dict[int, TaskOut] = field(default_factory=dict)
    project_start: Optional[date] = None
    project_finish: Optional[date] = None
    critical_path: List[int] = field(default_factory=list)


def _expand_deps(tasks: Dict[int, TaskIn], children: Dict[int, List[int]],
                 deps: List[DepIn]) -> List[DepIn]:
    """Abhängigkeiten an Sammelvorgängen auf Blatt-Vorgänge abbilden."""

    def leaves(tid: int) -> List[int]:
        kids = children.get(tid)
        if not kids:
            return [tid]
        out: List[int] = []
        for k in kids:
            out.extend(leaves(k))
        return out

    seen: Set[Tuple[int, int, str, int]] = set()
    out: List[DepIn] = []
    for d in deps:
        if d.pred_id not in tasks or d.succ_id not in tasks:
            continue
        for p in leaves(d.pred_id):
            for s in leaves(d.succ_id):
                if p == s:
                    continue
                key = (p, s, d.type, d.lag)
                if key not in seen:
                    seen.add(key)
                    out.append(DepIn(p, s, d.type, d.lag))
    return out


def _toposort(ids: List[int], deps: List[DepIn]) -> List[int]:
    indeg = {i: 0 for i in ids}
    succ: Dict[int, List[int]] = {i: [] for i in ids}
    for d in deps:
        succ[d.pred_id].append(d.succ_id)
        indeg[d.succ_id] += 1
    queue = [i for i in ids if indeg[i] == 0]
    order: List[int] = []
    while queue:
        n = queue.pop(0)
        order.append(n)
        for m in succ[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
    if len(order) != len(ids):
        raise CycleError(sorted(i for i in ids if indeg[i] > 0))
    return order


def find_cycle(tasks: Iterable[TaskIn], deps: List[DepIn]) -> Optional[List[int]]:
    """Gibt die an einem Zyklus beteiligten Vorgänge zurück (oder None)."""
    tmap = {t.id: t for t in tasks}
    children: Dict[int, List[int]] = {}
    for t in tmap.values():
        if t.parent_id in tmap:
            children.setdefault(t.parent_id, []).append(t.id)
    leaf_ids = [i for i in tmap if i not in children]
    try:
        _toposort(leaf_ids, _expand_deps(tmap, children, deps))
    except CycleError as e:
        return e.task_ids
    return None


def schedule(tasks: List[TaskIn], deps: List[DepIn], project_start: date,
             work_days: Iterable[int] = (0, 1, 2, 3, 4),
             holidays: Iterable[date] = ()) -> Result:
    cal = Calendar(project_start, work_days, holidays)
    tmap: Dict[int, TaskIn] = {t.id: t for t in tasks}
    children: Dict[int, List[int]] = {}
    for t in sorted(tasks, key=lambda x: x.position):
        if t.parent_id in tmap:
            children.setdefault(t.parent_id, []).append(t.id)

    leaf_ids = [i for i in tmap if i not in children]
    edges = _expand_deps(tmap, children, deps)
    order = _toposort(leaf_ids, edges)

    preds: Dict[int, List[DepIn]] = {i: [] for i in leaf_ids}
    succs: Dict[int, List[DepIn]] = {i: [] for i in leaf_ids}
    for e in edges:
        preds[e.succ_id].append(e)
        succs[e.pred_id].append(e)

    es: Dict[int, int] = {}
    dur: Dict[int, int] = {i: max(0, int(tmap[i].duration)) for i in leaf_ids}

    # ── Vorwärtsrechnung ────────────────────────────────────────────────
    for i in order:
        t, d = tmap[i], dur[i]
        lo = 0
        if t.constraint in ("SNET", "MSO") and t.constraint_date:
            lo = (cal.idx_end_of_day(t.constraint_date) if d == 0
                  else cal.to_idx(t.constraint_date))
        if t.constraint == "MSO":
            es[i] = lo
            continue
        for e in preds[i]:
            ps, pe = es[e.pred_id], es[e.pred_id] + dur[e.pred_id]
            if e.type == "FS":
                lo = max(lo, pe + e.lag)
            elif e.type == "SS":
                lo = max(lo, ps + e.lag)
            elif e.type == "FF":
                lo = max(lo, pe + e.lag - d)
            else:  # SF
                lo = max(lo, ps + e.lag - d)
        es[i] = max(lo, 0)

    ef = {i: es[i] + dur[i] for i in leaf_ids}
    proj_end = max(ef.values()) if ef else 0

    # ── Rückwärtsrechnung ───────────────────────────────────────────────
    lf: Dict[int, int] = {}
    ls: Dict[int, int] = {}
    for i in reversed(order):
        t, d = tmap[i], dur[i]
        hi = proj_end
        if t.constraint == "FNLT" and t.constraint_date:
            hi = min(hi, cal.idx_end_of_day(t.constraint_date))
        for e in succs[i]:
            s_s, s_f = ls[e.succ_id], lf[e.succ_id]
            if e.type == "FS":
                hi = min(hi, s_s - e.lag)
            elif e.type == "SS":
                hi = min(hi, s_s - e.lag + d)
            elif e.type == "FF":
                hi = min(hi, s_f - e.lag)
            else:  # SF
                hi = min(hi, s_f - e.lag + d)
        lf[i] = hi
        ls[i] = hi - d

    def free_float(i: int, total: int) -> int:
        if not succs[i]:
            ff = proj_end - ef[i]
        else:
            ff = None
            for e in succs[i]:
                s_s, s_f = es[e.succ_id], ef[e.succ_id]
                if e.type == "FS":
                    v = s_s - (ef[i] + e.lag)
                elif e.type == "SS":
                    v = s_s - (es[i] + e.lag)
                elif e.type == "FF":
                    v = s_f - (ef[i] + e.lag)
                else:  # SF
                    v = s_f - (es[i] + e.lag)
                ff = v if ff is None else min(ff, v)
        return max(min(ff, total), 0)

    out: Dict[int, TaskOut] = {}
    for i in leaf_ids:
        d = dur[i]
        total_float = ls[i] - es[i]
        if d == 0:
            start_d = finish_d = cal.to_date(es[i] - 1)
        else:
            start_d, finish_d = cal.to_date(es[i]), cal.to_date(ef[i] - 1)
        out[i] = TaskOut(
            id=i, summary=False, start=start_d, finish=finish_d, duration=d,
            percent=float(tmap[i].percent), total_float=total_float, free_float=free_float(i, total_float),
            critical=total_float <= 0, es=es[i], ef=ef[i])

    # ── Sammelvorgänge von unten nach oben ──────────────────────────────
    def roll(tid: int) -> TaskOut:
        if tid in out:
            return out[tid]
        kids = [roll(k) for k in children[tid]]
        start_d = min(k.start for k in kids)
        finish_d = max(k.finish for k in kids)
        total = sum(max(k.duration, 0) for k in kids)
        pct = (sum(k.percent * k.duration for k in kids) / total) if total else (
            sum(k.percent for k in kids) / len(kids))
        so = TaskOut(
            id=tid, summary=True, start=start_d, finish=finish_d,
            duration=_workdays_between(cal, start_d, finish_d),
            percent=round(pct, 1), total_float=min((k.total_float for k in kids if k.total_float is not None), default=None),
            critical=any(k.critical for k in kids),
            es=min(k.es for k in kids), ef=max(k.ef for k in kids))
        out[tid] = so
        return so

    for tid in tmap:
        roll(tid)

    # ── Kritischer Pfad (Kette kritischer Blätter in Plan-Reihenfolge) ──
    crit = [i for i in order if out[i].critical and dur[i] >= 0]
    crit.sort(key=lambda i: (es[i], i))

    res = Result(tasks=out, critical_path=crit)
    if leaf_ids:
        res.project_start = min(out[i].start for i in leaf_ids)
        res.project_finish = max(out[i].finish for i in leaf_ids)
    return res


def _workdays_between(cal: Calendar, a: date, b: date) -> int:
    return max(cal.to_idx(b) - cal.to_idx(a) + 1, 0)
