"""Automatisches Reporting: Projektstatus per E-Mail (und Glocke) nach Zeitplan oder auf Knopfdruck.

Je Projekt einstellbar (Verantwortlicher): aktiv, Wochentag, Uhrzeit, Empfänger (Verantwortlicher / alle Mitglieder).
Jeder Empfänger bekommt zusätzlich seine eigenen offenen Vorgänge (über die mit seinem Benutzer verknüpfte Ressource).
"""
from __future__ import annotations

import datetime as dt
import html
import logging
import threading
import time
from typing import Any, Dict, List, Optional

import mailer
import notify
import service as svc
from i18n import norm, tr

log = logging.getLogger("openplan.reports")
SYSTEM = {"id": 0, "username": "system", "role": "admin"}
WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
_STATUS = {"open": "offen", "in_progress": "in Arbeit", "blocked": "blockiert", "done": "erledigt"}


def build(db, pid: int, today: Optional[dt.date] = None) -> Dict[str, Any]:
    today = today or dt.date.today()
    iso, soon = today.isoformat(), (today + dt.timedelta(days=14)).isoformat()
    d = svc.load_project(db, pid, SYSTEM)
    leaves = [t for t in d["tasks"] if not t["summary"]]
    work = [t for t in leaves if t["duration"] > 0 or t["milestone"]]
    total_d = sum(max(t["duration"], 1) for t in work) or 1
    pct = sum(t["percent"] * max(t["duration"], 1) for t in work) / total_d
    res_user = {r["id"]: r.get("user_id") for r in d["resources"]}
    res_name = {r["id"]: r["name"] for r in d["resources"]}

    def row(t):
        return {"id": t["id"], "wbs": t["wbs"], "name": t["name"], "start": t["start"], "finish": t["finish"], "status": t["status"],
                "percent": round(t["percent"]), "note": t["status_note"], "who": ", ".join(res_name.get(r, "?") for r in t["resource_ids"]),
                "user_ids": [res_user.get(r) for r in t["resource_ids"] if res_user.get(r)]}

    undone = [t for t in work if t["status"] != "done"]
    rep = {
        "project": d["project"]["name"], "pid": pid, "date": iso, "finish": d["project"]["finish"],
        "owner": (lambda o: o.get("display_name") or o.get("username", ""))(d["project"].get("owner") or {}),
        "kpi": {"total": len(work), "done": sum(t["status"] == "done" for t in work), "in_progress": sum(t["status"] == "in_progress" for t in work),
                "blocked": sum(t["status"] == "blocked" for t in work), "open": sum(t["status"] == "open" for t in work),
                "percent": round(pct), "critical": sum(1 for t in undone if t["critical"]),
                "deadline_missed": sum(1 for t in work if t.get("deadline_missed"))},
        "overdue": [row(t) for t in sorted(undone, key=lambda t: t["finish"]) if t["finish"] < iso],
        "blocked": [row(t) for t in work if t["status"] == "blocked"],
        "upcoming": [row(t) for t in sorted(undone, key=lambda t: t["start"]) if t["start"] <= soon and t["finish"] >= iso],
        "pool": [row(t) for t in leaves if t["pool"] and not t["resource_ids"] and t["status"] != "done"],
        "_all": {t["id"]: row(t) for t in work},
    }
    return rep


def mine(rep: Dict[str, Any], user_id: int) -> List[Dict[str, Any]]:
    rows = [r for r in rep["_all"].values() if user_id in r["user_ids"] and r["status"] != "done"]
    return sorted(rows, key=lambda r: r["finish"])


def _fmt(d: str) -> str:
    return "%s.%s.%s" % (d[8:10], d[5:7], d[2:4]) if d else ""


def _status(L: str, s: str) -> str:
    return tr(L, _STATUS[s])


def render_text(rep: Dict[str, Any], base: str, user_id: Optional[int] = None, lang: str = "de") -> str:
    L = lang
    k, out = rep["kpi"], []
    link = lambda r: "  %s" % ((base + notify.link_for(rep["pid"], r["id"])) if base else "")  # noqa: E731
    out.append(tr(L, "Projektreport: %s (%s)", rep["project"], _fmt(rep["date"])))
    out.append(tr(L, "Fortschritt %d %% · %d von %d erledigt · %d in Arbeit · %d blockiert · %d überfällig · geplantes Ende %s",
                  k["percent"], k["done"], k["total"], k["in_progress"], k["blocked"], len(rep["overdue"]), _fmt(rep["finish"] or "")))
    sections = [(tr(L, "Deine offenen Vorgänge"), mine(rep, user_id) if user_id else []), (tr(L, "Überfällig"), rep["overdue"]),
                (tr(L, "Blockiert"), rep["blocked"]), (tr(L, "Anstehend (14 Tage)"), rep["upcoming"]), (tr(L, "Offen im Pool"), rep["pool"])]
    for title, rows in sections:
        if rows:
            out.append("\n%s (%d)" % (title, len(rows)))
            for r in rows[:30]:
                out.append(tr(L, "- %s %s [%s, bis %s%s]%s\n%s", r["wbs"], r["name"], _status(L, r["status"]), _fmt(r["finish"]),
                              ", " + r["who"] if r["who"] else "", " – " + r["note"] if r["note"] else "", link(r)))
    if base:
        out.append(tr(L, "\nProjekt öffnen: %s", base + notify.link_for(rep["pid"])))
    out.append(tr(L, "\n— OpenPlan (automatischer Report)"))
    return "\n".join(out)


def render_html(rep: Dict[str, Any], base: str, user_id: Optional[int] = None, lang: str = "de") -> str:
    L = lang
    e, k = html.escape, rep["kpi"]
    href = lambda r: e((base + notify.link_for(rep["pid"], r["id"])) if base else "#", quote=True)  # noqa: E731

    def table(title, rows, color):
        if not rows:
            return ""
        trs = "".join("<tr><td style=\"padding:3px 8px\">%s</td><td style=\"padding:3px 8px\"><a href=\"%s\">%s</a>%s</td>"
                      "<td style=\"padding:3px 8px\">%s</td><td style=\"padding:3px 8px\">%s</td><td style=\"padding:3px 8px\">%s</td></tr>" % (
                          e(r["wbs"]), href(r), e(r["name"]), ("<br><small style=\"color:#b45309\">%s</small>" % e(r["note"])) if r["note"] else "",
                          _status(L, r["status"]), _fmt(r["finish"]), e(r["who"])) for r in rows[:30])
        more = "<p style=\"color:#6b7280\">%s</p>" % tr(L, "… und %d weitere", len(rows) - 30) if len(rows) > 30 else ""
        return ("<h4 style=\"margin:16px 0 4px;color:%s\">%s (%d)</h4><table style=\"border-collapse:collapse;font-size:13px\">"
                "<tr style=\"background:#f3f4f6;text-align:left\"><th style=\"padding:3px 8px\">%s</th><th style=\"padding:3px 8px\">%s</th>"
                "<th style=\"padding:3px 8px\">%s</th><th style=\"padding:3px 8px\">%s</th><th style=\"padding:3px 8px\">%s</th></tr>%s</table>%s" % (
                    color, e(title), len(rows), tr(L, "PSP"), tr(L, "Vorgang"), tr(L, "Status"), tr(L, "Ende"), tr(L, "Bearbeiter"), trs, more))

    kp = "".join("<td style=\"padding:6px 14px;text-align:center\"><div style=\"font-size:22px;font-weight:600;color:%s\">%s</div><div style=\"font-size:11px;color:#6b7280\">%s</div></td>" % (c, v, lbl)
                 for v, lbl, c in ((str(k["percent"]) + " %", tr(L, "Fortschritt"), "#2563eb"), (k["done"], tr(L, "erledigt"), "#16a34a"), (k["in_progress"], tr(L, "in Arbeit"), "#2563eb"),
                                   (k["blocked"], tr(L, "blockiert"), "#d97706"), (len(rep["overdue"]), tr(L, "überfällig"), "#dc2626")))
    btn = ("<p><a href=\"%s\" style=\"background:#2563eb;color:#fff;padding:8px 14px;border-radius:6px;text-decoration:none\">%s</a></p>"
           % (e(base + notify.link_for(rep["pid"]), quote=True), tr(L, "Projekt öffnen"))) if base else ""
    return ("<div style=\"font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#1f2937\"><h2 style=\"margin:0\">%s</h2>"
            "<p style=\"color:#6b7280;margin:2px 0 10px\">%s</p>"
            "<table style=\"border:1px solid #e5e7eb;border-radius:8px\"><tr>%s</tr></table>%s%s%s%s%s%s"
            "<p style=\"color:#6b7280;font-size:12px;margin-top:18px\">%s</p></div>" % (
                tr(L, "Projektreport: %s", e(rep["project"])),
                tr(L, "Stand %s · geplantes Ende %s · Verantwortlich: %s", _fmt(rep["date"]), _fmt(rep["finish"] or ""), e(rep["owner"])), kp,
                table(tr(L, "Deine offenen Vorgänge"), mine(rep, user_id) if user_id else [], "#2563eb"), table(tr(L, "Überfällig"), rep["overdue"], "#dc2626"),
                table(tr(L, "Blockiert"), rep["blocked"], "#d97706"), table(tr(L, "Anstehend (14 Tage)"), rep["upcoming"], "#1f2937"),
                table(tr(L, "Offen im Pool (zur Selbstübernahme)"), rep["pool"], "#1f2937"), btn, tr(L, "Automatischer Report von OpenPlan.")))


def recipients(db, pid: int) -> List[Dict[str, Any]]:
    p = db.execute("SELECT owner_id, report_to FROM projects WHERE id=?", (pid,)).fetchone()
    ids = [p["owner_id"]] if p["owner_id"] else []
    if p["report_to"] == "members":
        ids += [r["user_id"] for r in db.execute("SELECT user_id FROM project_members WHERE project_id=?", (pid,))]
    out = []
    for uid in dict.fromkeys(ids):
        u = db.execute("SELECT id, username, display_name, email, notify_email, lang FROM users WHERE id=?", (uid,)).fetchone()
        if u:
            out.append(dict(u))
    return out


def send_report(db, pid: int, base: str = "", today: Optional[dt.date] = None) -> Dict[str, int]:
    """Report an alle Empfänger: Glocke immer, E-Mail wenn Mailversand konfiguriert und Adresse hinterlegt (Sprache je Empfänger)."""
    rep = build(db, pid, today)
    base = mailer.base_url(db, base)
    k = rep["kpi"]
    mails, notified, no_mail = [], 0, 0
    can_mail = mailer.configured(db)
    for u in recipients(db, pid):
        L = norm(u.get("lang"))
        title = tr(L, "Projektreport %s: %d %% fertig, %d überfällig, %d blockiert", rep["project"], k["percent"], len(rep["overdue"]), k["blocked"])
        db.execute("INSERT INTO notifications(user_id, project_id, task_id, kind, title, body, link) VALUES (?,?,?,?,?,?,?)",
                   (u["id"], pid, None, "report", title[:200], tr(L, "Stand %s", _fmt(rep["date"])), notify.link_for(pid)))
        notified += 1
        if can_mail and u["email"] and u["notify_email"]:
            mails.append({"to": u["email"], "subject": title, "text": render_text(rep, base, u["id"], L), "html": render_html(rep, base, u["id"], L)})
        elif can_mail:
            no_mail += 1
    mailer.dispatch(db, mails)
    db.execute("UPDATE projects SET report_last=? WHERE id=?", ((today or dt.date.today()).isoformat(), pid))
    return {"notified": notified, "mails": len(mails), "without_email": no_mail}


def due(db, now: Optional[dt.datetime] = None) -> List[int]:
    now = now or dt.datetime.now()
    rows = db.execute("SELECT id, report_weekday, report_hour, report_last FROM projects WHERE report_enabled=1").fetchall()
    return [r["id"] for r in rows if r["report_weekday"] == now.weekday() and now.hour >= r["report_hour"] and r["report_last"] != now.date().isoformat()]


def run_due(now: Optional[dt.datetime] = None) -> int:
    from database import connect
    db = connect()
    n = 0
    try:
        for pid in due(db, now):
            try:
                r = send_report(db, pid, today=(now or dt.datetime.now()).date())
                db.commit()
                n += 1
                log.info("Report für Projekt %d verschickt: %s", pid, r)
            except Exception:
                db.rollback()
                log.exception("Report für Projekt %d fehlgeschlagen", pid)
        import notify as _n
        _n.prune(db)
        db.commit()
    finally:
        db.close()
    return n


_started = False


def start_background(interval: float = 300.0) -> None:
    global _started
    if _started:
        return
    _started = True

    def loop():
        time.sleep(60)
        while True:
            try:
                run_due()
                import portfolio
                portfolio.run_due()
            except Exception:
                log.exception("Report-Scheduler")
            time.sleep(interval)

    threading.Thread(target=loop, daemon=True, name="reports").start()
