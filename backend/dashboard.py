"""Management-Dashboard: Portfolio-Ampel, Meilensteine, Risiken, Auslastung und (mit Kostenrecht) Budget über alle Projekte,
die der Benutzer sehen darf (Admins / „Betrachter alle Projekte“ alle, andere ihre eigenen).

Ampelregeln: siehe ``ampel.py`` (gemeinsam mit dem Portfolio-Report). Kurz:
  rot    = mindestens ein Vorgang plant sein Ende nach der gesetzten Frist, ODER mehr als 10 % der Vorgänge sind überfällig,
           ODER irgendetwas ist blockiert
  gelb   = nicht rot, aber mindestens ein Vorgang überfällig
  grün   = sonst;  „abgeschlossen“ = alle Vorgänge erledigt;  „leer“ = noch keine Vorgänge
Das Budget fließt nicht in die Ampel ein, wird aber daneben ausgewiesen (Überschreitung, CPI/SPI).
"""
from __future__ import annotations

import datetime as dt
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

import access
import finance_api
from ampel import OVERDUE_PCT, rag as _rag
import overview
import service as svc
from auth import current_user
from database import get_db

router = APIRouter(prefix="/api")
RULES = {"overdue_pct": OVERDUE_PCT, "milestone_days": 60, "risk_limit": 15}
ORDER = {"red": 0, "yellow": 1, "green": 2, "done": 3, "empty": 4}


def _today() -> date:
    return dt.date.today()


def _budget(db, user, pid: int) -> Optional[Dict[str, Any]]:
    if access.cost_level(db, user, pid) == "none":
        return None
    try:
        b = finance_api.get_budget(pid, None, user=user, db=db)
    except HTTPException:
        return None
    s = b["summary"]
    bud = s["budget"]
    if bud is None:
        parts = [r["budget"] for r in b["by_cost_center"] if r["budget"] is not None]
        bud = sum(parts) if parts else None
    return {"budget": bud, "plan": s["plan"], "ac": s["ac"], "eac": s["eac"], "cpi": s["cpi"], "spi": s["spi"],
            "over": bool(bud is not None and s["ac"] > bud + 0.005)}


@router.get("/dashboard")
def dashboard(user=Depends(current_user), db=Depends(get_db, scope="function")):
    today = _today()
    horizon = today + timedelta(days=RULES["milestone_days"])
    projects: List[Dict[str, Any]] = []
    milestones: List[Dict[str, Any]] = []
    risks: List[Dict[str, Any]] = []
    for row in db.execute("SELECT p.*, COALESCE(NULLIF(u.display_name, ''), u.username) AS owner_name FROM projects p LEFT JOIN users u ON u.id=p.owner_id ORDER BY p.name"):
        pid = row["id"]
        if not access.level_of(db, user, pid):
            continue
        try:
            _proj, trows, _d, res = svc.run_schedule(db, pid)
        except HTTPException:
            continue
        rows = {r["id"]: r for r in trows}
        names = {r["id"]: r["name"] for r in db.execute("SELECT id, name FROM resources WHERE project_id=?", (pid,))}
        who: Dict[int, List[str]] = {}
        for a in db.execute("SELECT a.task_id, a.resource_id FROM assignments a JOIN tasks t ON t.id=a.task_id WHERE t.project_id=?", (pid,)):
            who.setdefault(a["task_id"], []).append(names.get(a["resource_id"], "?"))
        leaves = [o for o in res.tasks.values() if not o.summary]
        total, done = len(leaves), 0
        overdue = blocked = missed = 0
        nxt: Optional[Dict[str, Any]] = None
        for o in leaves:
            r = rows[o.id]
            if r["status"] == "done":
                done += 1
                continue
            base = {"pid": pid, "project": row["name"], "task_id": o.id, "name": r["name"], "who": who.get(o.id, [])}
            late = (today - o.finish).days
            if late > 0:
                overdue += 1
            if r["status"] == "blocked":
                blocked += 1
                since = r["status_since"]
                risks.append(dict(base, kind="blocked", note=r["status_note"] or "",
                                  days=(today - date.fromisoformat(since[:10])).days if since else None))
            if r["deadline"] and o.finish.isoformat() > r["deadline"]:
                missed += 1
                risks.append(dict(base, kind="deadline", days=(o.finish - date.fromisoformat(r["deadline"])).days, date=r["deadline"]))
            elif late > 0:
                risks.append(dict(base, kind="overdue", days=late, date=o.finish.isoformat()))
            if o.duration == 0 and o.finish <= horizon:
                m = {"pid": pid, "project": row["name"], "task_id": o.id, "name": r["name"], "date": o.finish.isoformat(),
                     "late": late > 0, "critical": bool(o.critical)}
                milestones.append(m)
                if not nxt or m["date"] < nxt["date"]:
                    nxt = m
        rag = _rag(total, done, overdue, blocked, missed)
        projects.append({
            "id": pid, "name": row["name"], "owner": row["owner_name"], "finish": res.project_finish.isoformat() if res.project_finish else None,
            "tasks_total": total, "tasks_done": done, "percent": round(done * 100.0 / total) if total else 0,
            "overdue": overdue, "blocked": blocked, "deadline_missed": missed, "status": rag["status"], "reasons": rag["reasons"],
            "next_milestone": {"name": nxt["name"], "date": nxt["date"], "late": nxt["late"]} if nxt else None,
            "budget": _budget(db, user, pid),
        })
    projects.sort(key=lambda p: (ORDER[p["status"]], p["name"].lower()))
    milestones.sort(key=lambda m: (m["date"], m["project"].lower()))
    kind_order = {"deadline": 0, "blocked": 1, "overdue": 2}
    risks.sort(key=lambda r: (kind_order[r["kind"]], -(r["days"] or 0)))
    risk_counts = {k: sum(1 for r in risks if r["kind"] == k) for k in kind_order}

    ppl = overview.people(user=user, db=db)                     # Auslastung/Abwesenheit: gleiche Quelle wie „Wer arbeitet woran“
    over = sorted((p for p in ppl["people"] if p["over"]), key=lambda p: -p["peak"])
    absent = [p for p in ppl["people"] if p["absent_today"]]
    counts = {s: sum(1 for p in projects if p["status"] == s) for s in ORDER}
    active = [p for p in projects if p["status"] not in ("done", "empty")]
    cost = [p["budget"] for p in projects if p["budget"]]
    return {
        "today": today.isoformat(), "rules": RULES,
        "kpi": {"projects": len(projects), "status": counts, "overdue": sum(p["overdue"] for p in projects),
                "blocked": sum(p["blocked"] for p in projects), "deadline_missed": sum(p["deadline_missed"] for p in projects),
                "percent": round(sum(p["percent"] for p in active) / len(active)) if active else 0,
                "people": len(ppl["people"]), "people_over": len(over), "absent_today": len(absent)},
        "projects": projects,
        "milestones": milestones[:40],
        "risks": {"counts": risk_counts, "items": risks[:RULES["risk_limit"]]},
        "load": {"over": [{"name": p["name"], "peak": p["peak"], "capacity": p["capacity"], "load_now": p["load_now"],
                           "projects": len(p["projects"])} for p in over[:10]],
                 "absent": [{"name": p["name"], "until": (p["next_absence"] or {}).get("end"), "kind": (p["next_absence"] or {}).get("kind")} for p in absent[:15]]},
        "cost": ({"budget": sum(c["budget"] or 0 for c in cost), "ac": sum(c["ac"] for c in cost), "eac": sum(c["eac"] or 0 for c in cost),
                  "over": sum(1 for c in cost if c["over"]), "projects": len(cost)} if cost else None),
    }
