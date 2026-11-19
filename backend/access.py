"""Projektbezogene Zugriffsrechte.

Stufen: view (1) < work (2) < edit (3) < owner (4).

* ``owner`` – Projekt-Verantwortlicher (und globale Admins).
* ``edit`` – Mitglied mit Rolle Editor: plant.
* ``view`` – Mitglied mit Rolle Leser.
* ``work`` („Mitarbeiter“) – ergibt sich **automatisch aus der Zuordnung**: Wer über seine verknüpfte Ressource einem Vorgang des Projekts
  zugeordnet ist, sieht das Projekt und darf an *seinen* Vorgängen Status/Fortschritt/Notiz, Kommentare und Dokumente pflegen sowie Pool-Pakete
  übernehmen – aber nicht planen. Wird die Zuordnung entfernt, entfällt der Zugriff wieder.

Die globale Rolle ``viewer`` deckelt jede Projektrolle auf ``view``. Ein ``viewer`` mit Flag ``see_all`` („Betrachter alle Projekte“)
sieht zusätzlich alle Projekte lesend (Kosten nur, wenn das Projekt sie für Mitglieder freigibt).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException

from auth import current_user
from database import get_db

LEVELS = {"view": 1, "work": 2, "edit": 3, "owner": 4}
NAMES = {1: "view", 2: "work", 3: "edit", 4: "owner"}
NEED_TEXT = {"work": "Mitarbeiter", "edit": "Bearbeiter", "owner": "Projekt-Verantwortlicher"}


def is_assigned(db, user_id: int, tid: int) -> bool:
    """Ist der Benutzer über eine mit ihm verknüpfte Ressource diesem Vorgang zugeordnet?"""
    return db.execute("SELECT 1 FROM assignments a JOIN resources r ON r.id=a.resource_id WHERE a.task_id=? AND r.user_id=? LIMIT 1",
                      (tid, user_id)).fetchone() is not None


def level_of(db, user: Dict[str, Any], pid: int) -> int:
    if user["role"] == "admin":
        return 4
    tok = user.get("token")
    if tok and tok["projects"] and pid not in tok["projects"]:       # API-Token auf bestimmte Projekte beschränkt
        return 0
    row = db.execute("SELECT owner_id FROM projects WHERE id=?", (pid,)).fetchone()
    if not row:
        return 0
    lvl = 0
    if row["owner_id"] == user["id"]:
        lvl = 4
    else:
        m = db.execute("SELECT role FROM project_members WHERE project_id=? AND user_id=?", (pid, user["id"])).fetchone()
        if m:
            lvl = 3 if m["role"] == "editor" else 1
        if lvl < 2 and db.execute("SELECT 1 FROM assignments a JOIN resources r ON r.id=a.resource_id JOIN tasks t ON t.id=a.task_id "
                                  "WHERE t.project_id=? AND r.user_id=? LIMIT 1", (pid, user["id"])).fetchone():
            lvl = 2
    if user["role"] == "viewer":
        lvl = min(lvl, 1)
        if user.get("see_all"):
            lvl = 1
    return lvl


def check(db, user: Dict[str, Any], pid: Optional[int], need: str) -> None:
    if pid is None or not db.execute("SELECT 1 FROM projects WHERE id=?", (pid,)).fetchone():
        raise HTTPException(404, "Projekt nicht gefunden")
    lvl = level_of(db, user, pid)
    if lvl == 0:
        raise HTTPException(404, "Projekt nicht gefunden")  # Existenz nicht verraten
    if lvl < LEVELS[need]:
        raise HTTPException(403, "Keine Berechtigung (benötigt: %s)" % NEED_TEXT.get(need, need))


def access_name(db, user: Dict[str, Any], pid: int) -> str:
    return NAMES.get(level_of(db, user, pid), "none")


def cost_level(db, user: Dict[str, Any], pid: int) -> str:
    """'edit' = Verantwortlicher/Admin, 'view' = Mitglied bei freigegebenen Kosten, sonst 'none'."""
    lvl = level_of(db, user, pid)
    if lvl >= 4:
        return "edit"
    row = db.execute("SELECT members_see_costs FROM projects WHERE id=?", (pid,)).fetchone()
    return "view" if lvl >= 1 and row and row["members_see_costs"] else "none"


def costs(need: str):
    def dep(pid: int, user=Depends(current_user), db=Depends(get_db, scope="function")):
        check(db, user, pid, "view")
        have = cost_level(db, user, pid)
        if have == "none" or (need == "edit" and have != "edit"):
            raise HTTPException(403, "Keine Berechtigung für Kosten/Budget")
        return user
    return dep


def proj(need: str):
    def dep(pid: int, user=Depends(current_user), db=Depends(get_db, scope="function")):
        check(db, user, pid, need)
        return user
    return dep


def task(need: str):
    def dep(tid: int, user=Depends(current_user), db=Depends(get_db, scope="function")):
        row = db.execute("SELECT project_id FROM tasks WHERE id=?", (tid,)).fetchone()
        check(db, user, row["project_id"] if row else None, need)
        return user
    return dep


def task_own():
    """Bearbeiter/Verantwortliche an jedem Vorgang, Mitarbeiter nur an Vorgängen, denen sie zugeordnet sind."""
    def dep(tid: int, user=Depends(current_user), db=Depends(get_db, scope="function")):
        row = db.execute("SELECT project_id FROM tasks WHERE id=?", (tid,)).fetchone()
        pid = row["project_id"] if row else None
        check(db, user, pid, "work")
        if level_of(db, user, pid) < 3 and not is_assigned(db, user["id"], tid):
            raise HTTPException(403, "Keine Berechtigung (benötigt: Bearbeiter oder Zuordnung zu diesem Vorgang)")
        return user
    return dep


def absence_own():
    """Bearbeiter/Verantwortliche an jeder Abwesenheit, Mitarbeiter nur an denen ihrer eigenen Ressource."""
    def dep(aid: int, user=Depends(current_user), db=Depends(get_db, scope="function")):
        row = db.execute("SELECT a.project_id, r.user_id FROM absences a JOIN resources r ON r.id=a.resource_id WHERE a.id=?", (aid,)).fetchone()
        pid = row["project_id"] if row else None
        check(db, user, pid, "work")
        if level_of(db, user, pid) < 3 and row["user_id"] != user["id"]:
            raise HTTPException(403, "Keine Berechtigung (benötigt: Bearbeiter oder eigene Abwesenheit)")
        return user
    return dep


def resource(need: str):
    def dep(rid: int, user=Depends(current_user), db=Depends(get_db, scope="function")):
        row = db.execute("SELECT project_id FROM resources WHERE id=?", (rid,)).fetchone()
        check(db, user, row["project_id"] if row else None, need)
        return user
    return dep
