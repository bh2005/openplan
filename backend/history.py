"""Rückgängig/Wiederholen für Planänderungen (Vorgänge, Abhängigkeiten, Ressourcen, Zuordnungen, Basisplan).

Vor jeder Änderung wird ein Snapshot dieser Tabellen im Speicher gehalten; hat die Anfrage den Plan tatsächlich
verändert (Revision gestiegen), landet er auf dem Undo-Stapel (``undo_stack``). Die Wiederherstellung arbeitet
diff-basiert (Upsert + Löschen nicht mehr vorhandener Zeilen), damit Kaskaden keine Dokumente/Buchungen löschen.
Nicht enthalten: Projekteinstellungen, Budget/Ist-Kosten, Dateien.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from fastapi import Depends, Request

from database import get_db

MAX_UNDO = 20
SCOPES = re.compile(r"^/api/(?:(?:tasks|resources|absences)/\d+|projects/\d+/(?:tasks|resources|absences|baseline|devices|leveling))")

# (Tabelle, Schlüsselspalten, Auswahl der Projektzeilen)
TABLES = [
    ("tasks", ("id",), "SELECT * FROM tasks WHERE project_id=?"),
    ("resources", ("id",), "SELECT * FROM resources WHERE project_id=?"),
    ("absences", ("id",), "SELECT * FROM absences WHERE project_id=?"),
    ("deps", ("id",), "SELECT * FROM deps WHERE project_id=?"),
    ("assignments", ("task_id", "resource_id"),
     "SELECT a.* FROM assignments a JOIN tasks t ON t.id=a.task_id WHERE t.project_id=?"),
    ("cost_items", ("id",), "SELECT * FROM cost_items WHERE project_id=?"),
]


def snapshot(db, pid: int) -> Dict[str, List[Dict[str, Any]]]:
    return {t: [dict(r) for r in db.execute(sql, (pid,)).fetchall()] for t, _k, sql in TABLES}


def restore(db, pid: int, snap: Dict[str, List[Dict[str, Any]]]) -> None:
    db.execute("PRAGMA defer_foreign_keys=ON")
    keyf = lambda row, keys: tuple(row[k] for k in keys)  # noqa: E731
    for table, keys, sql in reversed(TABLES):                       # erst überzählige Zeilen entfernen
        keep = {keyf(r, keys) for r in snap.get(table, [])}
        for r in db.execute(sql, (pid,)).fetchall():
            if keyf(r, keys) not in keep:
                db.execute("DELETE FROM %s WHERE %s" % (table, " AND ".join("%s=?" % k for k in keys)), keyf(r, keys))
    for table, keys, _sql in TABLES:                                # dann Upsert
        for r in snap.get(table, []):
            cols = list(r.keys())
            upd = [c for c in cols if c not in keys]
            conflict = "ON CONFLICT(%s) DO %s" % (",".join(keys), ("UPDATE SET " + ",".join("%s=excluded.%s" % (c, c) for c in upd)) if upd else "NOTHING")
            db.execute("INSERT INTO %s(%s) VALUES (%s) %s" % (table, ",".join(cols), ",".join("?" * len(cols)), conflict),
                       [r[c] for c in cols])


def _push(db, pid: int, kind: str, label: str, username: str, snap: Dict[str, Any]) -> None:
    db.execute("INSERT INTO undo_stack(project_id, kind, label, username, snapshot) VALUES (?,?,?,?,?)",
               (pid, kind, label[:120], username, json.dumps(snap)))


def _project_of(db, params: Dict[str, Any]) -> Optional[int]:
    if "pid" in params:
        return int(params["pid"])
    for key, table in (("tid", "tasks"), ("rid", "resources"), ("aid", "absences")):
        if key in params:
            row = db.execute("SELECT project_id FROM %s WHERE id=?" % table, (int(params[key]),)).fetchone()
            return row["project_id"] if row else None
    return None


_PENDING: Dict[int, Dict[str, Any]] = {}      # offene Snapshots je DB-Verbindung (= je Anfrage)


def finalize(db) -> None:
    """Snapshot ablegen, falls die laufende Anfrage den Plan verändert hat. Idempotent; wird vor dem Bauen der
    Antwort (``state``) und nach dem Handler aufgerufen, damit die Antwort schon den aktuellen Stapel enthält."""
    p = _PENDING.get(id(db))
    if not p or p["done"]:
        return
    pid = p["pid"]
    rev1 = db.execute("SELECT revision FROM projects WHERE id=?", (pid,)).fetchone()
    if not rev1 or rev1["revision"] == p["rev0"]:
        return
    p["done"] = True
    j = db.execute("SELECT action, detail, username FROM journal WHERE project_id=? AND id>? ORDER BY id DESC LIMIT 1",
                   (pid, p["j0"])).fetchone()
    label = ("%s: %s" % (j["action"], j["detail"]) if j and j["detail"] else (j["action"] if j else "Änderung"))
    _push(db, pid, "undo", label, j["username"] if j else "", p["before"])
    db.execute("DELETE FROM undo_stack WHERE project_id=? AND kind='redo'", (pid,))
    db.execute("DELETE FROM undo_stack WHERE project_id=? AND kind='undo' AND id NOT IN "
               "(SELECT id FROM undo_stack WHERE project_id=? AND kind='undo' ORDER BY id DESC LIMIT ?)", (pid, pid, MAX_UNDO))


def record(request: Request, db=Depends(get_db, scope="function")):
    """Router-Abhängigkeit: Snapshot vor der Änderung, Ablage nur bei Erfolg und echter Änderung."""
    pid = None
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and SCOPES.match(request.url.path):
        pid = _project_of(db, request.scope.get("path_params", {}))
    if pid is None:
        yield
        return
    rev0 = db.execute("SELECT revision FROM projects WHERE id=?", (pid,)).fetchone()
    j0 = db.execute("SELECT COALESCE(MAX(id),0) FROM journal WHERE project_id=?", (pid,)).fetchone()[0]
    _PENDING[id(db)] = {"pid": pid, "rev0": rev0["revision"] if rev0 else None, "j0": j0, "done": False,
                        "before": snapshot(db, pid)}
    try:
        yield                                                      # Exceptions laufen hier durch -> nichts gespeichert
        finalize(db)
    finally:
        _PENDING.pop(id(db), None)


def state(db, pid: int) -> Dict[str, Any]:
    finalize(db)
    out: Dict[str, Any] = {}
    for kind in ("undo", "redo"):
        r = db.execute("SELECT label, username FROM undo_stack WHERE project_id=? AND kind=? ORDER BY id DESC LIMIT 1",
                       (pid, kind)).fetchone()
        out[kind] = {"label": r["label"], "username": r["username"]} if r else None
    return out


def step(db, pid: int, kind: str) -> Dict[str, Any]:
    """Letzten Eintrag von ``kind`` ('undo'/'redo') anwenden; der Gegenstapel erhält den aktuellen Stand."""
    row = db.execute("SELECT * FROM undo_stack WHERE project_id=? AND kind=? ORDER BY id DESC LIMIT 1", (pid, kind)).fetchone()
    return dict(row) if row else {}


def apply(db, pid: int, row: Dict[str, Any], opposite: str, username: str) -> None:
    _push(db, pid, opposite, row["label"], row["username"], snapshot(db, pid))
    restore(db, pid, json.loads(row["snapshot"]))
    db.execute("DELETE FROM undo_stack WHERE id=?", (row["id"],))
