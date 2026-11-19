"""Projekt-Laden, Terminberechnung und gemeinsame Hilfsfunktionen."""
from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

import access
import cpm
import history
import user_absences


def parse_days(s: str) -> List[int]:
    return [int(x) for x in s.split(",") if x.strip() != ""] or [0, 1, 2, 3, 4]


def parse_holidays(s: str) -> List[date]:
    out = []
    for x in s.split(","):
        x = x.strip()
        if x:
            try:
                out.append(date.fromisoformat(x))
            except ValueError:
                pass
    return out


def _d(s: Optional[str]) -> Optional[date]:
    return date.fromisoformat(s) if s else None


def apply_status(status: str, percent: float, new_status: Optional[str] = None,
                 new_percent: Optional[float] = None) -> "tuple[str, float]":
    """Kopplung Status <-> Fortschritt.

    * Status gesetzt:  erledigt -> 100 %, offen -> 0 %, in Arbeit -> bei 0 %/100 % bleibt es (100 -> 90 %),
      blockiert -> Fortschritt unverändert (100 -> 90 %).
    * Fortschritt gesetzt: 100 -> erledigt; > 0 und (offen/erledigt) -> in Arbeit; 0 und erledigt -> offen.
    """
    if new_status is not None:
        status = new_status
        if status == "done":
            percent = 100.0
        elif status == "open":
            percent = 0.0
        elif percent >= 100:
            percent = 90.0
    elif new_percent is not None:
        percent = new_percent
        if percent >= 100:
            status = "done"
        elif percent > 0 and status in ("open", "done"):
            status = "in_progress"
        elif percent <= 0 and status == "done":
            status = "open"
    return status, percent


def derive_summary_status(children: List[str]) -> str:
    if all(c == "done" for c in children):
        return "done"
    if any(c == "blocked" for c in children):
        return "blocked"
    if any(c in ("in_progress", "done") for c in children):
        return "in_progress"
    return "open"


def get_project_row(db, pid: int):
    row = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if not row:
        raise HTTPException(404, "Projekt nicht gefunden")
    return row


def project_of_task(db, tid: int):
    row = db.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
    if not row:
        raise HTTPException(404, "Vorgang nicht gefunden")
    return row


def bump(db, pid: int) -> None:
    db.execute("UPDATE projects SET revision=revision+1, updated_at=datetime('now') WHERE id=?", (pid,))


def log(db, pid: int, user: Dict[str, Any], action: str, detail: str = "", task_id: Optional[int] = None) -> None:
    db.execute("INSERT INTO journal(project_id, task_id, username, action, detail) VALUES (?,?,?,?,?)",
               (pid, task_id, user["username"], action, detail[:500]))


def run_schedule(db, pid: int):
    proj = get_project_row(db, pid)
    trows = db.execute("SELECT * FROM tasks WHERE project_id=?", (pid,)).fetchall()
    drows = db.execute("SELECT * FROM deps WHERE project_id=?", (pid,)).fetchall()
    tasks = [cpm.TaskIn(id=r["id"], parent_id=r["parent_id"], position=r["position"],
                        duration=r["duration"], percent=r["percent"], constraint=r["constraint_type"],
                        constraint_date=_d(r["constraint_date"])) for r in trows]
    deps = [cpm.DepIn(r["pred_id"], r["succ_id"], r["type"], r["lag"]) for r in drows]
    try:
        res = cpm.schedule(tasks, deps, date.fromisoformat(proj["start_date"]),
                           parse_days(proj["work_days"]), parse_holidays(proj["holidays"]))
    except cpm.CycleError as e:
        raise HTTPException(422, {"message": str(e), "task_ids": e.task_ids})
    return proj, trows, drows, res


def validate_no_cycle(db, pid: int) -> None:
    run_schedule(db, pid)


def project_summary(db, row) -> Dict[str, Any]:
    d = dict(row)
    d["work_days"] = parse_days(d["work_days"])
    d["holidays"] = [h.isoformat() for h in parse_holidays(d["holidays"])]
    return d


def load_project(db, pid: int, user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    proj, trows, drows, res = run_schedule(db, pid)
    by_parent: Dict[Optional[int], List[Any]] = {}
    ids = {r["id"] for r in trows}
    for r in trows:
        by_parent.setdefault(r["parent_id"] if r["parent_id"] in ids else None, []).append(r)
    for lst in by_parent.values():
        lst.sort(key=lambda r: (r["position"], r["id"]))

    assign = db.execute(
        "SELECT a.task_id, a.resource_id, a.units FROM assignments a JOIN tasks t ON t.id=a.task_id "
        "WHERE t.project_id=?", (pid,)).fetchall()
    res_by_task: Dict[int, List[int]] = {}
    for a in assign:
        res_by_task.setdefault(a["task_id"], []).append(a["resource_id"])

    out: List[Dict[str, Any]] = []
    file_counts = {r["task_id"]: r["n"] for r in db.execute(
        "SELECT task_id, COUNT(*) AS n FROM task_files WHERE project_id=? GROUP BY task_id", (pid,))}
    comment_counts = {r["task_id"]: r["n"] for r in db.execute("SELECT task_id, COUNT(*) AS n FROM comments WHERE project_id=? GROUP BY task_id", (pid,))}
    from refs import refs_of_project
    ext_refs = refs_of_project(db, pid)
    own_status = {r["id"]: r["status"] for r in trows}
    kids_of: Dict[int, List[int]] = {}
    for r in trows:
        if r["parent_id"] in ids:
            kids_of.setdefault(r["parent_id"], []).append(r["id"])

    def eff_status(tid: int) -> str:
        return derive_summary_status([eff_status(k) for k in kids_of[tid]]) if tid in kids_of else own_status[tid]

    def walk(parent: Optional[int], prefix: str, level: int) -> None:
        for i, r in enumerate(by_parent.get(parent, []), 1):
            wbs = "%s%d" % (prefix, i)
            o = res.tasks[r["id"]]
            out.append({
                "id": r["id"], "parent_id": r["parent_id"], "position": r["position"],
                "wbs": wbs, "level": level, "name": r["name"],
                "duration": o.duration, "percent": o.percent,
                "constraint_type": r["constraint_type"], "constraint_date": r["constraint_date"],
                "notes": r["notes"], "deadline": r["deadline"], "ext_key": r["ext_key"],
                "attrs": json.loads(r["attrs"]) if r["attrs"] else None, "tpl_step": r["tpl_step"], "tpl_id": r["tpl_id"],
                "deadline_missed": bool(r["deadline"] and o.finish.isoformat() > r["deadline"] and eff_status(r["id"]) != "done"), "pool": bool(r["pool"]) and not kids_of.get(r["id"]), "status": eff_status(r["id"]), "status_note": r["status_note"], "file_count": file_counts.get(r["id"], 0), "comment_count": comment_counts.get(r["id"], 0), "refs": ext_refs.get(r["id"], {}), "summary": o.summary, "milestone": (not o.summary and o.duration == 0),
                "start": o.start.isoformat(), "finish": o.finish.isoformat(),
                "total_float": o.total_float, "free_float": o.free_float, "critical": o.critical,
                "baseline_start": r["baseline_start"], "baseline_finish": r["baseline_finish"],
                "resource_ids": res_by_task.get(r["id"], []),
            })
            walk(r["id"], wbs + ".", level + 1)

    walk(None, "", 0)
    p = project_summary(db, proj)
    p["finish"] = res.project_finish.isoformat() if res.project_finish else None
    p["first_task_start"] = res.project_start.isoformat() if res.project_start else None
    owner = db.execute("SELECT id, username, display_name FROM users WHERE id=?", (proj["owner_id"],)).fetchone()
    p["owner"] = dict(owner) if owner else None
    members = [dict(r) for r in db.execute(
        "SELECT m.user_id, u.username, u.display_name, m.role FROM project_members m JOIN users u ON u.id=m.user_id "
        "WHERE m.project_id=? ORDER BY lower(COALESCE(NULLIF(u.display_name, ''), u.username))", (pid,))]
    resources = [dict(r) for r in db.execute("SELECT * FROM resources WHERE project_id=? ORDER BY name", (pid,))]
    linked = {r["user_id"] for r in resources if r["user_id"]}
    if linked:                                                   # „Name (ID)“ der verknüpften Benutzer für die Ressourcenliste
        ulab = {u["id"]: (("%s (%s)" % (u["display_name"], u["username"])) if u["display_name"] else u["username"])
                for u in db.execute("SELECT id, username, display_name FROM users WHERE id IN (%s)" % ",".join("?" * len(linked)), list(linked))}
        for r in resources:
            r["user_label"] = ulab.get(r["user_id"], "") if r["user_id"] else ""
    cost_access = access.cost_level(db, user, pid) if user else "none"
    if cost_access == "none":
        for r in resources:
            for k in ("cost_rate", "cost_center_id", "cost_type_id"):
                r.pop(k, None)
    return {
        "project": p,
        "cost_access": cost_access,
        "members": members,
        "access": access.access_name(db, user, pid) if user else "view",
        "tasks": out,
        "deps": [dict(r) for r in drows],
        "resources": resources,
        "assignments": [dict(a) for a in assign],
        "absences": [dict(a, source="project") for a in db.execute(
            "SELECT id, resource_id, start_date, end_date, kind, note FROM absences WHERE project_id=? ORDER BY start_date, id", (pid,))]
                    + user_absences.project_absences(db, pid, user),
        "critical_path": res.critical_path,
        "history": history.state(db, pid),
    }


def renumber(db, pid: int, parent_id: Optional[int]) -> None:
    rows = db.execute(
        "SELECT id FROM tasks WHERE project_id=? AND parent_id IS ? ORDER BY position, id",
        (pid, parent_id)).fetchall()
    for i, r in enumerate(rows):
        db.execute("UPDATE tasks SET position=? WHERE id=?", (i, r["id"]))


def is_descendant(db, ancestor_id: int, candidate_id: Optional[int]) -> bool:
    """True, wenn candidate_id == ancestor_id oder darunter liegt."""
    cur = candidate_id
    seen = set()
    while cur is not None and cur not in seen:
        if cur == ancestor_id:
            return True
        seen.add(cur)
        row = db.execute("SELECT parent_id FROM tasks WHERE id=?", (cur,)).fetchone()
        cur = row["parent_id"] if row else None
    return False
