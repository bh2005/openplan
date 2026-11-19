"""Automatische Fälligkeits- und Eskalationshinweise.

Täglich (ab einer einstellbaren Uhrzeit) werden alle offenen Vorgänge geprüft:
* fällig in ≤ ``due_days`` Tagen  -> Bearbeiter (bei Pool-Paketen ohne Bearbeiter: Verantwortlicher)
* überfällig                      -> Bearbeiter; ab ``escalate_days`` Tagen zusätzlich der Projekt-Verantwortliche (Eskalation)
* blockiert seit ≥ ``blocked_days`` Tagen -> Verantwortlicher und Bearbeiter
Jede Meldung geht pro Vorgang/Termin nur einmal raus (``reminder_log``).
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional

import mailer
import notify
import service as svc
from i18n import tr

log = logging.getLogger("openplan.reminders")
SYSTEM = {"id": 0, "username": "system", "role": "admin"}
DEFAULTS = {"enabled": True, "hour": 7, "due_days": 2, "escalate_days": 3, "blocked_days": 3}


def settings(db) -> Dict[str, Any]:
    r = db.execute("SELECT value FROM app_settings WHERE key='reminders'").fetchone()
    return {**DEFAULTS, **(json.loads(r["value"]) if r else {})}


def save_settings(db, patch: Dict[str, Any]) -> Dict[str, Any]:
    s = settings(db)
    for k in DEFAULTS:
        if patch.get(k) is not None:
            s[k] = patch[k]
    if not (0 <= int(s["hour"]) <= 23):
        raise ValueError("Uhrzeit 0–23")
    for k, lo, hi in (("due_days", 0, 14), ("escalate_days", 1, 60), ("blocked_days", 1, 60)):
        if not (lo <= int(s[k]) <= hi):
            raise ValueError("%s: %d–%d" % (k, lo, hi))
    db.execute("INSERT INTO app_settings(key, value) VALUES ('reminders', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps(s),))
    return s


def _once(db, key: str) -> bool:
    """True, wenn die Meldung neu ist (und merkt sie sich)."""
    return db.execute("INSERT OR IGNORE INTO reminder_log(key) VALUES (?)", (key,)).rowcount == 1


def _when(L: str, delta: int) -> str:
    return tr(L, "heute") if delta == 0 else tr(L, "morgen") if delta == 1 else tr(L, "in %d Tagen", delta)


def check(db, today: Optional[dt.date] = None, base: str = "") -> Dict[str, int]:
    """Alle Projekte prüfen und Hinweise erzeugen. Liefert Zähler je Art."""
    today = today or dt.date.today()
    cfg = settings(db)
    counts = {"due": 0, "overdue": 0, "escalation": 0, "blocked": 0}
    mails: List[Dict[str, Any]] = []
    for p in db.execute("SELECT id, name, owner_id FROM projects").fetchall():
        pid, owner = p["id"], p["owner_id"]
        d = svc.load_project(db, pid, SYSTEM)
        res_user = {r["id"]: r.get("user_id") for r in d["resources"]}
        since = {r["id"]: r["status_since"] for r in db.execute("SELECT id, status_since FROM tasks WHERE project_id=?", (pid,))}
        for t in d["tasks"]:
            if t["summary"] or t["status"] == "done" or (t["duration"] <= 0 and not t["milestone"]):
                continue
            assignees = list(dict.fromkeys(res_user[r] for r in t["resource_ids"] if res_user.get(r)))
            end = t["deadline"] or t["finish"]                       # eine gesetzte Frist („bis“) hat Vorrang vor dem geplanten Ende
            finish = dt.date.fromisoformat(end)
            delta = (finish - today).days
            pname, tname, wbs, st, pct, ddl = p["name"], t["name"], t["wbs"], t["status"], round(t["percent"]), bool(t["deadline"])
            ST = {"open": "offen", "in_progress": "in Arbeit", "blocked": "blockiert", "done": "erledigt"}
            ctx = lambda L: tr(L, "Projekt: %s\nVorgang: %s %s\n%s: %s\nStatus: %s, %d %% fertig", pname, wbs, tname, tr(L, "Frist" if ddl else "Ende"), end, tr(L, ST.get(st, st)), pct)  # noqa: E731
            if 0 <= delta <= int(cfg["due_days"]) and _once(db, "due:%d:%s" % (t["id"], end)):
                who = assignees or ([owner] if owner and t["pool"] else [])
                if who:
                    mails += notify.create(db, who, pid, t["id"], "due", lambda L: tr(L, "Fällig %s: %s", _when(L, delta), tname), ctx, base)
                    counts["due"] += 1
            if delta < 0:
                late = -delta
                if assignees and _once(db, "overdue:%d:%s" % (t["id"], end)):
                    mails += notify.create(db, assignees, pid, t["id"], "overdue",
                                           lambda L: tr(L, "Überfällig seit %d Tag: %s" if late == 1 else "Überfällig seit %d Tagen: %s", late, tname), ctx, base)
                    counts["overdue"] += 1
                if late >= int(cfg["escalate_days"]) and owner and _once(db, "esc:%d:%s" % (t["id"], end)):
                    names = ", ".join(r["name"] for r in d["resources"] if r["id"] in t["resource_ids"])
                    mails += notify.create(db, [owner], pid, t["id"], "escalation", lambda L: tr(L, "Eskalation: seit %d Tagen überfällig – %s", late, tname),
                                           lambda L: ctx(L) + tr(L, "\nBearbeiter: ") + (names or tr(L, "niemand zugeordnet")), base)
                    counts["escalation"] += 1
            if t["status"] == "blocked" and since.get(t["id"]):
                days = (today - dt.date.fromisoformat(since[t["id"]][:10])).days
                if days >= int(cfg["blocked_days"]) and _once(db, "blk:%d:%s" % (t["id"], since[t["id"]][:10])):
                    who = list(dict.fromkeys(([owner] if owner else []) + assignees))
                    note = t["status_note"]
                    mails += notify.create(db, who, pid, t["id"], "blocked", lambda L: tr(L, "Blockiert seit %d Tagen: %s", days, tname),
                                           lambda L: ctx(L) + ((tr(L, "\nGrund: ") + note) if note else ""), base)
                    counts["blocked"] += 1
    db.execute("DELETE FROM reminder_log WHERE ts < datetime('now', '-180 days')")
    mailer.dispatch(db, mails)
    return counts


def run_due(now: Optional[dt.datetime] = None) -> Optional[Dict[str, int]]:
    from database import connect
    now = now or dt.datetime.now()
    db = connect()
    try:
        cfg = settings(db)
        if not cfg["enabled"] or now.hour < int(cfg["hour"]):
            return None
        r = db.execute("SELECT value FROM app_settings WHERE key='reminders_state'").fetchone()
        if r and json.loads(r["value"]).get("date") == now.date().isoformat():
            return None
        res = check(db, now.date(), mailer.base_url(db))
        db.execute("INSERT INTO app_settings(key, value) VALUES ('reminders_state', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                   (json.dumps({"date": now.date().isoformat(), "result": res}),))
        db.commit()
        log.info("Erinnerungen: %s", res)
        return res
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


_started = False


def start_background(interval: float = 1800.0) -> None:
    global _started
    if _started:
        return
    _started = True

    def loop():
        time.sleep(90)
        while True:
            try:
                run_due()
            except Exception:
                log.exception("Erinnerungen")
            time.sleep(interval)

    threading.Thread(target=loop, daemon=True, name="reminders").start()
