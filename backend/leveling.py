"""Überlastungs-Vorschlag („Leveling“): schlägt Verschiebungen vor, die Überlastung und Einsatz während einer
Abwesenheit auflösen, **ohne** Nachfolger oder das Projektende zu verschieben.

Verschoben wird nur innerhalb des *freien Puffers* eines Vorgangs (siehe ``cpm.TaskOut.free_float``). Greedy: der
früheste überlastete Tag einer Ressource wird aufgelöst, indem der Vorgang mit dem kleinsten nötigen Versatz hinter
diesen Tag geschoben wird; das wiederholt sich, bis nichts mehr geht. Was nicht innerhalb des Puffers lösbar ist,
steht in ``unresolved`` (dort braucht es eine Entscheidung: umverteilen, Termin ändern, Kapazität erhöhen).
Übernommen wird ein Vorschlag als Einschränkung „Beginn frühestens“ (SNET); vorher wird er serverseitig neu geprüft.
"""
from __future__ import annotations

import datetime as dt
from datetime import date
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import access
import cpm
import history
import service as svc
import user_absences
from database import get_db

router = APIRouter(prefix="/api", dependencies=[Depends(history.record, scope="function")])
MAX_STEPS = 500
MAX_UNRESOLVED = 60


def _today() -> date:
    return dt.date.today()


def _calendar(proj) -> cpm.Calendar:
    return cpm.Calendar(date.fromisoformat(proj["start_date"]), svc.parse_days(proj["work_days"]), svc.parse_holidays(proj["holidays"]))


def _absent_idx(cal: cpm.Calendar, ranges: List[Any]) -> set:
    out = set()
    for s, e in ranges:
        lo, hi = cal.to_idx(date.fromisoformat(s)), cal.idx_end_of_day(date.fromisoformat(e))
        out.update(range(lo, hi))
    return out


def propose(db, pid: int) -> Dict[str, Any]:
    proj, trows, _drows, res = svc.run_schedule(db, pid)
    cal = _calendar(proj)
    rows = {r["id"]: r for r in trows}
    resources = {r["id"]: dict(r) for r in db.execute("SELECT * FROM resources WHERE project_id=?", (pid,))}
    assigns = [dict(a) for a in db.execute(
        "SELECT a.* FROM assignments a JOIN tasks t ON t.id=a.task_id WHERE t.project_id=?", (pid,))]
    leaves = {i: o for i, o in res.tasks.items() if not o.summary}
    by_res: Dict[int, List[Dict[str, Any]]] = {}
    for a in assigns:
        t = leaves.get(a["task_id"])
        if t and t.duration > 0 and rows[a["task_id"]]["status"] != "done" and a["resource_id"] in resources:
            by_res.setdefault(a["resource_id"], []).append(a)
    horizon = max([o.ef + (o.free_float or 0) for o in leaves.values()] + [1]) + 1

    ranges: Dict[int, List[Any]] = {}
    for a in db.execute("SELECT resource_id, start_date, end_date FROM absences WHERE project_id=?", (pid,)):
        ranges.setdefault(a["resource_id"], []).append((a["start_date"], a["end_date"]))
    for a in user_absences.project_absences(db, pid, None):
        ranges.setdefault(a["resource_id"], []).append((a["start_date"], a["end_date"]))
    cap: Dict[int, List[float]] = {}
    for rid, r in resources.items():
        c = [float(r["max_units"])] * horizon
        for i in _absent_idx(cal, ranges.get(rid, [])):
            if 0 <= i < horizon:
                c[i] = 0.0
        cap[rid] = c

    shift: Dict[int, int] = {}
    today_idx = cal.to_idx(_today())

    def eligible(tid: int) -> bool:
        r = rows[tid]
        return r["percent"] == 0 and r["status"] in ("open", "blocked") and r["constraint_type"] != "MSO"

    def loads() -> Dict[int, List[float]]:
        out = {rid: [0.0] * horizon for rid in by_res}
        for rid, al in by_res.items():
            for a in al:
                t = leaves[a["task_id"]]
                s = shift.get(t.id, 0)
                for i in range(t.es + s, min(t.ef + s, horizon)):
                    out[rid][i] += a["units"]
        return out

    def conflicts(load) -> List[Any]:
        found = []
        for rid, l in load.items():
            if resources[rid]["max_units"] <= 0:
                continue
            for i, v in enumerate(l):
                if i >= today_idx and v > cap[rid][i]:
                    found.append((i, rid))
        return sorted(found)

    before = len(conflicts(loads()))
    ignored: set = set()
    unresolved: List[Dict[str, Any]] = []
    for _ in range(MAX_STEPS):
        load = loads()
        todo = [c for c in conflicts(load) if c not in ignored]
        if not todo:
            break
        day, rid = todo[0]
        cands = []
        for a in by_res.get(rid, []):
            t = leaves[a["task_id"]]
            cur = t.es + shift.get(t.id, 0)
            if not (cur <= day < cur + t.duration) or not eligible(t.id):
                continue
            need = day - cur + 1
            budget = (t.free_float or 0) - shift.get(t.id, 0)
            dl = rows[t.id]["deadline"]
            if need > budget or (dl and cal.to_date(cur + need + t.duration - 1).isoformat() > dl):
                continue
            cands.append((need, -budget, t.id))
        if not cands:
            ignored.add((day, rid))
            if len(unresolved) < MAX_UNRESOLVED:
                names = [{"id": a["task_id"], "name": rows[a["task_id"]]["name"]} for a in by_res.get(rid, [])
                         if leaves[a["task_id"]].es + shift.get(a["task_id"], 0) <= day < leaves[a["task_id"]].ef + shift.get(a["task_id"], 0)]
                unresolved.append({"resource_id": rid, "resource": resources[rid]["name"], "date": cal.to_date(day).isoformat(),
                                   "load": load[rid][day], "capacity": cap[rid][day], "tasks": names})
            continue
        need, _b, tid = min(cands)
        shift[tid] = shift.get(tid, 0) + need

    moves = []
    for tid, s in sorted(shift.items(), key=lambda kv: (leaves[kv[0]].es, kv[0])):
        t = leaves[tid]
        moves.append({
            "task_id": tid, "name": rows[tid]["name"], "shift": s,
            "old_start": t.start.isoformat(), "old_finish": t.finish.isoformat(),
            "new_start": cal.to_date(t.es + s).isoformat(), "new_finish": cal.to_date(t.ef + s - 1).isoformat(),
            "resources": sorted({resources[a["resource_id"]]["name"] for a in assigns if a["task_id"] == tid and a["resource_id"] in resources}),
        })
    return {"conflicts_before": before, "conflicts_after": len(unresolved), "moves": moves, "unresolved": unresolved}


@router.get("/projects/{pid}/leveling")
def get_proposal(pid: int, user=Depends(access.proj("edit")), db=Depends(get_db, scope="function")):
    svc.get_project_row(db, pid)
    return propose(db, pid)


class MoveIn(BaseModel):
    task_id: int
    new_start: date


class ApplyIn(BaseModel):
    moves: List[MoveIn] = Field(min_length=1, max_length=500)


@router.post("/projects/{pid}/leveling/apply")
def apply_moves(pid: int, body: ApplyIn, user=Depends(access.proj("edit")), db=Depends(get_db, scope="function")):
    proj, trows, _d, res = svc.run_schedule(db, pid)
    cal = _calendar(proj)
    rows = {r["id"]: r for r in trows}
    done = set()
    for m in body.moves:
        o = res.tasks.get(m.task_id)
        if not o or o.summary or m.task_id not in rows or m.task_id in done:
            raise HTTPException(422, "Ungültiger Vorgang in der Verschiebung")
        done.add(m.task_id)
        if rows[m.task_id]["constraint_type"] == "MSO":
            raise HTTPException(422, "Manuell geplante Vorgänge werden nicht verschoben")
        idx = cal.to_idx(m.new_start)
        if cal.to_date(idx) != m.new_start:
            raise HTTPException(422, "Der neue Beginn ist kein Arbeitstag")
        if not 0 < idx - o.es <= (o.free_float or 0):
            raise HTTPException(422, "Die Verschiebung übersteigt den freien Puffer")
    for m in body.moves:
        db.execute("UPDATE tasks SET constraint_type='SNET', constraint_date=? WHERE id=? AND project_id=?",
                   (m.new_start.isoformat(), m.task_id, pid))
    svc.bump(db, pid)
    svc.log(db, pid, user, "Überlastung aufgelöst", "%d Vorgang/Vorgänge verschoben" % len(body.moves))
    return svc.load_project(db, pid, user)
