"""Verwaltung → Server-Umgebung: ``.env`` bearbeiten und den Container neu starten (nur Admins)."""
from __future__ import annotations

import datetime as dt
import os
import pathlib
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

import audit
import config
import envfile
from auth import require_admin
from database import get_db

router = APIRouter(prefix="/api/admin")
KNOWN = [
    "ADMIN_USERNAME", "ADMIN_PASSWORD", "TOKEN_TTL_HOURS", "MAX_UPLOAD_MB", "TZ", "PORT", "TLS_PORT", "FORCE_HTTPS", "PUBLIC_HTTPS_PORT",
    "BACKUP_DIR", "LDAP_URL", "LDAP_BASE_DN", "LDAP_DOMAIN", "LDAP_BIND_DN", "LDAP_BIND_PASSWORD", "LDAP_USER_FILTER", "LDAP_CA_FILE",
    "LDAP_REQUIRED_GROUP", "LDAP_ADMIN_GROUP", "LDAP_AUDITOR_GROUP", "LDAP_DEFAULT_ROLE", "LDAP_AUTO_CREATE", "LDAP_NESTED_GROUPS",
    "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "SSL_CERT_FILE", "JWT_SECRET",
    "API_DOCS", "API_TOKEN_RATE", "WEBHOOK_ALLOWED_HOSTS", "WEBHOOK_ALLOW_HTTP", "WEBHOOK_WORKER",
]
KEEP_BACKUPS = 10


class EnvEntry(BaseModel):
    key: str = Field(max_length=100)
    value: Optional[str] = Field(None, max_length=4000)     # None = unverändert lassen (nur bei vorhandenen Schlüsseln)


class EnvIn(BaseModel):
    entries: List[EnvEntry] = Field(max_length=300)


def _backup_dir() -> pathlib.Path:
    return pathlib.Path(config.DATA_DIR) / "env-backups"


def _state(user_secret_peek: bool = False) -> Dict[str, Any]:
    path = envfile.current_path()
    base: Dict[str, Any] = {"enabled": False, "path": path, "known": KNOWN, "restart_enabled": os.environ.get("ALLOW_SELF_RESTART") == "1",
                            "backup_dir": str(_backup_dir()), "entries": [], "pending_restart": False, "reason": ""}
    if not path:
        base["reason"] = "ENV_FILE ist nicht gesetzt: Die .env-Datei muss in den Container eingebunden werden (Compose: ./.env:/app/.env und ENV_FILE=/app/.env)."
        return base
    try:
        text = envfile.read(path)
    except (OSError, UnicodeDecodeError) as e:
        base["reason"] = "Die Datei %s ist nicht lesbar: %s" % (path, e)
        return base
    items = envfile.parse(text)
    base.update(enabled=True, writable=os.access(path, os.W_OK), pending_restart=envfile.digest(items) != envfile.LOADED_HASH,
                entries=[{"key": k, "secret": envfile.is_secret(k), "set": v != "", "value": None if envfile.is_secret(k) else v} for k, v in items])
    return base


@router.get("/env")
def get_env(admin=Depends(require_admin)):
    return _state()


@router.put("/env")
def save_env(body: EnvIn, request: Request, admin=Depends(require_admin), db=Depends(get_db, scope="function")):
    path = envfile.current_path()
    st = _state()
    if not st["enabled"]:
        raise HTTPException(409, st["reason"])
    if not st["writable"]:
        raise HTTPException(409, "Die .env-Datei ist schreibgeschützt (Container-Mount ohne Schreibrecht oder falscher Besitzer).")
    old = {e["key"]: e for e in st["entries"]}
    desired: Dict[str, Optional[str]] = {}
    for e in body.entries:
        k = e.key.strip()
        if not envfile.KEY_RE.match(k):
            raise HTTPException(422, "Ungültiger Variablenname: %s" % k[:40])
        if k in envfile.RESERVED:
            raise HTTPException(422, "%s darf hier nicht geändert werden" % k)
        if k in desired:
            raise HTTPException(422, "Variable doppelt angegeben: %s" % k)
        if e.value is None and k not in old:
            raise HTTPException(422, "Für die neue Variable %s fehlt ein Wert" % k)
        if e.value is None and not old[k]["secret"]:
            raise HTTPException(422, "Für %s fehlt der Wert" % k)
        desired[k] = e.value
    try:
        text = envfile.apply(envfile.read(path), desired)
    except ValueError as ex:
        raise HTTPException(422, str(ex))
    new = dict(envfile.parse(text))
    added = [k for k in new if k not in old]
    removed = [k for k in old if k not in new]
    changed = [k for k in new if k in old and (old[k]["secret"] and desired.get(k) is not None or (not old[k]["secret"] and old[k]["value"] != new[k]))]
    if not (added or removed or changed):
        return _state()
    bdir = _backup_dir()                                    # Sicherung der alten Datei (enthält Geheimnisse → 0600)
    bdir.mkdir(parents=True, exist_ok=True)
    bak = bdir / ("env-%s.bak" % dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
    bak.write_text(envfile.read(path), encoding="utf-8")
    try:
        bak.chmod(0o600)
    except OSError:
        pass
    for old_bak in sorted(bdir.glob("env-*.bak"))[:-KEEP_BACKUPS]:
        old_bak.unlink(missing_ok=True)
    envfile.write_in_place(path, text)
    audit.log(db, admin, "env.save", "geändert: %s; neu: %s; entfernt: %s (nur Namen)" % (", ".join(changed) or "-", ", ".join(added) or "-", ", ".join(removed) or "-"),
              audit.ip_of(request))
    return _state()


@router.post("/restart")
def restart(request: Request, admin=Depends(require_admin), db=Depends(get_db, scope="function")):
    if os.environ.get("ALLOW_SELF_RESTART") != "1":
        raise HTTPException(409, "Neustart aus der Oberfläche ist nicht aktiviert (ALLOW_SELF_RESTART=1 und restart: unless-stopped in der Compose-Datei).")
    audit.log(db, admin, "server.restart", "", audit.ip_of(request))
    db.commit()
    envfile.schedule_restart()
    return {"restarting": True}
