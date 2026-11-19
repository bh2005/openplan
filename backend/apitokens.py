"""Verwaltung der API-Tokens (Dienstkonten) – nur für Administratoren.

Ein Token gehört zu einem Dienstkonto (``users.auth_source='service'``, kein Passwort-Login, nie Admin). Rollen, Projektrechte und Audit
gelten damit unverändert. Der Klartext wird nur beim Anlegen ausgegeben, gespeichert wird der SHA-256-Hash (Anmeldung: ``auth._token_user``).
"""
from __future__ import annotations

import secrets
from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import audit
from auth import TOKEN_PREFIX, hash_token, require_admin
from database import get_db

router = APIRouter(prefix="/api/admin/tokens")


class TokenIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    username: str = Field(min_length=2, max_length=64)           # Dienstkonto; wird angelegt, falls es noch nicht existiert
    role: Literal["editor", "viewer"] = "editor"                 # nur beim Anlegen des Kontos wirksam
    scope: Literal["read", "write"] = "read"
    project_ids: List[int] = []                                  # leer = alle Projekte, die das Konto sehen darf
    expires_days: int = Field(365, ge=1, le=3650)


def _row(r) -> dict:
    return {"id": r["id"], "name": r["name"], "username": r["username"], "role": r["role"], "prefix": r["prefix"], "scope": r["scope"],
            "project_ids": [int(x) for x in r["project_ids"].split(",") if x], "expires_at": r["expires_at"], "expired": bool(r["expired"]),
            "last_used_at": r["last_used_at"], "created_by": r["created_by"], "created_at": r["created_at"]}


_SELECT = ("SELECT t.*, u.username, u.role, (t.expires_at IS NOT NULL AND t.expires_at <= datetime('now')) AS expired "
           "FROM api_tokens t JOIN users u ON u.id=t.user_id")


@router.get("")
def list_tokens(_=Depends(require_admin), db=Depends(get_db, scope="function")):
    return [_row(r) for r in db.execute(_SELECT + " ORDER BY t.id DESC")]


@router.post("", status_code=201)
def create_token(body: TokenIn, admin=Depends(require_admin), db=Depends(get_db, scope="function")):
    ids = sorted(set(body.project_ids))
    for pid in ids:
        if not db.execute("SELECT 1 FROM projects WHERE id=?", (pid,)).fetchone():
            raise HTTPException(422, "Projekt %d existiert nicht" % pid)
    acc = db.execute("SELECT id, auth_source, role FROM users WHERE username=?", (body.username,)).fetchone()
    if acc and acc["auth_source"] != "service":
        raise HTTPException(409, "Der Benutzername gehört einem normalen Konto – bitte einen neuen Namen für das Dienstkonto wählen")
    if acc:
        uid = acc["id"]
    else:
        uid = db.execute("INSERT INTO users(username, display_name, password_hash, role, auth_source) VALUES (?,?,?,?, 'service')",
                         (body.username, body.name, "service$" + secrets.token_hex(16), body.role)).lastrowid     # Hash ohne gültiges Format: Passwort-Login unmöglich
        audit.log(db, admin, "user.create", "%s (%s, service)" % (body.username, body.role))
    raw = TOKEN_PREFIX + secrets.token_urlsafe(30)
    tid = db.execute("INSERT INTO api_tokens(user_id, name, token_hash, prefix, scope, project_ids, expires_at, created_by) "
                     "VALUES (?,?,?,?,?,?, datetime('now', ?), ?)",
                     (uid, body.name.strip(), hash_token(raw), raw[:len(TOKEN_PREFIX) + 6], body.scope, ",".join(map(str, ids)),
                      "+%d days" % body.expires_days, admin["username"])).lastrowid
    audit.log(db, admin, "token.create", "%s: Konto %s, %s, %s, %d Tage" % (body.name.strip(), body.username, body.scope,
                                                                         "Projekte " + ",".join(map(str, ids)) if ids else "alle Projekte", body.expires_days))
    out = _row(db.execute(_SELECT + " WHERE t.id=?", (tid,)).fetchone())
    out["token"] = raw                    # einmalig – danach nicht mehr abrufbar
    return out


@router.delete("/{tid}")
def revoke_token(tid: int, admin=Depends(require_admin), db=Depends(get_db, scope="function")):
    r = db.execute(_SELECT + " WHERE t.id=?", (tid,)).fetchone()
    if not r:
        raise HTTPException(404, "Token nicht gefunden")
    db.execute("DELETE FROM api_tokens WHERE id=?", (tid,))
    audit.log(db, admin, "token.revoke", "%s (Konto %s)" % (r["name"], r["username"]))
    return {"ok": True}
