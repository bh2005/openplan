"""Übersicht „Wer arbeitet woran“ für Vorgesetzte: Personen über alle für den Benutzer sichtbaren Projekte.

Sichtbar sind genau die Projekte, die der Benutzer auch in der Projektliste sieht (Admins und „Betrachter alle
Projekte“ also alle). Eine Person ist ein Benutzer (über ``resources.user_id``, Verantwortliche und Mitglieder) oder – ohne
Konto – eine Ressource mit gleichem Namen. Kosten kommen hier nicht vor. „Krank“ wird für andere als „Sonstiges“ gezeigt.
"""
from __future__ import annotations

import datetime as dt
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

import access
import cpm
import service as svc
from auth import current_user
from database import get_db

router = APIRouter(prefix="/api/overview")
HORIZON = 30            # Tage Vorschau für Spitzenlast und Abwesenheiten


def _today() -> date:
    return dt.date.today()


def _kind(kind: str, own: bool) -> str:
    return "other" if kind == "sick" and not own else kind


@router.get("/people")
def people(user=Depends(current_user), db=Depends(get_db, scope="function")):
    today = _today()
    days = [today + timedelta(days=i) for i in range(HORIZON)]
    persons: Dict[str, Dict[str, Any]] = {}
    projects: List[Dict[str, Any]] = []
    users = {u["id"]: u["display_name"] or u["username"] for u in db.execute("SELECT id, username, display_name FROM users")}
    user_abs: Dict[int, List[Any]] = {}
    for a in db.execute("SELECT user_id, start_date, end_date, kind FROM user_absences ORDER BY start_date"):
        user_abs.setdefault(a["user_id"], []).append(a)

    def person(key: str, name: str, uid: Optional[int]) -> Dict[str, Any]:
        p = persons.get(key)
        if not p:
            p = persons[key] = {"key": key, "name": name, "user_id": uid, "capacity": 0.0, "load": [0.0] * HORIZON,
                                "ranges": [], "projects": {}}
            for a in user_abs.get(uid, []) if uid else []:
                p["ranges"].append((a["start_date"], a["end_date"], _kind(a["kind"], user["id"] == uid)))
        return p

    def slot(p: Dict[str, Any], proj: Dict[str, Any]) -> Dict[str, Any]:
        return p["projects"].setdefault(proj["id"], {"pid": proj["id"], "name": proj["name"], "roles": [], "tasks_open": 0,
                                                     "tasks_blocked": 0, "tasks_overdue": 0, "load_now": 0.0, "until": None, "funktion": ""})

    for row in db.execute("SELECT p.*, COALESCE(NULLIF(u.display_name, ''), u.username) AS owner_name FROM projects p LEFT JOIN users u ON u.id=p.owner_id ORDER BY p.name"):
        pid = row["id"]
        if not access.level_of(db, user, pid):
            continue
        try:
            proj, trows, _d, res = svc.run_schedule(db, pid)
        except HTTPException:                      # Zyklus im Plan: Projekt überspringen statt die Übersicht zu sprengen
            continue
        cal = cpm.Calendar(date.fromisoformat(proj["start_date"]), svc.parse_days(proj["work_days"]), svc.parse_holidays(proj["holidays"]))
        info = {"id": pid, "name": row["name"], "owner_id": row["owner_id"], "owner": row["owner_name"],
                "finish": res.project_finish.isoformat() if res.project_finish else None, "people": {}}
        rows = {r["id"]: r for r in trows}
        leaves = [o for o in res.tasks.values() if not o.summary]
        info["tasks_total"] = len(leaves)
        info["tasks_done"] = sum(1 for o in leaves if rows[o.id]["status"] == "done")
        info["tasks_blocked"] = sum(1 for o in leaves if rows[o.id]["status"] == "blocked")
        info["tasks_overdue"] = sum(1 for o in leaves if rows[o.id]["status"] != "done" and o.finish < today)

        def add_role(p, role):
            s = slot(p, info)
            if role not in s["roles"]:
                s["roles"].append(role)
            info["people"][p["key"]] = s
            return s

        if row["owner_id"]:
            add_role(person("u%d" % row["owner_id"], users.get(row["owner_id"], "?"), row["owner_id"]), "lead")
        for m in db.execute("SELECT user_id FROM project_members WHERE project_id=?", (pid,)):
            add_role(person("u%d" % m["user_id"], users.get(m["user_id"], "?"), m["user_id"]), "member")

        res_abs: Dict[int, List[Any]] = {}
        for a in db.execute("SELECT resource_id, start_date, end_date, kind FROM absences WHERE project_id=?", (pid,)):
            res_abs.setdefault(a["resource_id"], []).append(a)
        resources = {r["id"]: r for r in db.execute("SELECT * FROM resources WHERE project_id=?", (pid,))}
        owner_of: Dict[int, Dict[str, Any]] = {}
        for rid, r in resources.items():
            p = person("u%d" % r["user_id"], users.get(r["user_id"], r["name"]), r["user_id"]) if r["user_id"] else \
                person("n:" + r["name"].strip().lower(), r["name"], None)
            owner_of[rid] = p
            p["capacity"] = max(p["capacity"], float(r["max_units"]))
            for a in res_abs.get(rid, []):
                p["ranges"].append((a["start_date"], a["end_date"], _kind(a["kind"], user["id"] == p["user_id"])))
            s = add_role(p, "assigned")
            if r["funktion"]:
                s["funktion"] = r["funktion"]
        for a in db.execute("SELECT a.* FROM assignments a JOIN tasks t ON t.id=a.task_id WHERE t.project_id=?", (pid,)):
            o = res.tasks.get(a["task_id"])
            if not o or o.summary or o.duration <= 0 or rows[a["task_id"]]["status"] == "done" or a["resource_id"] not in owner_of:
                continue
            p, s = owner_of[a["resource_id"]], info["people"][owner_of[a["resource_id"]]["key"]]
            s["tasks_open"] += 1
            s["tasks_blocked"] += rows[a["task_id"]]["status"] == "blocked"
            s["tasks_overdue"] += o.finish < today
            fin = o.finish.isoformat()
            s["until"] = fin if not s["until"] or fin > s["until"] else s["until"]
            for i, d in enumerate(days):
                if o.start <= d <= o.finish and cal.is_working(d):
                    p["load"][i] += a["units"]
                    if i == 0:
                        s["load_now"] += a["units"]
        projects.append(info)

    out_people = []
    for p in persons.values():
        absent = [i for i, d in enumerate(days) if any(s <= d.isoformat() <= e for s, e, _k in p["ranges"])]
        cap = p["capacity"] or (100.0 if p["projects"] else 0.0)
        nxt = sorted((r for r in p["ranges"] if r[1] >= today.isoformat()), key=lambda r: r[0])
        peak = max(p["load"])
        out_people.append({
            "key": p["key"], "name": p["name"], "user_id": p["user_id"], "capacity": cap,
            "load_now": p["load"][0], "peak": peak,
            "over": any(v > (0 if i in absent else cap) for i, v in enumerate(p["load"]) if v > 0) if cap else False,
            "absent_today": 0 in absent,
            "next_absence": {"start": nxt[0][0], "end": nxt[0][1], "kind": nxt[0][2]} if nxt else None,
            "projects": sorted(p["projects"].values(), key=lambda s: s["name"].lower()),
        })
    out_people.sort(key=lambda x: x["name"].lower())
    for info in projects:
        info["people"] = sorted(({**v, "key": k, "name": persons[k]["name"]} for k, v in info["people"].items()), key=lambda x: x["name"].lower())
    return {"today": today.isoformat(), "people": out_people, "projects": projects}
