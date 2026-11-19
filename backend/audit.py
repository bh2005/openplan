"""Audit-Log: wer hat wann was in der Verwaltung/Anmeldung/Datensicherung getan (Tabelle ``audit_log``)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log_ = logging.getLogger("openplan.audit")
KEEP_DAYS = 365


def _name(user: Any) -> str:
    return user if isinstance(user, str) else (user or {}).get("username", "")


def log(db, user: Any, action: str, detail: str = "", ip: str = "") -> None:
    """Eintrag in der laufenden Transaktion (wird mit der Anfrage committed)."""
    db.execute("INSERT INTO audit_log(username, action, detail, ip) VALUES (?,?,?,?)", (_name(user), action[:80], detail[:500], ip[:64]))
    log_.info("%s | %s | %s | %s", _name(user), action, detail, ip)


def log_now(user: Any, action: str, detail: str = "", ip: str = "") -> None:
    """Eintrag mit eigener Verbindung – bleibt auch erhalten, wenn die Anfrage danach scheitert (z. B. fehlgeschlagener Login)."""
    from database import connect
    try:
        conn = connect()
        try:
            log(conn, user, action, detail, ip)
            conn.commit()
        finally:
            conn.close()
    except Exception:
        log_.exception("Audit-Eintrag konnte nicht geschrieben werden")


def ip_of(request) -> str:
    return request.client.host if request is not None and request.client else ""


def query(db, q: str = "", action: str = "", limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    where, args = [], []
    if q.strip():
        where.append("(username LIKE ? OR detail LIKE ? OR ip LIKE ?)")
        args += ["%" + q.strip() + "%"] * 3
    if action.strip():
        where.append("action LIKE ?")
        args.append(action.strip() + "%")
    w = (" WHERE " + " AND ".join(where)) if where else ""
    total = db.execute("SELECT COUNT(*) FROM audit_log" + w, args).fetchone()[0]
    rows = [dict(r) for r in db.execute("SELECT * FROM audit_log" + w + " ORDER BY id DESC LIMIT ? OFFSET ?", args + [min(max(limit, 1), 500), max(offset, 0)])]
    actions = [r[0] for r in db.execute("SELECT DISTINCT action FROM audit_log ORDER BY action")]
    return {"total": total, "items": rows, "actions": actions}


def prune(db, days: int = KEEP_DAYS) -> None:
    db.execute("DELETE FROM audit_log WHERE ts < datetime('now', ?)", ("-%d days" % days,))
