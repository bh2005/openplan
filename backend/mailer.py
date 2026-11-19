"""E-Mail-Versand (SMTP) für Benachrichtigungen und Reports. Einstellungen in der Verwaltung (``app_settings``/``mail``)."""
from __future__ import annotations

import json
import logging
import re
import smtplib
import ssl
import threading
import datetime as dt
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException

log = logging.getLogger("openplan.mail")

DEFAULTS: Dict[str, Any] = {
    "enabled": False, "host": "", "port": 25, "security": "none", "username": "", "password": "",
    "from_addr": "", "from_name": "OpenPlan", "public_url": "",
}
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
run_async = True                        # Tests setzen False: dann wird synchron versendet


def settings(db) -> Dict[str, Any]:
    r = db.execute("SELECT value FROM app_settings WHERE key='mail'").fetchone()
    return {**DEFAULTS, **(json.loads(r["value"]) if r else {})}


def public(db) -> Dict[str, Any]:
    s = settings(db)
    pw = bool(s.pop("password"))
    st = db.execute("SELECT value FROM app_settings WHERE key='mail_state'").fetchone()
    return {**s, "password_set": pw, "state": json.loads(st["value"]) if st else {}}


def validate(v: Dict[str, Any]) -> None:
    if v["enabled"]:
        if not v["host"]:
            raise HTTPException(422, "SMTP-Server fehlt")
        if not _EMAIL.match(v["from_addr"] or ""):
            raise HTTPException(422, "Absenderadresse fehlt oder ist ungültig")
    if not (1 <= int(v["port"]) <= 65535):
        raise HTTPException(422, "Port ungültig")
    if v["security"] not in ("none", "starttls", "ssl"):
        raise HTTPException(422, "Verschlüsselung: none, starttls oder ssl")
    url = (v["public_url"] or "").strip().rstrip("/")
    if url and not re.match(r"^https?://[^\s/]+(/[^\s]*)?$", url):
        raise HTTPException(422, "Öffentliche URL muss mit http:// oder https:// beginnen")


def save(db, patch: Dict[str, Any]) -> Dict[str, Any]:
    cur = settings(db)
    for k, val in patch.items():
        if k not in DEFAULTS or val is None:
            continue
        if k == "password" and val == "":
            continue
        cur[k] = val.strip() if isinstance(val, str) and k != "password" else val
    if patch.get("clear_password"):
        cur["password"] = ""
    cur["public_url"] = (cur["public_url"] or "").rstrip("/")
    validate(cur)
    db.execute("INSERT INTO app_settings(key, value) VALUES ('mail', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps(cur),))
    return public(db)


def configured(db) -> bool:
    s = settings(db)
    return bool(s["enabled"] and s["host"] and s["from_addr"])


def base_url(db, fallback: str = "") -> str:
    return (settings(db)["public_url"] or fallback or "").rstrip("/")


def _connect(s: Dict[str, Any]):
    if s["security"] == "ssl":
        srv = smtplib.SMTP_SSL(s["host"], int(s["port"]), timeout=15, context=ssl.create_default_context())
    else:
        srv = smtplib.SMTP(s["host"], int(s["port"]), timeout=15)
        srv.ehlo()
        if s["security"] == "starttls":
            srv.starttls(context=ssl.create_default_context())
            srv.ehlo()
    if s["username"]:
        srv.login(s["username"], s["password"])
    return srv


def build_message(s: Dict[str, Any], to: str, subject: str, text: str, html: Optional[str]) -> EmailMessage:
    m = EmailMessage()
    m["From"] = formataddr((s["from_name"] or "OpenPlan", s["from_addr"]))
    m["To"] = to
    m["Subject"] = re.sub(r"[\r\n]+", " ", subject)[:200]
    m["Date"] = dt.datetime.now(dt.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    m["Auto-Submitted"] = "auto-generated"
    m.set_content(text)
    if html:
        m.add_alternative(html, subtype="html")
    return m


def send_now(s: Dict[str, Any], to: str, subject: str, text: str, html: Optional[str] = None) -> None:
    """Eine Mail synchron senden (wirft bei Fehlern)."""
    srv = _connect(s)
    try:
        srv.send_message(build_message(s, to, subject, text, html))
    finally:
        try:
            srv.quit()
        except smtplib.SMTPException:
            pass


def _record(state: Dict[str, Any], db=None) -> None:
    """Status des letzten Versands für die Verwaltung festhalten (mit eigener Verbindung, wenn keine übergeben wird)."""
    from database import connect
    own = db is None
    conn = connect() if own else db
    try:
        conn.execute("INSERT INTO app_settings(key, value) VALUES ('mail_state', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps(state),))
        if own:
            conn.commit()
    except Exception:                                    # Status ist nur Komfort – nie den Versand stören
        log.exception("Mail-Status konnte nicht gespeichert werden")
    finally:
        if own:
            conn.close()


def deliver(s: Dict[str, Any], messages: Iterable[Dict[str, Any]], db=None) -> int:
    """Mails nacheinander senden (eine SMTP-Sitzung je Mail); Ergebnis/Fehler wird für die Verwaltung festgehalten."""
    ok = fail = 0
    err = ""
    for m in messages:
        try:
            send_now(s, m["to"], m["subject"], m["text"], m.get("html"))
            ok += 1
        except (smtplib.SMTPException, OSError, ssl.SSLError) as e:
            fail += 1
            err = "%s: %s" % (type(e).__name__, e)
            log.error("Mailversand an %s fehlgeschlagen: %s", m["to"], err)
    if ok or fail:
        _record({"ts": dt.datetime.now(dt.timezone.utc).isoformat(), "ok": fail == 0, "sent": ok, "failed": fail,
                 "message": err or "%d Mail(s) gesendet" % ok}, db)
    return ok


def dispatch(db, messages: List[Dict[str, Any]]) -> None:
    """Mails nach der Anfrage im Hintergrund versenden (Einstellungen werden jetzt gelesen)."""
    if not messages or not configured(db):
        return
    s = settings(db)
    if run_async:
        threading.Thread(target=deliver, args=(s, messages), daemon=True, name="mail").start()
    else:
        deliver(s, messages, db)
