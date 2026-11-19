"""Ausgehende Webhooks und Callback-Endpunkt für Fremdsysteme.

Ablauf: Eine Änderung (Status, Zuordnung, neues Gerät) ruft ``emit`` in derselben Transaktion auf – bei Rollback (auch Trockenlauf des
Geräteimports) entsteht nichts. ``emit`` legt je passendem Webhook eine Zeile in ``webhook_deliveries`` an; ein Hintergrund-Thread liefert aus
und wiederholt bei Fehlern (1, 5, 30, 120 Minuten; danach ``failed``). Der Empfänger prüft ``X-OpenPlan-Signature`` (HMAC-SHA256 über den Body).

Sicherheit: nur https (``WEBHOOK_ALLOW_HTTP=1`` erlaubt http), keine Ziele auf Loopback/Link-Local (inkl. Cloud-Metadaten 169.254.169.254)
oder nicht auflösbare Namen, keine Weiterleitungen, optionale Positivliste ``WEBHOOK_ALLOWED_HOSTS`` (kommagetrennte Domains).
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import os
import secrets
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import access
import audit
import service as svc
from auth import require_admin
from database import connect, get_db
from schemas import Status

log = logging.getLogger("openplan.webhooks")
router = APIRouter(prefix="/api")

EVENTS = ("task.status", "task.blocked", "task.assigned", "device.created", "ping")
BACKOFF_MIN = (1, 5, 30, 120)          # Wartezeit nach Fehlversuch 1..4; der 5. Fehlversuch beendet die Zustellung
MAX_ATTEMPTS = len(BACKOFF_MIN) + 1
KEEP_DAYS = 14
TIMEOUT = 10


# ── Zieladresse prüfen ──────────────────────────────────────────────────────────
def check_url(url: str) -> None:
    """Wirft HTTPException(422), wenn die Adresse als Webhook-Ziel nicht zulässig ist."""
    p = urllib.parse.urlsplit(url.strip())
    allow_http = os.environ.get("WEBHOOK_ALLOW_HTTP", "").lower() in ("1", "true", "yes")
    if p.scheme not in (("https", "http") if allow_http else ("https",)):
        raise HTTPException(422, "Ziel-URL muss mit https:// beginnen")
    if not p.hostname or p.username or p.password:
        raise HTTPException(422, "Ziel-URL ohne Benutzer/Passwort und mit Rechnername angeben")
    allowed = [h.strip().lower().lstrip(".") for h in os.environ.get("WEBHOOK_ALLOWED_HOSTS", "").split(",") if h.strip()]
    host = p.hostname.lower()
    if allowed and not any(host == a or host.endswith("." + a) for a in allowed):
        raise HTTPException(422, "Ziel nicht in WEBHOOK_ALLOWED_HOSTS erlaubt")
    try:
        infos = socket.getaddrinfo(host, p.port or (443 if p.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise HTTPException(422, "Rechnername „%s“ ist nicht auflösbar" % host)
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_multicast or ip.is_reserved:
            raise HTTPException(422, "Ziel %s ist nicht zulässig (Loopback, Link-Local oder reserviert)" % ip)


# ── Ereignisse anlegen (in der Transaktion der Änderung) ───────────────────────
def _matches(events: str, event: str) -> bool:
    ev = [e.strip() for e in events.split(",") if e.strip()]
    return "*" in ev or event in ev


def _device_of(db, tid: int) -> Optional[Dict[str, str]]:
    cur = tid
    for _ in range(6):                                  # Gerät = Vorgang mit ext_key, selbst oder Elternteil
        r = db.execute("SELECT id, parent_id, name, ext_key, attrs FROM tasks WHERE id=?", (cur,)).fetchone()
        if not r:
            return None
        if r["ext_key"] is not None:
            a = json.loads(r["attrs"]) if r["attrs"] else {}
            return {"id": r["id"], "hostname": a.get("hostname") or r["name"], "standort": a.get("standort", ""), "typ": a.get("typ", "")}
        if r["parent_id"] is None:
            return None
        cur = r["parent_id"]
    return None


def _task_payload(db, tid: int) -> Dict[str, Any]:
    t = db.execute("SELECT id, name, status, percent, status_note FROM tasks WHERE id=?", (tid,)).fetchone()
    return {"id": t["id"], "name": t["name"], "status": t["status"], "percent": t["percent"], "status_note": t["status_note"],
            "device": _device_of(db, tid),
            "refs": {r["system"]: r["ref"] for r in db.execute("SELECT system, ref FROM external_refs WHERE task_id=?", (tid,))}}


def emit(db, pid: Optional[int], event: str, tid: Optional[int] = None, actor: Any = "", previous: Optional[Dict[str, Any]] = None,
         extra: Optional[Dict[str, Any]] = None) -> int:
    """Legt für jeden passenden, aktiven Webhook eine Zustellung an. Liefert die Anzahl (0 = keine Webhooks eingerichtet)."""
    hooks = [h for h in db.execute("SELECT id, events FROM webhooks WHERE enabled=1 AND (project_id IS NULL OR project_id IS ?)", (pid,))
             if _matches(h["events"], event)]
    if not hooks:
        return 0
    body: Dict[str, Any] = {"id": "evt_" + secrets.token_hex(8), "event": event,
                            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "actor": actor if isinstance(actor, str) else (actor or {}).get("username", "")}
    if pid is not None:
        p = db.execute("SELECT id, name FROM projects WHERE id=?", (pid,)).fetchone()
        if p:
            body["project"] = {"id": p["id"], "name": p["name"]}
    if tid is not None:
        body["task"] = _task_payload(db, tid)
    if previous:
        body["previous"] = previous
    if extra:
        body.update(extra)
    text = json.dumps(body, ensure_ascii=False)
    for h in hooks:
        db.execute("INSERT INTO webhook_deliveries(webhook_id, event, payload) VALUES (?,?,?)", (h["id"], event, text))
    return len(hooks)


def status_changed(db, pid: int, tid: int, old: str, new: str, actor: Any) -> None:
    """Statuswechsel eines Blatt-Vorgangs: ``task.status`` und bei „blocked“ zusätzlich ``task.blocked``."""
    if old == new:
        return
    emit(db, pid, "task.status", tid, actor, {"status": old})
    if new == "blocked":
        emit(db, pid, "task.blocked", tid, actor, {"status": old})


# ── Zustellung ─────────────────────────────────────────────────────────────────────────────
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):               # Weiterleitungen würden die Zielprüfung umgehen
        return None


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _send(url: str, secret: str, event: str, delivery_id: int, body: bytes) -> int:
    check_url(url)                                      # erneut: DNS kann sich seit dem Anlegen geändert haben
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json; charset=utf-8", "User-Agent": "OpenPlan-Webhook/1",
        "X-OpenPlan-Event": event, "X-OpenPlan-Delivery": str(delivery_id), "X-OpenPlan-Timestamp": str(int(time.time())),
        "X-OpenPlan-Signature": sign(secret, body)})
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=TIMEOUT) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def deliver(conn, did: int) -> Dict[str, Any]:
    """Eine Zustellung versuchen und das Ergebnis speichern. Gibt {'status', 'code', 'error'} zurück."""
    d = conn.execute("SELECT d.*, w.url, w.secret, w.enabled FROM webhook_deliveries d JOIN webhooks w ON w.id=d.webhook_id WHERE d.id=?", (did,)).fetchone()
    if not d or d["status"] != "pending":
        return {"status": d["status"] if d else "gone", "code": d["last_code"] if d else None, "error": ""}
    attempts = d["attempts"] + 1
    code, err = None, ""
    if not d["enabled"]:
        err = "Webhook deaktiviert"
        status, nxt = "failed", None
    else:
        try:
            code = _send(d["url"], d["secret"], d["event"], did, d["payload"].encode("utf-8"))
            ok = 200 <= code < 300
            err = "" if ok else "HTTP %d" % code
        except HTTPException as e:
            ok, err = False, str(e.detail)
        except Exception as e:                           # Netzwerk-, TLS-, Zeitüberschreitung
            ok, err = False, (type(e).__name__ + ": " + str(e))[:300]
        status = "ok" if ok else ("failed" if attempts >= MAX_ATTEMPTS else "pending")
        nxt = None if status != "pending" else "+%d minutes" % BACKOFF_MIN[attempts - 1]
    if nxt:
        conn.execute("UPDATE webhook_deliveries SET attempts=?, status=?, last_code=?, last_error=?, next_try=datetime('now', ?) WHERE id=?", (attempts, status, code, err, nxt, did))
    else:
        conn.execute("UPDATE webhook_deliveries SET attempts=?, status=?, last_code=?, last_error=? WHERE id=?", (attempts, status, code, err, did))
    conn.commit()
    return {"status": status, "code": code, "error": err}


def run_due(limit: int = 20) -> int:
    conn = connect()
    try:
        ids = [r["id"] for r in conn.execute("SELECT id FROM webhook_deliveries WHERE status='pending' AND next_try <= datetime('now') ORDER BY id LIMIT ?", (limit,))]
        for i in ids:
            deliver(conn, i)
        return len(ids)
    finally:
        conn.close()


def prune() -> None:
    conn = connect()
    try:
        conn.execute("DELETE FROM webhook_deliveries WHERE ts < datetime('now', ?)", ("-%d days" % KEEP_DAYS,))
        conn.commit()
    finally:
        conn.close()


_started = False


def start_background(interval: float = 10.0) -> None:
    global _started
    if _started or os.environ.get("WEBHOOK_WORKER", "1") == "0":
        return
    _started = True

    def loop():
        last_prune = 0.0
        while True:
            try:
                run_due()
                if time.time() - last_prune > 3600:
                    prune()
                    last_prune = time.time()
            except Exception:
                log.exception("Webhook-Zustellung")
            time.sleep(interval)

    threading.Thread(target=loop, daemon=True, name="webhooks").start()


# ── Verwaltung (Admin) ────────────────────────────────────────────────────────────────────
class WebhookIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    url: str = Field(min_length=8, max_length=500)
    events: List[str] = ["*"]
    project_id: Optional[int] = None                  # None = alle Projekte
    enabled: bool = True
    rotate_secret: bool = False                       # nur beim Ändern: neues Geheimnis erzeugen und einmalig ausgeben


def _events(ev: List[str]) -> str:
    bad = [e for e in ev if e != "*" and e not in EVENTS]
    if bad:
        raise HTTPException(422, "Unbekanntes Ereignis: %s (erlaubt: %s oder *)" % (", ".join(bad), ", ".join(e for e in EVENTS if e != "ping")))
    return ",".join(dict.fromkeys(ev)) or "*"


def _hook(r) -> Dict[str, Any]:
    return {"id": r["id"], "name": r["name"], "url": r["url"], "events": r["events"].split(","), "project_id": r["project_id"], "enabled": bool(r["enabled"]),
            "created_by": r["created_by"], "pending": r["pending"], "failed": r["failed"], "last_ok": r["last_ok"]}


_LIST = ("SELECT w.*, (SELECT COUNT(*) FROM webhook_deliveries d WHERE d.webhook_id=w.id AND d.status='pending') AS pending, "
         "(SELECT COUNT(*) FROM webhook_deliveries d WHERE d.webhook_id=w.id AND d.status='failed') AS failed, "
         "(SELECT MAX(d.ts) FROM webhook_deliveries d WHERE d.webhook_id=w.id AND d.status='ok') AS last_ok FROM webhooks w")


def _validate_project(db, pid: Optional[int]) -> None:
    if pid is not None and not db.execute("SELECT 1 FROM projects WHERE id=?", (pid,)).fetchone():
        raise HTTPException(422, "Projekt %d existiert nicht" % pid)


@router.get("/admin/webhooks")
def list_hooks(_=Depends(require_admin), db=Depends(get_db, scope="function")):
    return {"items": [_hook(r) for r in db.execute(_LIST + " ORDER BY w.id")], "events": [e for e in EVENTS if e != "ping"]}


@router.post("/admin/webhooks", status_code=201)
def create_hook(body: WebhookIn, admin=Depends(require_admin), db=Depends(get_db, scope="function")):
    check_url(body.url)
    _validate_project(db, body.project_id)
    secret = "whsec_" + secrets.token_urlsafe(32)
    wid = db.execute("INSERT INTO webhooks(name, url, secret, events, project_id, enabled, created_by) VALUES (?,?,?,?,?,?,?)",
                     (body.name.strip(), body.url.strip(), secret, _events(body.events), body.project_id, int(body.enabled), admin["username"])).lastrowid
    audit.log(db, admin, "webhook.create", "%s → %s" % (body.name.strip(), urllib.parse.urlsplit(body.url).hostname))
    out = _hook(db.execute(_LIST + " WHERE w.id=?", (wid,)).fetchone())
    out["secret"] = secret                              # einmalig – danach nicht mehr abrufbar
    return out


@router.put("/admin/webhooks/{wid}")
def update_hook(wid: int, body: WebhookIn, admin=Depends(require_admin), db=Depends(get_db, scope="function")):
    if not db.execute("SELECT 1 FROM webhooks WHERE id=?", (wid,)).fetchone():
        raise HTTPException(404, "Webhook nicht gefunden")
    check_url(body.url)
    _validate_project(db, body.project_id)
    db.execute("UPDATE webhooks SET name=?, url=?, events=?, project_id=?, enabled=? WHERE id=?",
               (body.name.strip(), body.url.strip(), _events(body.events), body.project_id, int(body.enabled), wid))
    secret = None
    if body.rotate_secret:
        secret = "whsec_" + secrets.token_urlsafe(32)
        db.execute("UPDATE webhooks SET secret=? WHERE id=?", (secret, wid))
    audit.log(db, admin, "webhook.update", "%s%s" % (body.name.strip(), " (neues Geheimnis)" if secret else ""))
    out = _hook(db.execute(_LIST + " WHERE w.id=?", (wid,)).fetchone())
    if secret:
        out["secret"] = secret
    return out


@router.delete("/admin/webhooks/{wid}")
def delete_hook(wid: int, admin=Depends(require_admin), db=Depends(get_db, scope="function")):
    r = db.execute("SELECT name FROM webhooks WHERE id=?", (wid,)).fetchone()
    if not r:
        raise HTTPException(404, "Webhook nicht gefunden")
    db.execute("DELETE FROM webhooks WHERE id=?", (wid,))
    audit.log(db, admin, "webhook.delete", r["name"])
    return {"ok": True}


@router.get("/admin/webhooks/{wid}/deliveries")
def deliveries(wid: int, limit: int = 50, _=Depends(require_admin), db=Depends(get_db, scope="function")):
    if not db.execute("SELECT 1 FROM webhooks WHERE id=?", (wid,)).fetchone():
        raise HTTPException(404, "Webhook nicht gefunden")
    return [dict(r) for r in db.execute("SELECT id, event, status, attempts, last_code, last_error, next_try, ts FROM webhook_deliveries "
                                        "WHERE webhook_id=? ORDER BY id DESC LIMIT ?", (wid, min(max(limit, 1), 200)))]


@router.post("/admin/webhooks/{wid}/test")
def test_hook(wid: int, admin=Depends(require_admin), db=Depends(get_db, scope="function")):
    """Sendet ein ``ping``-Ereignis sofort und meldet das Ergebnis (unabhängig von der Ereignisauswahl des Webhooks)."""
    if not db.execute("SELECT 1 FROM webhooks WHERE id=?", (wid,)).fetchone():
        raise HTTPException(404, "Webhook nicht gefunden")
    body = json.dumps({"id": "evt_" + secrets.token_hex(8), "event": "ping", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "actor": admin["username"]})
    did = db.execute("INSERT INTO webhook_deliveries(webhook_id, event, payload) VALUES (?,?,?)", (wid, "ping", body)).lastrowid
    db.commit()                                         # sichtbar für die zweite Verbindung in deliver()
    conn = connect()
    try:
        res = deliver(conn, did)
    finally:
        conn.close()
    audit.log(db, admin, "webhook.test", "Webhook %d: %s" % (wid, res["status"]))
    return {**res, "delivery_id": did}


# ── Callback eines Fremdsystems (z. B. AWX meldet Joberfolg) ─────────────────────────────────────
class TaskEventIn(BaseModel):
    status: Optional[Status] = None
    percent: Optional[float] = Field(None, ge=0, le=100)
    note: Optional[str] = Field(None, max_length=300)           # wird als Status-Notiz gespeichert (z. B. „AWX-Job 4711 erfolgreich“)
    system: Optional[Literal["servicenow", "awx", "checkmk", "jira", "autopatch"]] = None
    ref: Optional[str] = Field(None, max_length=200)            # zusammen mit ``system``: externe Referenz am Vorgang setzen
    url: str = Field("", max_length=500)


def apply_task_event(db, user, t, status: Optional[str] = None, percent: Optional[float] = None, note: Optional[str] = None,
                     system: Optional[str] = None, ref: Optional[str] = None, url: str = "", journal: str = "Rückmeldung (API)") -> Tuple[bool, str]:
    """Status/Fortschritt/Notiz/Referenz an einem Teilvorgang setzen (Journal, Revision, Webhook). Idempotent.

    ``t`` ist die Zeile aus ``tasks``; Rückgabe: (geändert, neuer Status). Rechte und Sammelvorgang prüft der Aufrufer."""
    from refs import RefIn
    tid, pid = t["id"], t["project_id"]
    changes: List[str] = []
    st, pc = t["status"], t["percent"]
    if status is not None or percent is not None:
        st, pc = svc.apply_status(t["status"], t["percent"], status, percent)
        if st != t["status"] or pc != t["percent"]:
            db.execute("UPDATE tasks SET status=?, percent=?, status_note=CASE WHEN ?='blocked' THEN status_note ELSE '' END WHERE id=?", (st, pc, st, tid))
            changes.append("status/fortschritt: %s %s%% → %s %s%%" % (t["status"], t["percent"], st, pc))
    if note is not None and note != db.execute("SELECT status_note FROM tasks WHERE id=?", (tid,)).fetchone()["status_note"]:
        db.execute("UPDATE tasks SET status_note=? WHERE id=?", (note, tid))
        changes.append("status-notiz")
    if system and ref:
        r = RefIn(ref=ref, url=url)
        old = db.execute("SELECT ref, url FROM external_refs WHERE task_id=? AND system=?", (tid, system)).fetchone()
        if not old or old["ref"] != r.ref or old["url"] != r.url:
            db.execute("INSERT INTO external_refs(task_id, system, ref, url) VALUES (?,?,?,?) ON CONFLICT(task_id, system) DO UPDATE SET ref=excluded.ref, url=excluded.url",
                       (tid, system, r.ref, r.url))
            changes.append("referenz %s: %s" % (system, r.ref))
    if changes:
        svc.bump(db, pid)
        svc.log(db, pid, user, journal, "%s | %s" % (t["name"], "; ".join(changes)), tid)
        status_changed(db, pid, tid, t["status"], st, user)
    return bool(changes), st


@router.post("/tasks/{tid}/events")
def task_event(tid: int, body: TaskEventIn, user=Depends(access.task_own()), db=Depends(get_db, scope="function")):
    """Schmaler, idempotenter Rückkanal für Automatisierung: Status/Fortschritt/Notiz und optional eine Referenz setzen.

    Nur für Blatt-Vorgänge; gleiche Werte ein zweites Mal senden ändert nichts (keine Revision, kein Webhook)."""
    t = svc.project_of_task(db, tid)
    if db.execute("SELECT 1 FROM tasks WHERE parent_id=?", (tid,)).fetchone():
        raise HTTPException(422, "Nur für Teilvorgänge ohne Unterpunkte (kein Sammelvorgang)")
    if access.level_of(db, user, t["project_id"]) < 3 and (body.system or body.ref):
        raise HTTPException(403, "Referenzen setzen darf nur ein Bearbeiter")
    if bool(body.system) != bool(body.ref):
        raise HTTPException(422, "system und ref gehören zusammen")
    changed, _ = apply_task_event(db, user, t, body.status, body.percent, body.note, body.system, body.ref, body.url)
    cur = db.execute("SELECT status, percent, status_note FROM tasks WHERE id=?", (tid,)).fetchone()
    return {"changed": changed, "task": {"id": tid, "status": cur["status"], "percent": cur["percent"], "status_note": cur["status_note"]}}
