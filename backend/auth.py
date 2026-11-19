import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from collections import deque
from typing import Dict, Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import DATA_DIR, TOKEN_TTL_HOURS
from database import get_db

_bearer = HTTPBearer(auto_error=False)
_ITER = 200_000


def _secret() -> str:
    env = os.environ.get("JWT_SECRET")
    if env:
        return env
    f = DATA_DIR / "jwt_secret"
    if not f.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        f.write_text(secrets.token_urlsafe(48))
        try:
            f.chmod(0o600)
        except OSError:
            pass
    return f.read_text().strip()


def hash_password(pw: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), _ITER).hex()
    return "pbkdf2$%s$%s" % (salt, h)


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, salt, h = stored.split("$")
    except ValueError:
        return False
    cand = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), _ITER).hex()
    return hmac.compare_digest(cand, h)


def label(u) -> str:
    """Anzeigename eines Benutzers (dict/Row); ohne Anzeigenamen der Benutzername."""
    try:
        d = u["display_name"]
    except (KeyError, IndexError):
        d = ""
    return d or u["username"]


def create_token(user_id: int, username: str, role: str, version: int = 0) -> str:
    now = int(time.time())
    return jwt.encode({"sub": str(user_id), "name": username, "role": role, "tv": version,
                       "iat": now, "exp": now + TOKEN_TTL_HOURS * 3600}, _secret(), algorithm="HS256")


TOKEN_PREFIX = "op_"                  # API-Tokens der Dienstkonten (JWTs beginnen nie so)
RATE_LIMIT = int(os.environ.get("API_TOKEN_RATE", "120"))    # Anfragen je Token und Minute
_USER_COLS = "id, username, display_name, role, email, notify_email, lang, theme, see_all, token_version"
_rate: Dict[int, deque] = {}
_rate_lock = threading.Lock()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _rate_ok(token_id: int) -> bool:
    now = time.monotonic()
    with _rate_lock:
        q = _rate.setdefault(token_id, deque())
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= RATE_LIMIT:
            return False
        q.append(now)
        return True


def _token_user(request: Request, raw: str, db):
    """Anmeldung per API-Token: Benutzer = Dienstkonto, zusätzlich ``user['token']`` mit Umfang und Projektbeschränkung."""
    row = db.execute("SELECT t.id AS tid, t.scope, t.project_ids, t.last_used_at, "
                     "(t.expires_at IS NOT NULL AND t.expires_at <= datetime('now')) AS expired, "
                     "(t.last_used_at IS NULL OR t.last_used_at <= datetime('now', '-60 seconds')) AS stale, "
                     "u.auth_source, " + ", ".join("u." + c.strip() for c in _USER_COLS.split(",")) +
                     " FROM api_tokens t JOIN users u ON u.id=t.user_id WHERE t.token_hash=?", (hash_token(raw),)).fetchone()
    if not row or row["auth_source"] != "service":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API-Token ungültig")
    if row["expired"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API-Token abgelaufen")
    if not _rate_ok(row["tid"]):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Zu viele Anfragen (max. %d pro Minute)" % RATE_LIMIT)
    projects = [int(x) for x in row["project_ids"].split(",") if x]
    if row["scope"] == "read" and request.method not in ("GET", "HEAD", "OPTIONS"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Dieses API-Token darf nur lesen")
    if projects and request.method == "POST" and re.fullmatch(r"/api/projects(/(wizard|demo))?/?", request.url.path):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ein auf Projekte beschränktes Token kann keine Projekte anlegen")
    if row["stale"]:
        db.execute("UPDATE api_tokens SET last_used_at=datetime('now') WHERE id=?", (row["tid"],))
    user = {c.strip(): row[c.strip()] for c in _USER_COLS.split(",")}
    user["token"] = {"id": row["tid"], "scope": row["scope"], "projects": projects}
    return user


def current_user(request: Request, cred: Optional[HTTPAuthorizationCredentials] = Depends(_bearer), db=Depends(get_db, scope="function")):
    if not cred:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Nicht angemeldet")
    if cred.credentials.startswith(TOKEN_PREFIX):
        return _token_user(request, cred.credentials, db)
    try:
        data = jwt.decode(cred.credentials, _secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token ungültig oder abgelaufen")
    row = db.execute("SELECT id, username, display_name, role, email, notify_email, lang, theme, see_all, token_version FROM users WHERE id=?", (int(data["sub"]),)).fetchone()
    if not row:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Benutzer existiert nicht mehr")
    if int(data.get("tv", 0)) != row["token_version"]:       # Passwort geändert / Sitzungen beendet
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sitzung beendet – bitte neu anmelden")
    return dict(row)


def require_editor(user=Depends(current_user)):
    if user["role"] not in ("admin", "editor"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Nur lesender Zugriff")
    return user


def require_admin(user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Nur für Administratoren")
    return user
