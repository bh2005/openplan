"""Externe Referenzen an Vorgängen (z. B. ServiceNow-Change, AWX-Job, Checkmk-Host) und Suche danach.

Je Vorgang und System genau eine Referenz (``PUT`` ersetzt, wiederholte Aufrufe sind unschädlich). Skripte finden Vorgänge über
``GET /projects/{pid}/lookup`` per Hostname oder Referenz und brauchen keine internen IDs.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

import access
import service as svc
from database import get_db

router = APIRouter(prefix="/api")
SYSTEM_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
_CTRL = re.compile(r"[\x00-\x1f\x7f]")


def _system(s: str) -> str:
    s = s.strip().lower()
    if not SYSTEM_RE.match(s):
        raise HTTPException(422, "System: 1–32 Zeichen aus a–z, 0–9, „-“ und „_“")
    return s


class RefIn(BaseModel):
    ref: str = Field(min_length=1, max_length=200)
    url: str = Field("", max_length=500)

    @field_validator("ref")
    @classmethod
    def _ref(cls, v: str) -> str:
        v = v.strip()
        if not v or _CTRL.search(v):
            raise ValueError("Referenz darf nicht leer sein und keine Steuerzeichen enthalten")
        return v

    @field_validator("url")
    @classmethod
    def _url(cls, v: str) -> str:
        v = v.strip()
        if v and not re.match(r"^https?://[^\s]+$", v, re.I):
            raise ValueError("Link muss mit http:// oder https:// beginnen")
        return v


def refs_of_project(db, pid: int) -> Dict[int, Dict[str, Dict[str, str]]]:
    """task_id -> {system: {ref, url}} für ein ganzes Projekt (für load_project)."""
    out: Dict[int, Dict[str, Dict[str, str]]] = {}
    for r in db.execute("SELECT e.task_id, e.system, e.ref, e.url FROM external_refs e JOIN tasks t ON t.id=e.task_id WHERE t.project_id=?", (pid,)):
        out.setdefault(r["task_id"], {})[r["system"]] = {"ref": r["ref"], "url": r["url"]}
    return out


def _pid(db, tid: int) -> int:
    return db.execute("SELECT project_id FROM tasks WHERE id=?", (tid,)).fetchone()["project_id"]


@router.get("/tasks/{tid}/refs")
def list_refs(tid: int, _=Depends(access.task("view")), db=Depends(get_db, scope="function")):
    return [dict(r) for r in db.execute("SELECT system, ref, url FROM external_refs WHERE task_id=? ORDER BY system", (tid,))]


@router.put("/tasks/{tid}/refs/{system}")
def put_ref(tid: int, system: str, body: RefIn, user=Depends(access.task("edit")), db=Depends(get_db, scope="function")):
    system = _system(system)
    old = db.execute("SELECT ref, url FROM external_refs WHERE task_id=? AND system=?", (tid, system)).fetchone()
    if old and old["ref"] == body.ref and old["url"] == body.url:
        return {"system": system, "ref": body.ref, "url": body.url, "changed": False}            # idempotent: nichts zu tun, keine Revision
    db.execute("INSERT INTO external_refs(task_id, system, ref, url) VALUES (?,?,?,?) "
               "ON CONFLICT(task_id, system) DO UPDATE SET ref=excluded.ref, url=excluded.url", (tid, system, body.ref, body.url))
    pid = _pid(db, tid)
    svc.log(db, pid, user, "Referenz gesetzt", "%s: %s" % (system, body.ref), tid)
    svc.bump(db, pid)
    return {"system": system, "ref": body.ref, "url": body.url, "changed": True}


@router.delete("/tasks/{tid}/refs/{system}")
def delete_ref(tid: int, system: str, user=Depends(access.task("edit")), db=Depends(get_db, scope="function")):
    system = _system(system)
    cur = db.execute("DELETE FROM external_refs WHERE task_id=? AND system=?", (tid, system))
    if cur.rowcount:
        pid = _pid(db, tid)
        svc.log(db, pid, user, "Referenz entfernt", system, tid)
        svc.bump(db, pid)
    return {"ok": True, "removed": bool(cur.rowcount)}


@router.get("/projects/{pid}/lookup")
def lookup(pid: int, hostname: Optional[str] = Query(None, max_length=200), ref: Optional[str] = Query(None, max_length=200),
           system: Optional[str] = Query(None, max_length=32), _=Depends(access.proj("view")), db=Depends(get_db, scope="function")):
    """Vorgänge per Hostname (Gerät samt Schritten) oder per externer Referenz finden. Mindestens ein Suchkriterium nötig.

    ``ref`` ohne ``system`` sucht in allen Systemen; mit ``system`` nur dort. Groß-/Kleinschreibung ist egal."""
    if not hostname and not ref:
        raise HTTPException(422, "hostname oder ref angeben")
    ids: List[int] = []
    if hostname:
        ids += [r["id"] for r in db.execute("SELECT id FROM tasks WHERE project_id=? AND lower(name)=lower(?) AND ext_key IS NOT NULL", (pid, hostname.strip()))]
    if ref:
        q, a = ("SELECT e.task_id FROM external_refs e JOIN tasks t ON t.id=e.task_id WHERE t.project_id=? AND lower(e.ref)=lower(?)", [pid, ref.strip()])
        if system:
            q, a = q + " AND e.system=?", a + [_system(system)]
        ids += [r["task_id"] for r in db.execute(q, a)]
    seen, items = set(), []
    for tid in ids:
        if tid in seen:
            continue
        seen.add(tid)
        items.append(_card(db, tid, with_steps=bool(hostname)))
    return {"items": items}


def _card(db, tid: int, with_steps: bool) -> Dict[str, Any]:
    t = db.execute("SELECT id, parent_id, name, status, percent, status_note, ext_key FROM tasks WHERE id=?", (tid,)).fetchone()
    d = {"id": t["id"], "parent_id": t["parent_id"], "name": t["name"], "status": t["status"], "percent": t["percent"], "status_note": t["status_note"],
         "device": t["ext_key"] is not None, "refs": {r["system"]: {"ref": r["ref"], "url": r["url"]} for r in
                                                      db.execute("SELECT system, ref, url FROM external_refs WHERE task_id=?", (tid,))}}
    if with_steps and d["device"]:
        d["steps"] = [{"id": s["id"], "name": s["name"], "status": s["status"], "percent": s["percent"],
                       "refs": {r["system"]: r["ref"] for r in db.execute("SELECT system, ref FROM external_refs WHERE task_id=?", (s["id"],))}}
                      for s in db.execute("SELECT id, name, status, percent FROM tasks WHERE parent_id=? ORDER BY position, id", (tid,))]
    return d
