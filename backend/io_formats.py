"""Import/Export: OpenPlan-JSON, CSV und MS-Project-XML (MSPDI).

Zwischenformat (``parsed``)::

    {name, description, start_date: date,
     tasks: [{uid, parent_uid, name, duration, percent, constraint_type, constraint_date, notes}],
     deps: [{pred_uid, succ_uid, type, lag}],
     resources: [{uid, name, max_units, cost_rate}],
     assignments: [{task_uid, res_uid, units}]}
"""
from __future__ import annotations

import csv
import io
import json
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime
from typing import Any, Dict, List, Optional

NS = "http://schemas.microsoft.com/project"
MIN_PER_DAY = 480

# MSPDI ConstraintType -> OpenPlan (alle übrigen werden zu ASAP)
_MSP_CONSTRAINT = {0: "ASAP", 2: "MSO", 4: "SNET", 7: "FNLT"}
_CONSTRAINT_MSP = {v: k for k, v in _MSP_CONSTRAINT.items()}
# MSPDI Link-Typ: 0=FF 1=FS 2=SF 3=SS
_MSP_LINK = {0: "FF", 1: "FS", 2: "SF", 3: "SS"}
_LINK_MSP = {v: k for k, v in _MSP_LINK.items()}


# ── JSON ────────────────────────────────────────────────────────────────────
def to_json(data: Dict[str, Any]) -> bytes:
    out = {"format": "openplan", "version": 1, **data}
    return json.dumps(out, ensure_ascii=False, indent=2).encode("utf-8")


def parse_json(raw: bytes) -> Dict[str, Any]:
    try:
        d = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError("kein gültiges JSON (%s)" % e)
    if d.get("format") != "openplan":
        raise ValueError("kein OpenPlan-Export")
    p = d["project"]
    tasks = []
    for t in d["tasks"]:
        tasks.append({
            "uid": t["id"], "parent_uid": t.get("parent_id"), "name": t["name"],
            "duration": int(t.get("duration") or 0), "percent": float(t.get("percent") or 0),
            "constraint_type": t.get("constraint_type") or "ASAP",
            "constraint_date": _pd(t.get("constraint_date")), "notes": t.get("notes") or ""})
    return {
        "name": p["name"], "description": p.get("description", ""),
        "start_date": date.fromisoformat(p["start_date"]),
        "work_days": p.get("work_days"), "holidays": p.get("holidays", []),
        "tasks": tasks,
        "deps": [{"pred_uid": x["pred_id"], "succ_uid": x["succ_id"], "type": x["type"], "lag": x["lag"]}
                 for x in d.get("deps", [])],
        "resources": [{"uid": r["id"], "name": r["name"], "max_units": r["max_units"],
                       "cost_rate": r["cost_rate"]} for r in d.get("resources", [])],
        "assignments": [{"task_uid": a["task_id"], "res_uid": a["resource_id"], "units": a["units"]}
                        for a in d.get("assignments", [])],
    }


def _pd(s: Optional[str]) -> Optional[date]:
    return date.fromisoformat(s[:10]) if s else None


# ── CSV ─────────────────────────────────────────────────────────────────────
def to_csv(data: Dict[str, Any]) -> bytes:
    wbs = {t["id"]: t["wbs"] for t in data["tasks"]}
    preds: Dict[int, List[str]] = {}
    for d in data["deps"]:
        lag = "%+d" % d["lag"] if d["lag"] else ""
        preds.setdefault(d["succ_id"], []).append("%s%s%s" % (wbs.get(d["pred_id"], "?"), d["type"], lag))
    rnames = {r["id"]: r["name"] for r in data["resources"]}
    ares: Dict[int, List[str]] = {}
    for a in data["assignments"]:
        ares.setdefault(a["task_id"], []).append(rnames.get(a["resource_id"], "?"))
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["PSP", "Name", "Dauer (AT)", "Start", "Ende", "% fertig", "Vorgänger", "Ressourcen",
                "Puffer (AT)", "Kritisch", "Sammelvorgang"])
    for t in data["tasks"]:
        w.writerow([t["wbs"], ("  " * t["level"]) + t["name"], t["duration"], t["start"], t["finish"],
                    t["percent"], ", ".join(preds.get(t["id"], [])), ", ".join(ares.get(t["id"], [])),
                    "" if t["total_float"] is None else t["total_float"],
                    "ja" if t["critical"] else "", "ja" if t["summary"] else ""])
    return buf.getvalue().encode("utf-8-sig")  # BOM, damit Excel UTF-8 erkennt


# ── MS Project XML ──────────────────────────────────────────────────────────
def _strip(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _child(el: ET.Element, name: str) -> Optional[str]:
    for c in el:
        if _strip(c.tag) == name:
            return (c.text or "").strip()
    return None


def _children(el: ET.Element, name: str) -> List[ET.Element]:
    return [c for c in el if _strip(c.tag) == name]


def _find(el: ET.Element, name: str) -> Optional[ET.Element]:
    r = _children(el, name)
    return r[0] if r else None


def _iso_duration_minutes(s: Optional[str]) -> int:
    if not s:
        return 0
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+(?:\.\d+)?)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?", s)
    if not m:
        return 0
    d, h, mi, sec = (float(x) if x else 0.0 for x in m.groups())
    return int(d * 24 * 60 + h * 60 + mi + sec / 60)


def parse_msp_xml(raw: bytes) -> Dict[str, Any]:
    try:
        # Entities/DTD werden von ElementTree nicht nachgeladen; trotzdem Größe oben begrenzt.
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        raise ValueError("XML ungültig (%s)" % e)
    if _strip(root.tag) != "Project":
        raise ValueError("kein MS-Project-XML (Wurzelelement Project fehlt)")
    mpd = int(_child(root, "MinutesPerDay") or MIN_PER_DAY) or MIN_PER_DAY
    name = _child(root, "Title") or _child(root, "Name") or "Importiertes Projekt"

    tasks: List[Dict[str, Any]] = []
    deps: List[Dict[str, Any]] = []
    stack: List[Dict[str, Any]] = []  # (outline level -> task)
    starts: List[date] = []
    tasks_el = _find(root, "Tasks")
    for te in (_children(tasks_el, "Task") if tasks_el is not None else []):
        uid = int(_child(te, "UID") or -1)
        if uid <= 0 and _child(te, "OutlineLevel") in (None, "0"):
            continue  # Projekt-Sammelvorgang (UID 0) überspringen
        if _child(te, "Active") == "0":
            continue
        level = int(_child(te, "OutlineLevel") or 1)
        while len(stack) >= level:
            stack.pop()
        parent = stack[-1]["uid"] if stack else None
        summary = _child(te, "Summary") == "1"
        milestone = _child(te, "Milestone") == "1"
        dur_days = 0 if milestone else max(round(_iso_duration_minutes(_child(te, "Duration")) / mpd), 0)
        if not milestone and not summary and dur_days == 0:
            dur_days = 1 if _child(te, "Duration") is None else 0
        ct = _MSP_CONSTRAINT.get(int(_child(te, "ConstraintType") or 0), "ASAP")
        cd = _pd(_child(te, "ConstraintDate"))
        if ct != "ASAP" and not cd:
            ct = "ASAP"
        st = _pd(_child(te, "Start"))
        if st and not summary:
            starts.append(st)
        t = {"uid": uid, "parent_uid": parent, "name": _child(te, "Name") or "(ohne Name)",
             "duration": dur_days, "percent": float(_child(te, "PercentComplete") or 0),
             "constraint_type": ct, "constraint_date": cd, "notes": _child(te, "Notes") or ""}
        tasks.append(t)
        stack.append(t)
        for pl in _children(te, "PredecessorLink"):
            lag_min = int(_child(pl, "LinkLag") or 0) / 10.0  # Zehntelminuten
            deps.append({"pred_uid": int(_child(pl, "PredecessorUID") or -1), "succ_uid": uid,
                         "type": _MSP_LINK.get(int(_child(pl, "Type") or 1), "FS"),
                         "lag": int(round(lag_min / mpd))})

    resources, assignments = [], []
    res_el = _find(root, "Resources")
    for re_ in (_children(res_el, "Resource") if res_el is not None else []):
        uid = int(_child(re_, "UID") or -1)
        if uid <= 0 or not _child(re_, "Name"):
            continue
        resources.append({"uid": uid, "name": _child(re_, "Name"),
                          "max_units": float(_child(re_, "MaxUnits") or 1) * 100,
                          "cost_rate": 0.0})
    as_el = _find(root, "Assignments")
    for ae in (_children(as_el, "Assignment") if as_el is not None else []):
        tu, ru = int(_child(ae, "TaskUID") or -1), int(_child(ae, "ResourceUID") or -1)
        if tu > 0 and ru > 0:
            assignments.append({"task_uid": tu, "res_uid": ru,
                                "units": float(_child(ae, "Units") or 1) * 100})

    start = _pd(_child(root, "StartDate")) or (min(starts) if starts else date.today())
    return {"name": name, "description": "", "start_date": start, "work_days": None, "holidays": [],
            "tasks": tasks, "deps": deps, "resources": resources, "assignments": assignments}


def to_msp_xml(data: Dict[str, Any]) -> bytes:
    ET.register_namespace("", NS)
    p = data["project"]

    def el(parent, tag, text=None):
        e = ET.SubElement(parent, "{%s}%s" % (NS, tag))
        if text is not None:
            e.text = str(text)
        return e

    def dur(days):  # Arbeitstage -> ISO-8601 (8h/Tag)
        return "PT%dH0M0S" % (days * MIN_PER_DAY // 60)

    root = ET.Element("{%s}Project" % NS)
    el(root, "Name", p["name"])
    el(root, "Title", p["name"])
    el(root, "StartDate", "%sT08:00:00" % p["start_date"])
    if p.get("finish"):
        el(root, "FinishDate", "%sT17:00:00" % p["finish"])
    el(root, "MinutesPerDay", MIN_PER_DAY)
    el(root, "MinutesPerWeek", MIN_PER_DAY * 5)
    el(root, "DaysPerMonth", 20)
    el(root, "ScheduleFromStart", 1)
    el(root, "DefaultStartTime", "08:00:00")
    el(root, "DefaultFinishTime", "17:00:00")

    uid_of = {t["id"]: t["id"] for t in data["tasks"]}
    tasks_el = el(root, "Tasks")
    pr = el(tasks_el, "Task")  # Projekt-Sammelvorgang UID 0
    for k, v in (("UID", 0), ("ID", 0), ("Name", p["name"]), ("OutlineLevel", 0), ("Summary", 1)):
        el(pr, k, v)
    preds: Dict[int, List[Dict[str, Any]]] = {}
    for d in data["deps"]:
        preds.setdefault(d["succ_id"], []).append(d)
    for i, t in enumerate(data["tasks"], 1):
        te = el(tasks_el, "Task")
        el(te, "UID", t["id"])
        el(te, "ID", i)
        el(te, "Name", t["name"])
        el(te, "Active", 1)
        el(te, "OutlineNumber", t["wbs"])
        el(te, "OutlineLevel", t["level"] + 1)
        el(te, "Summary", 1 if t["summary"] else 0)
        el(te, "Milestone", 1 if t["milestone"] else 0)
        el(te, "Start", "%sT08:00:00" % t["start"])
        el(te, "Finish", "%sT17:00:00" % t["finish"])
        el(te, "Duration", dur(t["duration"]))
        el(te, "PercentComplete", int(round(t["percent"])))
        el(te, "ConstraintType", _CONSTRAINT_MSP.get(t["constraint_type"], 0))
        if t["constraint_date"]:
            el(te, "ConstraintDate", "%sT08:00:00" % t["constraint_date"])
        if t["notes"]:
            el(te, "Notes", t["notes"])
        for d in preds.get(t["id"], []):
            pl = el(te, "PredecessorLink")
            el(pl, "PredecessorUID", uid_of[d["pred_id"]])
            el(pl, "Type", _LINK_MSP[d["type"]])
            el(pl, "LinkLag", d["lag"] * MIN_PER_DAY * 10)
            el(pl, "LagFormat", 7)  # Tage
    res_el = el(root, "Resources")
    for r in data["resources"]:
        re_ = el(res_el, "Resource")
        el(re_, "UID", r["id"])
        el(re_, "ID", r["id"])
        el(re_, "Name", r["name"])
        el(re_, "Type", 1)
        el(re_, "MaxUnits", r["max_units"] / 100.0)
    as_el = el(root, "Assignments")
    for n, a in enumerate(data["assignments"], 1):
        ae = el(as_el, "Assignment")
        el(ae, "UID", n)
        el(ae, "TaskUID", a["task_id"])
        el(ae, "ResourceUID", a["resource_id"])
        el(ae, "Units", a["units"] / 100.0)
    ET.indent(root) if hasattr(ET, "indent") else None
    return b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + ET.tostring(root, encoding="utf-8")


# ── Persistenz des Imports ──────────────────────────────────────────────────
def store_import(db, parsed: Dict[str, Any], owner_id: int) -> int:
    wd = parsed.get("work_days")
    wd_s = ",".join(map(str, wd)) if wd else "0,1,2,3,4"
    hol = ",".join(str(h) for h in parsed.get("holidays") or [])
    cur = db.execute("INSERT INTO projects(name, description, start_date, work_days, holidays, owner_id) "
                     "VALUES (?,?,?,?,?,?)",
                     (parsed["name"][:200], parsed.get("description", ""),
                      parsed["start_date"].isoformat(), wd_s, hol, owner_id))
    pid = cur.lastrowid
    known = {t["uid"] for t in parsed["tasks"]}
    idmap: Dict[Any, int] = {}
    counters: Dict[Any, int] = {}
    pending = list(parsed["tasks"])
    # Elternvorgänge zuerst: Aufträge stehen bei MSP in Outline-Reihenfolge, JSON evtl. nicht
    guard = 0
    while pending and guard < len(parsed["tasks"]) + 5:
        guard += 1
        rest = []
        for t in pending:
            pu = t["parent_uid"] if t["parent_uid"] in known else None
            if pu is not None and pu not in idmap:
                rest.append(t)
                continue
            pos = counters.get(pu, 0)
            counters[pu] = pos + 1
            c = db.execute(
                "INSERT INTO tasks(project_id, parent_id, position, name, duration, percent, constraint_type, "
                "constraint_date, notes, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (pid, idmap.get(pu), pos, t["name"][:300], max(t["duration"], 0), min(max(t["percent"], 0), 100),
                 t["constraint_type"], t["constraint_date"].isoformat() if t["constraint_date"] else None,
                 t["notes"], "done" if t["percent"] >= 100 else "in_progress" if t["percent"] > 0 else "open"))
            idmap[t["uid"]] = c.lastrowid
        pending = rest
    if pending:
        raise ValueError("Vorgangshierarchie nicht auflösbar")
    seen = set()
    for d in parsed["deps"]:
        a, b = idmap.get(d["pred_uid"]), idmap.get(d["succ_uid"])
        if a and b and a != b and (a, b) not in seen:
            seen.add((a, b))
            db.execute("INSERT INTO deps(project_id, pred_id, succ_id, type, lag) VALUES (?,?,?,?,?)",
                       (pid, a, b, d["type"], d["lag"]))
    rmap = {}
    for r in parsed["resources"]:
        c = db.execute("INSERT INTO resources(project_id, name, max_units, cost_rate) VALUES (?,?,?,?)",
                       (pid, r["name"][:200], r["max_units"], r["cost_rate"]))
        rmap[r["uid"]] = c.lastrowid
    for a in parsed["assignments"]:
        t_id, r_id = idmap.get(a["task_uid"]), rmap.get(a["res_uid"])
        if t_id and r_id:
            db.execute("INSERT OR REPLACE INTO assignments(task_id, resource_id, units) VALUES (?,?,?)",
                       (t_id, r_id, a["units"]))
    return pid
