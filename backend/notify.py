"""In-App-Benachrichtigungen (Glocke) und E-Mails bei Zuteilung/Reports. Jede Nachricht trägt einen Link zum Vorgang/Projekt.

Texte (``title``/``body``) dürfen ``str`` oder ``lambda L: tr(L, …)`` sein und werden je Empfänger in dessen Sprache
(``users.lang``) erzeugt – siehe ``i18n.py``.
"""
from __future__ import annotations

import html
from typing import Any, Dict, Iterable, List, Optional

import mailer
from i18n import Msg, norm, render, tr


def link_for(pid: int, task_id: Optional[int] = None) -> str:
    return "/project/%d%s" % (pid, "?task=%d" % task_id if task_id else "")


def create(db, user_ids: Iterable[int], pid: int, task_id: Optional[int], kind: str, title: Msg, body: Msg = "",
           base: str = "", email_html_extra: str = "", send_email: bool = True) -> List[Dict[str, Any]]:
    """Benachrichtigung je Benutzer anlegen. Liefert die zu versendenden Mails (an ``mailer.dispatch`` übergeben)."""
    link = link_for(pid, task_id)
    mails: List[Dict[str, Any]] = []
    can_mail = send_email and mailer.configured(db)
    abs_base = mailer.base_url(db, base)
    for uid in dict.fromkeys(user_ids):
        u = db.execute("SELECT email, notify_email, lang FROM users WHERE id=?", (uid,)).fetchone()
        L = norm(u["lang"] if u else None)
        t, b = render(title, L), render(body, L)
        db.execute("INSERT INTO notifications(user_id, project_id, task_id, kind, title, body, link) VALUES (?,?,?,?,?,?,?)",
                   (uid, pid, task_id, kind, t[:200], b[:1000], link))
        if can_mail and u and u["email"] and u["notify_email"]:
            url = (abs_base + link) if abs_base else link
            text = "%s\n\n%s\n\n%s\n\n%s" % (t, b, tr(L, "Öffnen: %s", url), tr(L, "— OpenPlan (automatische Nachricht)"))
            htm = ("<div style=\"font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#1f2937\"><h3 style=\"margin:0 0 8px\">%s</h3>"
                   "<p style=\"white-space:pre-line\">%s</p>%s<p><a href=\"%s\" style=\"background:#2563eb;color:#fff;padding:8px 14px;"
                   "border-radius:6px;text-decoration:none\">%s</a></p>"
                   "<p style=\"color:#6b7280;font-size:12px\">%s</p></div>"
                   % (html.escape(t), html.escape(b), email_html_extra, html.escape(url, quote=True),
                      tr(L, "In OpenPlan öffnen"), tr(L, "Automatische Nachricht von OpenPlan.")))
            mails.append({"to": u["email"], "subject": t, "text": text, "html": htm})
    return mails


def assignment_changes(db, task, old_ids: set, new_ids: set, actor: Dict[str, Any], base: str = "", info: str = "") -> List[Dict[str, Any]]:
    """Zuteilung/Entzug an verknüpfte Benutzer melden (nicht an den auslösenden Benutzer selbst)."""
    pid = task["project_id"]
    proj = db.execute("SELECT name FROM projects WHERE id=?", (pid,)).fetchone()["name"]

    def users(rids):
        if not rids:
            return []
        q = "SELECT DISTINCT user_id FROM resources WHERE user_id IS NOT NULL AND id IN (%s)" % ",".join("?" * len(rids))
        return [r["user_id"] for r in db.execute(q, list(rids)) if r["user_id"] != actor["id"]]

    pool = bool(task["pool"])
    name, who = task["name"], actor.get("display_name") or actor["username"]
    kind = lambda L: tr(L, "Arbeitspaket" if pool else "Vorgang")  # noqa: E731
    mails: List[Dict[str, Any]] = []
    added, removed = new_ids - old_ids, old_ids - new_ids
    mails += create(db, users(added), pid, task["id"], "assigned", lambda L: tr(L, "%s zugeteilt: %s", kind(L), name),
                    lambda L: tr(L, "Projekt: %s\n%s: %s\nZugeteilt von: %s", proj, kind(L), name, who), base)
    mails += create(db, users(removed), pid, task["id"], "unassigned", lambda L: tr(L, "Zuteilung entfernt: %s", name),
                    lambda L: tr(L, "Projekt: %s\n%s: %s\nGeändert von: %s", proj, kind(L), name, who), base)
    return mails


def list_for(db, user_id: int, limit: int = 50) -> Dict[str, Any]:
    rows = [dict(r) for r in db.execute("SELECT n.*, p.name AS project_name FROM notifications n LEFT JOIN projects p ON p.id=n.project_id "
                                        "WHERE n.user_id=? ORDER BY n.id DESC LIMIT ?", (user_id, limit))]
    unread = db.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND read_at IS NULL", (user_id,)).fetchone()[0]
    return {"unread": unread, "items": rows}


def prune(db, days: int = 90) -> None:
    db.execute("DELETE FROM notifications WHERE created_at < datetime('now', ?)", ("-%d days" % days,))
