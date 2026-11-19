"""Persönliche Abwesenheiten (Urlaub, Schulung …): einmal je Benutzer eintragen, gelten in allen Projekten,
in denen der Benutzer als Ressource (``resources.user_id``) geführt wird.

In den Projekten erscheinen sie als Abwesenheiten mit ``source='user'`` und negativer ``id`` (``-id``), damit sie sich
nicht mit den projektbezogenen Abwesenheiten (Tabelle ``absences``) überschneiden. Datenschutz: andere Benutzer sehen
„Krank“ nur als „Sonstiges“ und keine Notiz.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

import service as svc
from auth import current_user
from database import get_db
from schemas import AbsenceIn

router = APIRouter(prefix="/api/me")


def project_absences(db, pid: int, viewer: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Persönliche Abwesenheiten der Ressourcen des Projekts, als Projekt-Abwesenheiten (je verknüpfter Ressource)."""
    out = []
    for r in db.execute(
            "SELECT ua.id, ua.user_id, ua.start_date, ua.end_date, ua.kind, ua.note, r.id AS resource_id "
            "FROM user_absences ua JOIN resources r ON r.user_id=ua.user_id WHERE r.project_id=? "
            "ORDER BY ua.start_date, ua.id", (pid,)):
        own = bool(viewer) and viewer["id"] == r["user_id"]
        out.append({"id": -r["id"], "resource_id": r["resource_id"], "start_date": r["start_date"], "end_date": r["end_date"],
                    "kind": r["kind"] if own or r["kind"] != "sick" else "other", "note": r["note"] if own else "",
                    "source": "user"})
    return out


def _check(body: AbsenceIn) -> None:
    if body.end_date < body.start_date:
        raise HTTPException(422, "Das Ende liegt vor dem Beginn")
    if (body.end_date - body.start_date).days > 400:
        raise HTTPException(422, "Eine Abwesenheit darf höchstens 400 Tage dauern")


def _bump_projects(db, uid: int) -> None:
    """Live-Update: alle Projekte, in denen der Benutzer eine Ressource ist, bekommen eine neue Revision."""
    for r in db.execute("SELECT DISTINCT project_id FROM resources WHERE user_id=?", (uid,)).fetchall():
        svc.bump(db, r["project_id"])


def _list(db, uid: int) -> List[Dict[str, Any]]:
    return [dict(r) for r in db.execute(
        "SELECT id, start_date, end_date, kind, note FROM user_absences WHERE user_id=? ORDER BY start_date, id", (uid,))]


@router.get("/absences")
def list_mine(user=Depends(current_user), db=Depends(get_db, scope="function")):
    return _list(db, user["id"])


@router.post("/absences", status_code=201)
def create_mine(body: AbsenceIn, user=Depends(current_user), db=Depends(get_db, scope="function")):
    _check(body)
    db.execute("INSERT INTO user_absences(user_id, start_date, end_date, kind, note) VALUES (?,?,?,?,?)",
               (user["id"], body.start_date.isoformat(), body.end_date.isoformat(), body.kind, body.note.strip()))
    _bump_projects(db, user["id"])
    return _list(db, user["id"])


def _own(db, aid: int, uid: int):
    row = db.execute("SELECT * FROM user_absences WHERE id=? AND user_id=?", (aid, uid)).fetchone()
    if not row:
        raise HTTPException(404, "Abwesenheit nicht gefunden")
    return row


@router.put("/absences/{aid}")
def update_mine(aid: int, body: AbsenceIn, user=Depends(current_user), db=Depends(get_db, scope="function")):
    _own(db, aid, user["id"])
    _check(body)
    db.execute("UPDATE user_absences SET start_date=?, end_date=?, kind=?, note=? WHERE id=?",
               (body.start_date.isoformat(), body.end_date.isoformat(), body.kind, body.note.strip(), aid))
    _bump_projects(db, user["id"])
    return _list(db, user["id"])


@router.delete("/absences/{aid}")
def delete_mine(aid: int, user=Depends(current_user), db=Depends(get_db, scope="function")):
    _own(db, aid, user["id"])
    db.execute("DELETE FROM user_absences WHERE id=?", (aid,))
    _bump_projects(db, user["id"])
    return _list(db, user["id"])
