from __future__ import annotations

from datetime import date, timedelta
import asyncio
import json
import logging
import secrets
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse

import access
import demo
import demo_kit
import feiertage
import acme_client
import audit
import backup
import files_api
import history
from i18n import tr
import finance_api
import io_formats
import ldap_auth
import mailer
import notify
import portfolio
import reminders
import webhooks
import reports
import settings
import service as svc
from auth import (create_token, current_user, label, hash_password, require_admin,
                  require_editor, verify_password)
from database import connect, get_db
from schemas import (AbsenceIn, AdminPasswordIn, BackupSettingsIn, DisplayNameIn, ReportsToIn, RoleIn, SeeAllIn, WizardIn, ReminderSettingsIn, AcmeFetchCaIn, AcmeSettingsIn, CostOwnerIn, MailSettingsIn, MailTestIn, ProfileIn, ReportSubIn, AssignIn, BulkStatusIn, LdapSettingsIn, LdapTestIn, LoginIn, MemberIn, MoveIn, PasswordIn, PredIn, ProjectIn, ProjectPatch,
                     ResourceIn, ShiftIn, TaskIn, TaskPatch, UserIn)

router = APIRouter(prefix="/api", dependencies=[Depends(history.record, scope="function")])
_audit = logging.getLogger("openplan.audit")


# ── Auth / Benutzer ─────────────────────────────────────────────────────────
def _ldap_user(db, info, row):
    """Lokales Konto zu einem erfolgreich authentifizierten AD-Benutzer anlegen bzw. Admin-Rolle abgleichen."""
    import config
    row = row or db.execute("SELECT * FROM users WHERE username=?", (info["username"],)).fetchone()
    if row and row["auth_source"] != "ldap":
        raise HTTPException(401, "Benutzername oder Passwort falsch")
    default = config.LDAP_DEFAULT_ROLE if config.LDAP_DEFAULT_ROLE in ("editor", "viewer") else "editor"
    if not row:
        if not config.LDAP_AUTO_CREATE:
            raise HTTPException(403, "Kein OpenPlan-Konto vorhanden – bitte vom Administrator anlegen lassen")
        aud = bool(info.get("auditor")) and not info["admin"]
        role = "admin" if info["admin"] else "viewer" if aud else default
        cur = db.execute("INSERT INTO users(username, display_name, password_hash, role, auth_source, email, see_all) VALUES (?,?,?,?, 'ldap', ?, ?)",
                         (info["username"], info.get("display", ""), "ldap$" + secrets.token_hex(16), role, info.get("email", ""), int(aud)))
        return db.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
    if info.get("display") and info["display"] != row["display_name"]:     # Anzeigename folgt dem AD
        db.execute("UPDATE users SET display_name=? WHERE id=?", (info["display"], row["id"]))
        row = db.execute("SELECT * FROM users WHERE id=?", (row["id"],)).fetchone()
    if info.get("email") and not row["email"]:                     # fehlende Mailadresse aus dem AD ergänzen
        db.execute("UPDATE users SET email=? WHERE id=?", (info["email"], row["id"]))
        row = db.execute("SELECT * FROM users WHERE id=?", (row["id"],)).fetchone()
    if config.LDAP_ADMIN_GROUP:                                    # die Admin-Gruppe steuert nur die Admin-Rolle
        if info["admin"] and row["role"] != "admin":
            db.execute("UPDATE users SET role='admin' WHERE id=?", (row["id"],))
        elif not info["admin"] and row["role"] == "admin":
            db.execute("UPDATE users SET role=? WHERE id=?", (default, row["id"]))
        row = db.execute("SELECT * FROM users WHERE id=?", (row["id"],)).fetchone()
    if config.LDAP_AUDITOR_GROUP and row["role"] != "admin":       # Betrachter-Gruppe steuert „viewer + alle Projekte sehen“
        if info.get("auditor") and not (row["role"] == "viewer" and row["see_all"]):
            db.execute("UPDATE users SET role='viewer', see_all=1 WHERE id=?", (row["id"],))
        elif not info.get("auditor") and row["see_all"]:
            db.execute("UPDATE users SET role=?, see_all=0 WHERE id=?", (default, row["id"]))
        row = db.execute("SELECT * FROM users WHERE id=?", (row["id"],)).fetchone()
    return row


@router.post("/auth/login")
def login(body: LoginIn, request: Request, db=Depends(get_db, scope="function")):
    ip = audit.ip_of(request)

    def fail(why: str):
        audit.log_now(body.username[:64], "login.fail", why, ip)          # eigene Verbindung: bleibt trotz Abbruch erhalten
        raise HTTPException(401, "Benutzername oder Passwort falsch")

    row = db.execute("SELECT * FROM users WHERE username=?", (body.username,)).fetchone()
    settings.apply(db)                                                         # in der Verwaltung gepflegte LDAP-Werte
    if ldap_auth.enabled() and (not row or row["auth_source"] == "ldap"):     # lokale Konten bleiben rein lokal
        info = ldap_auth.authenticate(body.username, body.password)
        if not info:
            fail("AD-Anmeldung abgelehnt")
        row = _ldap_user(db, info, row)
    elif not row or row["auth_source"] == "ldap" or not verify_password(body.password, row["password_hash"]):
        fail("Benutzer unbekannt" if not row else "falsches Passwort")
    audit.log(db, row["username"], "login", row["auth_source"], ip)
    return {"token": create_token(row["id"], row["username"], row["role"], row["token_version"]),
            "user": {"id": row["id"], "username": row["username"], "display_name": row["display_name"], "role": row["role"],
                     "email": row["email"], "notify_email": row["notify_email"], "lang": row["lang"], "theme": row["theme"], "see_all": row["see_all"]}}


@router.get("/auth/me")
def me(user=Depends(current_user)):
    return user


@router.post("/auth/password")
def change_password(body: PasswordIn, request: Request, user=Depends(current_user), db=Depends(get_db, scope="function")):
    row = db.execute("SELECT password_hash, auth_source, token_version FROM users WHERE id=?", (user["id"],)).fetchone()
    if row["auth_source"] == "ldap":
        raise HTTPException(400, "Das Passwort wird im Active Directory verwaltet")
    if not verify_password(body.old_password, row["password_hash"]):
        raise HTTPException(400, "Altes Passwort falsch")
    ver = row["token_version"] + 1                           # alle anderen Sitzungen enden; diese bekommt ein neues Token
    db.execute("UPDATE users SET password_hash=?, token_version=? WHERE id=?", (hash_password(body.new_password), ver, user["id"]))
    audit.log(db, user, "password.change", "", audit.ip_of(request))
    return {"ok": True, "token": create_token(user["id"], user["username"], user["role"], ver)}


@router.get("/users")
def list_users(_=Depends(require_admin), db=Depends(get_db, scope="function")):
    return [dict(r) for r in db.execute("SELECT id, username, display_name, role, created_at, auth_source, email, notify_email, see_all FROM users ORDER BY lower(COALESCE(NULLIF(display_name, ''), username))")]


@router.get("/admin/settings/ldap")
def get_ldap_settings(_=Depends(require_admin), db=Depends(get_db, scope="function")):
    return settings.public(db)


@router.put("/admin/settings/ldap")
def put_ldap_settings(body: LdapSettingsIn, user=Depends(require_admin), db=Depends(get_db, scope="function")):
    out = settings.save(db, body.model_dump(exclude_unset=True))
    audit.log(db, user, "settings.ldap.save", "aktiv=%s, url=%s, Pflichtgruppe=%s" % (out["enabled"], out["url"], out["required_group"] or "-"))
    return out


@router.post("/admin/settings/ldap/test")
def test_ldap_settings(body: LdapTestIn, _=Depends(require_admin), db=Depends(get_db, scope="function")):
    """Verbindungstest mit den (ggf. ungespeicherten) Formularwerten; ``enabled`` wird dafür vorausgesetzt."""
    patch = body.settings.model_dump(exclude_unset=True) if body.settings else {}
    patch["enabled"] = True
    with settings.override(db, patch):
        return ldap_auth.diagnose(body.username, body.password)


# ── Server-Zertifikat (ACME) ────────────────────────────────────────────────
@router.get("/admin/tls")
def get_tls(_=Depends(require_admin), db=Depends(get_db, scope="function")):
    return acme_client.public(db)


@router.put("/admin/tls")
def put_tls(body: AcmeSettingsIn, user=Depends(require_admin), db=Depends(get_db, scope="function")):
    out = acme_client.save_settings(db, body.model_dump(exclude_unset=True))
    audit.log(db, user, "settings.acme.save", "Domains: %s" % ", ".join(out["settings"]["domains"]))
    return out


@router.post("/admin/tls/fetch-ca")
def fetch_tls_ca(body: AcmeFetchCaIn, _=Depends(require_admin)):
    """CA-Kette (PEM) von einer URL abrufen und prüfen; wird erst mit „Speichern“ übernommen."""
    return acme_client.fetch_ca_chain(body.url.strip())


@router.post("/admin/tls/issue", status_code=202)
def issue_tls(user=Depends(require_admin), db=Depends(get_db, scope="function")):
    """Zertifikat jetzt anfordern/erneuern (läuft im Hintergrund; Status über GET /admin/tls)."""
    if not acme_client.settings(db)["domains"]:
        raise HTTPException(422, "Zuerst mindestens eine Domain eintragen und speichern")
    if not acme_client.start_issue_thread("manuell"):
        raise HTTPException(409, "Es läuft bereits eine Zertifikatsanforderung")
    audit.log(db, user, "tls.issue", "Domains: %s" % ", ".join(acme_client.settings(db)["domains"]))
    return {"started": True}


@router.get("/admin/tls/cert")
def download_tls_cert(_=Depends(require_admin)):
    """Öffentliche Zertifikatskette (nie der private Schlüssel)."""
    if not acme_client.CERT_FILE.exists():
        raise HTTPException(404, "Noch kein Zertifikat vorhanden")
    return Response(acme_client.CERT_FILE.read_bytes(), media_type="application/x-pem-file",
                    headers={"Content-Disposition": 'attachment; filename="openplan-fullchain.pem"'})


@router.put("/auth/profile")
def put_profile(body: ProfileIn, user=Depends(current_user), db=Depends(get_db, scope="function")):
    d = body.model_dump(exclude_unset=True)
    if d.get("email") is not None:
        email = d["email"].strip()
        if email and not mailer._EMAIL.match(email):
            raise HTTPException(422, "E-Mail-Adresse ungültig")
        db.execute("UPDATE users SET email=? WHERE id=?", (email, user["id"]))
    if d.get("notify_email") is not None:
        db.execute("UPDATE users SET notify_email=? WHERE id=?", (int(d["notify_email"]), user["id"]))
    if d.get("lang") is not None:
        db.execute("UPDATE users SET lang=? WHERE id=?", (d["lang"], user["id"]))
    if d.get("theme") is not None:
        db.execute("UPDATE users SET theme=? WHERE id=?", (d["theme"], user["id"]))
    r = db.execute("SELECT id, username, display_name, role, email, notify_email, lang, theme, see_all FROM users WHERE id=?", (user["id"],)).fetchone()
    return dict(r)


@router.put("/users/{uid}/email")
def admin_set_email(uid: int, body: ProfileIn, _=Depends(require_admin), db=Depends(get_db, scope="function")):
    email = (body.email or "").strip()
    if email and not mailer._EMAIL.match(email):
        raise HTTPException(422, "E-Mail-Adresse ungültig")
    if not db.execute("SELECT 1 FROM users WHERE id=?", (uid,)).fetchone():
        raise HTTPException(404, "Benutzer nicht gefunden")
    db.execute("UPDATE users SET email=? WHERE id=?", (email, uid))
    audit.log(db, _, "user.email", "Benutzer-ID %d" % uid)
    return {"ok": True}


# ── Meine Aufgaben (projektübergreifende To-do-Liste) ───────────────────────
@router.get("/my-tasks")
def my_tasks(user=Depends(current_user), db=Depends(get_db, scope="function")):
    """Offene Vorgänge, die dem Benutzer über seine verknüpfte Ressource zugeordnet sind – über alle Projekte, nach Ende sortiert.
    ``pool`` zählt offene Arbeitspakete (ohne Bearbeiter) in Projekten, in denen der Benutzer Verantwortlicher oder Mitglied ist."""
    today = date.today().isoformat()
    soon = (date.today() + timedelta(days=7)).isoformat()
    pids = [r["project_id"] for r in db.execute("SELECT DISTINCT project_id FROM resources WHERE user_id=?", (user["id"],))]
    items = []
    for pid in pids:
        d = svc.load_project(db, pid, user)
        mine = {r["id"] for r in d["resources"] if r.get("user_id") == user["id"]}
        for t in d["tasks"]:
            if t["summary"] or t["status"] == "done" or not (mine & set(t["resource_ids"])):
                continue
            end = t["deadline"] or t["finish"]
            items.append({"pid": pid, "project": d["project"]["name"], "id": t["id"], "wbs": t["wbs"], "name": t["name"], "start": t["start"],
                          "finish": t["finish"], "deadline": t["deadline"], "status": t["status"], "status_note": t["status_note"],
                          "percent": round(t["percent"]), "critical": bool(t["critical"]), "milestone": bool(t["milestone"]),
                          "bucket": "overdue" if end < today else "week" if end <= soon else "later"})
    items.sort(key=lambda i: (i["deadline"] or i["finish"], i["project"], i["wbs"]))
    pool = db.execute("SELECT COUNT(*) FROM tasks t JOIN projects p ON p.id=t.project_id WHERE t.pool=1 AND t.status!='done' "
                      "AND NOT EXISTS (SELECT 1 FROM assignments a WHERE a.task_id=t.id) "
                      "AND (p.owner_id=? OR EXISTS (SELECT 1 FROM project_members m WHERE m.project_id=p.id AND m.user_id=?))",
                      (user["id"], user["id"])).fetchone()[0]
    return {"items": items, "pool": pool, "today": today}


# ── Benachrichtigungen (Glocke) ─────────────────────────────────────────────
@router.get("/notifications")
def get_notifications(user=Depends(current_user), db=Depends(get_db, scope="function")):
    return notify.list_for(db, user["id"])


@router.post("/notifications/read-all")
def read_all_notifications(user=Depends(current_user), db=Depends(get_db, scope="function")):
    db.execute("UPDATE notifications SET read_at=datetime('now') WHERE user_id=? AND read_at IS NULL", (user["id"],))
    return notify.list_for(db, user["id"])


@router.post("/notifications/{nid}/read")
def read_notification(nid: int, user=Depends(current_user), db=Depends(get_db, scope="function")):
    db.execute("UPDATE notifications SET read_at=datetime('now') WHERE id=? AND user_id=? AND read_at IS NULL", (nid, user["id"]))
    return notify.list_for(db, user["id"])


# ── Mailversand (Verwaltung) ────────────────────────────────────────────────
@router.get("/admin/settings/mail")
def get_mail_settings(_=Depends(require_admin), db=Depends(get_db, scope="function")):
    return mailer.public(db)


@router.put("/admin/settings/mail")
def put_mail_settings(body: MailSettingsIn, user=Depends(require_admin), db=Depends(get_db, scope="function")):
    out = mailer.save(db, body.model_dump(exclude_unset=True))
    audit.log(db, user, "settings.mail.save", "aktiv=%s, Server=%s" % (out["enabled"], out["host"]))
    return out


@router.post("/admin/settings/mail/test")
def test_mail_settings(body: MailTestIn, user=Depends(require_admin), db=Depends(get_db, scope="function")):
    """Testmail mit den gespeicherten Einstellungen; Fehler werden samt Ursache zurückgegeben."""
    if not mailer._EMAIL.match(body.to.strip()):
        raise HTTPException(422, "Empfängeradresse ungültig")
    s = mailer.settings(db)
    if not (s["host"] and s["from_addr"]):
        raise HTTPException(422, "Zuerst SMTP-Server und Absender speichern")
    try:
        L = user.get("lang")
        mailer.send_now(s, body.to.strip(), tr(L, "OpenPlan: Testnachricht"), tr(L, "Wenn du diese Nachricht liest, funktioniert der Mailversand von OpenPlan.\n\nGesendet von %s.", user["username"]))
    except Exception as e:
        return {"ok": False, "message": "%s: %s" % (type(e).__name__, e)}
    return {"ok": True, "message": "Testmail an %s gesendet" % body.to.strip()}


# ── Projektreport (je Projekt) ──────────────────────────────────────────────
@router.get("/projects/{pid}/report/preview")
def report_preview(pid: int, request: Request, user=Depends(access.proj("owner")), db=Depends(get_db, scope="function")):
    rep = reports.build(db, pid)
    base = mailer.base_url(db, str(request.base_url))
    L = user.get("lang")
    return {"html": reports.render_html(rep, base, user["id"], L), "text": reports.render_text(rep, base, user["id"], L),
            "recipients": [{"username": label(u), "email": u["email"]} for u in reports.recipients(db, pid)]}


@router.post("/projects/{pid}/report/send")
def report_send(pid: int, request: Request, user=Depends(access.proj("owner")), db=Depends(get_db, scope="function")):
    r = reports.send_report(db, pid, str(request.base_url))
    svc.log(db, pid, user, "Report verschickt", "%d Empfänger, %d E-Mails" % (r["notified"], r["mails"]))
    return r


# ── Übergreifende Reports (Vorgesetzte / Kostenstellenverantwortliche) ───────
def _sub_out(db, r):
    d = dict(r)
    u = db.execute("SELECT username, display_name, email FROM users WHERE id=?", (d["user_id"],)).fetchone()
    d["username"], d["display_name"], d["email"] = (u["username"], u["display_name"], u["email"]) if u else ("?", "", "")
    d["project_ids"] = [int(x) for x in d["project_ids"].split(",") if x.strip()]
    return d


def _check_sub(db, body: ReportSubIn) -> None:
    if not db.execute("SELECT 1 FROM users WHERE id=?", (body.user_id,)).fetchone():
        raise HTTPException(422, "Benutzer nicht gefunden")
    for pid in body.project_ids:
        if not db.execute("SELECT 1 FROM projects WHERE id=?", (pid,)).fetchone():
            raise HTTPException(422, "Projekt %d existiert nicht" % pid)


@router.get("/admin/reports")
def admin_reports(_=Depends(require_admin), db=Depends(get_db, scope="function")):
    return {
        "subscriptions": [_sub_out(db, r) for r in db.execute("SELECT * FROM report_subscriptions ORDER BY id")],
        "owners": [dict(r) for r in db.execute("SELECT o.code, o.name, o.user_id, u.username, u.display_name FROM cost_center_owners o JOIN users u ON u.id=o.user_id ORDER BY o.code")],
        "projects": [dict(r) for r in db.execute("SELECT id, name FROM projects ORDER BY name")],
        "known_codes": [r["code"] for r in db.execute("SELECT DISTINCT code FROM cost_centers ORDER BY code")],
    }


@router.post("/admin/reports", status_code=201)
def admin_report_create(body: ReportSubIn, user=Depends(require_admin), db=Depends(get_db, scope="function")):
    _check_sub(db, body)
    cur = db.execute("INSERT INTO report_subscriptions(user_id, kind, name, project_ids, include_costs, weekday, hour, enabled) VALUES (?,?,?,?,?,?,?,?)",
                     (body.user_id, body.kind, body.name.strip(), ",".join(map(str, body.project_ids)), int(body.include_costs), body.weekday, body.hour, int(body.enabled)))
    audit.log(db, user, "report.create", "#%d %s für Benutzer-ID %d" % (cur.lastrowid, body.kind, body.user_id))
    return _sub_out(db, db.execute("SELECT * FROM report_subscriptions WHERE id=?", (cur.lastrowid,)).fetchone())


@router.put("/admin/reports/{sid}")
def admin_report_update(sid: int, body: ReportSubIn, user=Depends(require_admin), db=Depends(get_db, scope="function")):
    _check_sub(db, body)
    if not db.execute("SELECT 1 FROM report_subscriptions WHERE id=?", (sid,)).fetchone():
        raise HTTPException(404, "Report nicht gefunden")
    db.execute("UPDATE report_subscriptions SET user_id=?, kind=?, name=?, project_ids=?, include_costs=?, weekday=?, hour=?, enabled=? WHERE id=?",
               (body.user_id, body.kind, body.name.strip(), ",".join(map(str, body.project_ids)), int(body.include_costs), body.weekday, body.hour, int(body.enabled), sid))
    audit.log(db, user, "report.update", "#%d" % sid)
    return _sub_out(db, db.execute("SELECT * FROM report_subscriptions WHERE id=?", (sid,)).fetchone())


@router.delete("/admin/reports/{sid}")
def admin_report_delete(sid: int, user=Depends(require_admin), db=Depends(get_db, scope="function")):
    audit.log(db, user, "report.delete", "#%d" % sid)
    db.execute("DELETE FROM report_subscriptions WHERE id=?", (sid,))
    db.execute("DELETE FROM notifications WHERE link=?", ("/reports/%d" % sid,))
    return {"ok": True}


@router.post("/admin/reports/{sid}/send")
def admin_report_send(sid: int, request: Request, _=Depends(require_admin), db=Depends(get_db, scope="function")):
    if not db.execute("SELECT 1 FROM report_subscriptions WHERE id=?", (sid,)).fetchone():
        raise HTTPException(404, "Report nicht gefunden")
    return portfolio.send(db, sid, str(request.base_url))


@router.put("/admin/cost-owners")
def admin_cost_owners(items: List[CostOwnerIn], user=Depends(require_admin), db=Depends(get_db, scope="function")):
    codes = [portfolio._norm(i.code) for i in items]
    if len(set(codes)) != len(codes):
        raise HTTPException(422, "Jede Kostenstelle darf nur einen Verantwortlichen haben")
    for i in items:
        if not db.execute("SELECT 1 FROM users WHERE id=?", (i.user_id,)).fetchone():
            raise HTTPException(422, "Benutzer nicht gefunden")
    db.execute("DELETE FROM cost_center_owners")
    for i in items:
        db.execute("INSERT INTO cost_center_owners(code, name, user_id) VALUES (?,?,?)", (i.code.strip(), i.name.strip(), i.user_id))
    audit.log(db, user, "costowners.save", ", ".join("%s→%d" % (i.code, i.user_id) for i in items)[:400])
    return admin_reports(None, db)


@router.get("/reports/mine")
def my_reports(user=Depends(current_user), db=Depends(get_db, scope="function")):
    return [{"id": r["id"], "kind": r["kind"], "name": r["name"], "last_sent": r["last_sent"], "weekday": r["weekday"], "hour": r["hour"]}
            for r in db.execute("SELECT * FROM report_subscriptions WHERE user_id=? AND enabled=1 ORDER BY id", (user["id"],))]


@router.get("/reports/{sid}")
def view_report(sid: int, request: Request, user=Depends(current_user), db=Depends(get_db, scope="function")):
    sub = db.execute("SELECT * FROM report_subscriptions WHERE id=?", (sid,)).fetchone()
    if not sub or (sub["user_id"] != user["id"] and user["role"] != "admin"):
        raise HTTPException(404, "Report nicht gefunden")
    L = user.get("lang")
    rep = portfolio.build(db, sub, lang=L)
    base = mailer.base_url(db, str(request.base_url))
    return {"id": sid, "title": rep["title"], "html": portfolio.render_html(rep, base, sid, L), "text": portfolio.render_text(rep, base, sid, L)}


@router.get("/users/directory")
def user_directory(q: str = "", limit: int = 0, _=Depends(current_user), db=Depends(get_db, scope="function")):
    """Schlanke Benutzerliste (für Verantwortlichen-/Mitglieder-/Zuordnungsauswahl); ohne Admin-Rechte.
    Mit ``q`` wird nach ID, Anzeigename und E-Mail gesucht, ``limit`` begrenzt die Treffer (0 = alle)."""
    sql, args = "SELECT id, username, display_name, role FROM users", []
    words = [w for w in q.lower().split() if w]
    if words:
        sql += " WHERE " + " AND ".join("(lower(username) LIKE ? OR lower(display_name) LIKE ? OR lower(email) LIKE ?)" for _ in words)
        for w in words:
            args += ["%" + w + "%"] * 3
    sql += " ORDER BY lower(COALESCE(NULLIF(display_name, ''), username))" + (" LIMIT %d" % max(1, min(limit, 200)) if limit else "")
    return [dict(r) for r in db.execute(sql, args)]


@router.post("/users", status_code=201)
def create_user(body: UserIn, admin=Depends(require_admin), db=Depends(get_db, scope="function")):
    if db.execute("SELECT 1 FROM users WHERE username=?", (body.username,)).fetchone():
        raise HTTPException(409, "Benutzer existiert bereits")
    if body.source == "local" and not body.password:
        raise HTTPException(422, "Für lokale Benutzer ist ein Passwort nötig (mind. 8 Zeichen)")
    pwh = hash_password(body.password) if body.source == "local" else "ldap$" + secrets.token_hex(16)
    see_all = int(body.see_all and body.role == "viewer")
    cur = db.execute("INSERT INTO users(username, display_name, password_hash, role, auth_source, see_all) VALUES (?,?,?,?,?,?)",
                     (body.username, body.display_name.strip(), pwh, body.role, body.source, see_all))
    audit.log(db, admin, "user.create", "%s (%s, %s%s)" % (body.username, body.role, body.source, ", alle Projekte sehen" if see_all else ""))
    return {"id": cur.lastrowid}


@router.put("/users/{uid}/display-name")
def admin_set_display_name(uid: int, body: DisplayNameIn, admin=Depends(require_admin), db=Depends(get_db, scope="function")):
    """Anzeigename eines lokalen Benutzers setzen (bei AD-Konten kommt er aus dem AD und wird beim Login abgeglichen)."""
    u = db.execute("SELECT username, auth_source FROM users WHERE id=?", (uid,)).fetchone()
    if not u:
        raise HTTPException(404, "Benutzer nicht gefunden")
    if u["auth_source"] == "ldap":
        raise HTTPException(400, "Der Anzeigename wird aus dem Active Directory übernommen")
    db.execute("UPDATE users SET display_name=? WHERE id=?", (body.display_name.strip(), uid))
    audit.log(db, admin, "user.display_name", "%s: %s" % (u["username"], body.display_name.strip()))
    return {"ok": True}


@router.put("/users/{uid}/password")
def admin_set_password(uid: int, body: AdminPasswordIn, request: Request, admin=Depends(require_admin), db=Depends(get_db, scope="function")):
    """Admin setzt das Passwort eines lokalen Benutzers neu (AD-Konten werden im AD verwaltet)."""
    u = db.execute("SELECT username, auth_source FROM users WHERE id=?", (uid,)).fetchone()
    if not u:
        raise HTTPException(404, "Benutzer nicht gefunden")
    if uid == admin["id"]:
        raise HTTPException(400, "Eigenes Passwort bitte unter „Passwort ändern“ setzen")
    if u["auth_source"] == "ldap":
        raise HTTPException(400, "Das Passwort wird im Active Directory verwaltet")
    if u["auth_source"] == "service":
        raise HTTPException(400, "Dienstkonten haben kein Passwort (Zugang über API-Token)")
    db.execute("UPDATE users SET password_hash=?, token_version=token_version+1 WHERE id=?", (hash_password(body.new_password), uid))   # Sitzungen des Benutzers enden
    audit.log(db, admin, "user.password", u["username"], audit.ip_of(request))
    return {"ok": True}


@router.post("/users/{uid}/logout")
def admin_end_sessions(uid: int, admin=Depends(require_admin), db=Depends(get_db, scope="function")):
    """Alle Sitzungen eines Benutzers beenden (z. B. bei Verdacht oder Ausscheiden); er muss sich neu anmelden."""
    u = db.execute("SELECT username FROM users WHERE id=?", (uid,)).fetchone()
    if not u:
        raise HTTPException(404, "Benutzer nicht gefunden")
    if uid == admin["id"]:
        raise HTTPException(400, "Eigene Sitzung bitte über „Abmelden“ beenden")
    db.execute("UPDATE users SET token_version=token_version+1 WHERE id=?", (uid,))
    audit.log(db, admin, "user.logout", u["username"])
    return {"ok": True}


@router.put("/users/{uid}/role")
def set_role(uid: int, body: RoleIn, admin=Depends(require_admin), db=Depends(get_db, scope="function")):
    """Globale Rolle eines Benutzers ändern (wirkt sofort, die Rolle wird bei jeder Anfrage aus der DB gelesen)."""
    u = db.execute("SELECT username, role, auth_source FROM users WHERE id=?", (uid,)).fetchone()
    if not u:
        raise HTTPException(404, "Benutzer nicht gefunden")
    if uid == admin["id"]:
        raise HTTPException(400, "Eigene Rolle nicht änderbar")
    if u["auth_source"] == "service" and body.role == "admin":
        raise HTTPException(400, "Dienstkonten können keine Administratoren sein")
    if body.role == u["role"]:
        return {"ok": True}
    if body.role == "viewer":
        owned = db.execute("SELECT name FROM projects WHERE owner_id=?", (uid,)).fetchall()
        if owned:
            raise HTTPException(409, "Benutzer ist Verantwortlicher von: %s – zuerst Verantwortung übertragen"
                                % ", ".join(r["name"] for r in owned[:5]))
    db.execute("UPDATE users SET role=?, see_all=0 WHERE id=?", (body.role, uid))     # „Alle Projekte“ gilt nur für viewer
    audit.log(db, admin, "user.role", "%s: %s → %s" % (u["username"], u["role"], body.role))
    return {"ok": True}


@router.put("/users/{uid}/see-all")
def set_see_all(uid: int, body: SeeAllIn, admin=Depends(require_admin), db=Depends(get_db, scope="function")):
    """„Betrachter alle Projekte“: Benutzer mit Rolle viewer sieht alle Projekte lesend (Rolle wird bei Bedarf auf viewer gesetzt)."""
    u = db.execute("SELECT username, role FROM users WHERE id=?", (uid,)).fetchone()
    if not u:
        raise HTTPException(404, "Benutzer nicht gefunden")
    if body.see_all and u["role"] == "admin":
        raise HTTPException(422, "Administratoren sehen bereits alle Projekte")
    if body.see_all:
        db.execute("UPDATE users SET role='viewer', see_all=1 WHERE id=?", (uid,))
    else:
        db.execute("UPDATE users SET see_all=0 WHERE id=?", (uid,))
    audit.log(db, admin, "user.see_all", "%s: %s" % (u["username"], "an" if body.see_all else "aus"))
    return {"ok": True}


@router.delete("/users/{uid}")
def delete_user(uid: int, admin=Depends(require_admin), db=Depends(get_db, scope="function")):
    if uid == admin["id"]:
        raise HTTPException(400, "Eigenen Benutzer nicht löschbar")
    owned = db.execute("SELECT name FROM projects WHERE owner_id=?", (uid,)).fetchall()
    if owned:
        raise HTTPException(409, "Benutzer ist Verantwortlicher von: %s – zuerst Verantwortung übertragen"
                            % ", ".join(r["name"] for r in owned[:5]))
    gone = db.execute("SELECT username FROM users WHERE id=?", (uid,)).fetchone()
    db.execute("DELETE FROM users WHERE id=?", (uid,))
    audit.log(db, admin, "user.delete", gone["username"] if gone else "ID %d" % uid)
    return {"ok": True}


# ── Projekte ────────────────────────────────────────────────────────────────
def _hstate(v: str) -> str:
    v = (v or "").lower()
    if v and v not in feiertage.STATES:
        raise HTTPException(422, "Unbekanntes Bundesland")
    return v


def _days(v: List[int]) -> str:
    v = sorted({d for d in v if 0 <= d <= 6})
    if not v:
        raise HTTPException(422, "Mindestens ein Arbeitstag nötig")
    return ",".join(map(str, v))


@router.get("/projects")
def list_projects(user=Depends(current_user), db=Depends(get_db, scope="function")):
    rows = db.execute(
        "SELECT p.*, COALESCE(NULLIF(u.display_name, ''), u.username) AS owner_name, (SELECT COUNT(*) FROM tasks t WHERE t.project_id=p.id) AS task_count "
        "FROM projects p LEFT JOIN users u ON u.id=p.owner_id ORDER BY p.updated_at DESC").fetchall()
    out = []
    for r in rows:
        lvl = access.level_of(db, user, r["id"])
        if lvl:
            d = svc.project_summary(db, r)
            d["access"] = access.NAMES[lvl]
            out.append(d)
    return out


def _valid_owner(db, uid: int) -> None:
    u = db.execute("SELECT role FROM users WHERE id=?", (uid,)).fetchone()
    if not u:
        raise HTTPException(422, "Verantwortlicher existiert nicht")
    if u["role"] == "viewer":
        raise HTTPException(422, "Ein Benutzer mit Rolle viewer kann nicht Verantwortlicher sein")


@router.post("/projects", status_code=201)
def create_project(body: ProjectIn, user=Depends(require_editor), db=Depends(get_db, scope="function")):
    owner = user["id"]
    if body.owner_id is not None and body.owner_id != user["id"]:
        if user["role"] != "admin":
            raise HTTPException(403, "Nur Administratoren können einen anderen Verantwortlichen setzen")
        _valid_owner(db, body.owner_id)
        owner = body.owner_id
    cur = db.execute(
        "INSERT INTO projects(name, description, start_date, work_days, holidays, holiday_state, owner_id) VALUES (?,?,?,?,?,?,?)",
        (body.name, body.description, body.start_date.isoformat(), _days(body.work_days),
         ",".join(h.isoformat() for h in body.holidays), _hstate(body.holiday_state), owner))
    svc.log(db, cur.lastrowid, user, "Projekt angelegt", body.name)
    return svc.load_project(db, cur.lastrowid, user)


@router.post("/projects/wizard", status_code=201)
def create_project_wizard(body: WizardIn, user=Depends(require_editor), db=Depends(get_db, scope="function")):
    """Assistent „Neues Projekt“: Projekt mit Grunddaten, Struktur der Projektart, Mitgliedern und Berichtseinstellungen anlegen."""
    owner = user["id"]
    if body.owner_id is not None and body.owner_id != user["id"]:
        if user["role"] != "admin":
            raise HTTPException(403, "Nur Administratoren können einen anderen Verantwortlichen setzen")
        _valid_owner(db, body.owner_id)
        owner = body.owner_id
    seen = set()
    for m in body.members:
        if m.user_id == owner:
            raise HTTPException(422, "Der Verantwortliche ist bereits Projektleiter")
        if m.user_id in seen:
            raise HTTPException(422, "Benutzer doppelt angegeben")
        seen.add(m.user_id)
        if not db.execute("SELECT 1 FROM users WHERE id=?", (m.user_id,)).fetchone():
            raise HTTPException(422, "Benutzer %s existiert nicht" % m.user_id)
    cur = db.execute(
        "INSERT INTO projects(name, description, start_date, work_days, holidays, holiday_state, owner_id, report_enabled, report_weekday, report_hour, report_to) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (body.name.strip(), body.description, body.start_date.isoformat(), _days(body.work_days), ",".join(h.isoformat() for h in body.holidays), _hstate(body.holiday_state), owner,
         int(body.report_enabled), body.report_weekday, body.report_hour, body.report_to))
    pid = cur.lastrowid
    for m in body.members:
        db.execute("INSERT INTO project_members(project_id, user_id, role) VALUES (?,?,?)", (pid, m.user_id, m.role))
    if body.kind != "empty":
        demo_kit.apply_template(db, user, pid, body.kind)
    svc.validate_no_cycle(db, pid)
    svc.log(db, pid, user, "Projekt angelegt", "%s (Assistent, Art: %s, %d Mitglieder)" % (body.name, body.kind, len(body.members)))
    return svc.load_project(db, pid, user)


@router.get("/projects/{pid}")
def get_project(pid: int, user=Depends(access.proj("view")), db=Depends(get_db, scope="function")):
    return svc.load_project(db, pid, user)


@router.get("/projects/{pid}/revision")
def revision(pid: int, user=Depends(access.proj("view")), db=Depends(get_db, scope="function")):
    return {"revision": svc.get_project_row(db, pid)["revision"]}


EVENT_MAX_SECONDS = 600     # danach trennt der Server; der Client verbindet neu (erneute Rechteprüfung)


def _read_revision(pid: int) -> Optional[int]:
    conn = connect()
    try:
        row = conn.execute("SELECT revision FROM projects WHERE id=?", (pid,)).fetchone()
        return row["revision"] if row else None
    finally:
        conn.close()


@router.get("/projects/{pid}/events")
async def project_events(pid: int, user=Depends(access.proj("view"))):
    """Server-Sent Events: meldet Revisionsänderungen des Projekts (statt Client-Polling); Heartbeat alle 15 s."""
    async def gen():
        last, idle, waited = None, 0.0, 0.0
        while waited < EVENT_MAX_SECONDS:
            rev = await asyncio.to_thread(_read_revision, pid)
            if rev is None:
                yield "event: gone\ndata: {}\n\n"
                return
            if rev != last:
                last, idle = rev, 0.0
                yield "event: revision\ndata: %s\n\n" % json.dumps({"revision": rev})
            elif idle >= 15:
                idle = 0.0
                yield ": ping\n\n"
            await asyncio.sleep(1.0)
            idle += 1.0
            waited += 1.0
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.patch("/projects/{pid}")
def patch_project(pid: int, body: ProjectPatch, user=Depends(access.proj("owner")), db=Depends(get_db, scope="function")):
    svc.get_project_row(db, pid)
    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        db.execute("UPDATE projects SET name=? WHERE id=?", (data["name"], pid))
    if "description" in data and data["description"] is not None:
        db.execute("UPDATE projects SET description=? WHERE id=?", (data["description"], pid))
    if data.get("start_date"):
        db.execute("UPDATE projects SET start_date=? WHERE id=?", (data["start_date"].isoformat(), pid))
    if data.get("work_days") is not None:
        db.execute("UPDATE projects SET work_days=? WHERE id=?", (_days(data["work_days"]), pid))
    if data.get("holidays") is not None:
        db.execute("UPDATE projects SET holidays=? WHERE id=?",
                   (",".join(h.isoformat() for h in data["holidays"]), pid))
    if data.get("holiday_state") is not None:
        db.execute("UPDATE projects SET holiday_state=? WHERE id=?", (_hstate(data["holiday_state"]), pid))
    for key in ("report_enabled", "report_weekday", "report_hour", "report_to"):
        if data.get(key) is not None:
            db.execute("UPDATE projects SET %s=? WHERE id=?" % key, (int(data[key]) if key != "report_to" else data[key], pid))
    if data.get("owner_id") is not None:
        old = svc.get_project_row(db, pid)["owner_id"]
        if data["owner_id"] != old:
            _valid_owner(db, data["owner_id"])
            db.execute("UPDATE projects SET owner_id=? WHERE id=?", (data["owner_id"], pid))
            db.execute("DELETE FROM project_members WHERE project_id=? AND user_id=?", (pid, data["owner_id"]))
            svc.log(db, pid, user, "Verantwortlicher geändert", "→ Benutzer-ID %s" % data["owner_id"])
            audit.log(db, user, "project.owner", "Projekt %d → Benutzer-ID %s" % (pid, data["owner_id"]))
    svc.bump(db, pid)
    svc.log(db, pid, user, "Projekteinstellungen geändert")
    # Nach Übertragung hat der bisherige Owner evtl. nur noch Lesezugriff/keinen Zugriff
    if access.level_of(db, user, pid) == 0:
        return {"transferred": True}
    return svc.load_project(db, pid, user)


@router.put("/projects/{pid}/members")
def set_members(pid: int, items: List[MemberIn], user=Depends(access.proj("owner")), db=Depends(get_db, scope="function")):
    owner_id = svc.get_project_row(db, pid)["owner_id"]
    seen = set()
    for m in items:
        if m.user_id == owner_id:
            raise HTTPException(422, "Der Verantwortliche ist bereits Projektleiter")
        if m.user_id in seen:
            raise HTTPException(422, "Benutzer doppelt angegeben")
        seen.add(m.user_id)
        if not db.execute("SELECT 1 FROM users WHERE id=?", (m.user_id,)).fetchone():
            raise HTTPException(422, "Benutzer %s existiert nicht" % m.user_id)
    db.execute("DELETE FROM project_members WHERE project_id=?", (pid,))
    for m in items:
        db.execute("INSERT INTO project_members(project_id, user_id, role) VALUES (?,?,?)", (pid, m.user_id, m.role))
    svc.bump(db, pid)
    svc.log(db, pid, user, "Mitglieder geändert", "%d Mitglieder" % len(items))
    return svc.load_project(db, pid, user)


@router.delete("/projects/{pid}")
def delete_project(pid: int, user=Depends(access.proj("owner")), db=Depends(get_db, scope="function")):
    audit.log(db, user, "project.delete", "%s (ID %d)" % (svc.get_project_row(db, pid)["name"], pid))
    db.execute("DELETE FROM projects WHERE id=?", (pid,))
    files_api.remove_project_files(pid)
    return {"ok": True}


@router.get("/projects/{pid}/journal")
def journal(pid: int, limit: int = 100, user=Depends(access.proj("view")), db=Depends(get_db, scope="function")):
    svc.get_project_row(db, pid)
    return [dict(r) for r in db.execute(
        "SELECT * FROM journal WHERE project_id=? ORDER BY id DESC LIMIT ?", (pid, min(limit, 500)))]


@router.post("/projects/{pid}/baseline")
def set_baseline(pid: int, user=Depends(access.proj("owner")), db=Depends(get_db, scope="function")):
    data = svc.load_project(db, pid, user)
    plan = finance_api.plan_by_task(db, pid, data)
    for t in data["tasks"]:
        db.execute("UPDATE tasks SET baseline_start=?, baseline_finish=?, baseline_cost=? WHERE id=?",
                   (t["start"], t["finish"], None if t["summary"] else plan.get(t["id"], 0.0), t["id"]))
    svc.bump(db, pid)
    svc.log(db, pid, user, "Basisplan gespeichert")
    return svc.load_project(db, pid, user)


@router.delete("/projects/{pid}/baseline")
def clear_baseline(pid: int, user=Depends(access.proj("owner")), db=Depends(get_db, scope="function")):
    svc.get_project_row(db, pid)
    db.execute("UPDATE tasks SET baseline_start=NULL, baseline_finish=NULL, baseline_cost=NULL WHERE project_id=?", (pid,))
    svc.bump(db, pid)
    svc.log(db, pid, user, "Basisplan gelöscht")
    return svc.load_project(db, pid, user)


# ── Vorgänge ────────────────────────────────────────────────────────────────
def _check_window(ctype: str, cdate, deadline) -> None:
    """Erledigungszeitraum: „von“ (Beginn frühestens) darf nicht nach „bis“ (Frist) liegen."""
    if deadline and ctype == "SNET" and cdate and str(cdate)[:10] > str(deadline)[:10]:
        raise HTTPException(422, "Erledigungszeitraum: „von“ liegt nach „bis“")


def _check_constraint(ctype: str, cdate) -> None:
    if ctype != "ASAP" and not cdate:
        raise HTTPException(422, "Für diesen Constraint ist ein Datum nötig")


@router.post("/projects/{pid}/tasks", status_code=201)
def create_task(pid: int, body: TaskIn, user=Depends(access.proj("edit")), db=Depends(get_db, scope="function")):
    svc.get_project_row(db, pid)
    _check_constraint(body.constraint_type, body.constraint_date)
    _check_window(body.constraint_type, body.constraint_date, body.deadline)
    parent, pos = body.parent_id, None
    if body.after_id is not None:
        ref = svc.project_of_task(db, body.after_id)
        if ref["project_id"] != pid:
            raise HTTPException(422, "Bezugsvorgang gehört zu anderem Projekt")
        parent, pos = ref["parent_id"], ref["position"] + 1
    elif parent is not None and svc.project_of_task(db, parent)["project_id"] != pid:
        raise HTTPException(422, "Übergeordneter Vorgang gehört zu anderem Projekt")
    if pos is None:
        row = db.execute("SELECT COALESCE(MAX(position)+1, 0) AS n FROM tasks WHERE project_id=? AND parent_id IS ?",
                         (pid, parent)).fetchone()
        pos = row["n"]
    else:
        db.execute("UPDATE tasks SET position=position+1 WHERE project_id=? AND parent_id IS ? AND position>=?",
                   (pid, parent, pos))
    cur = db.execute(
        "INSERT INTO tasks(project_id, parent_id, position, name, duration, percent, constraint_type, "
        "constraint_date, notes, pool, deadline) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (pid, parent, pos, body.name, body.duration, body.percent, body.constraint_type,
         body.constraint_date.isoformat() if body.constraint_date else None, body.notes, int(body.pool),
         body.deadline.isoformat() if body.deadline else None))
    svc.bump(db, pid)
    svc.log(db, pid, user, "Vorgang angelegt", body.name, cur.lastrowid)
    return svc.load_project(db, pid, user)


def _set_status(db, ids: List[int], status: str, user=None) -> int:
    """Setzt den Status der Blatt-Vorgänge unter/unter den angegebenen IDs (Sammelvorgänge -> alle Teilvorgänge)."""
    rows = db.execute("SELECT id, project_id, parent_id, status, percent FROM tasks WHERE project_id=(SELECT project_id FROM tasks WHERE id=?)",
                      (ids[0],)).fetchall()
    by_id = {r["id"]: r for r in rows}
    kids: dict = {}
    for r in rows:
        kids.setdefault(r["parent_id"], []).append(r["id"])
    leaves, stack = set(), list(ids)
    while stack:
        cur = stack.pop()
        if cur not in by_id:
            continue
        if kids.get(cur):
            stack.extend(kids[cur])
        else:
            leaves.add(cur)
    for lid in leaves:
        st, pc = svc.apply_status(by_id[lid]["status"], by_id[lid]["percent"], status)
        db.execute("UPDATE tasks SET status=?, percent=?, status_note=CASE WHEN ?='blocked' THEN status_note ELSE '' END WHERE id=?",
                   (st, pc, st, lid))
        webhooks.status_changed(db, by_id[lid]["project_id"], lid, by_id[lid]["status"], st, user)
    return len(leaves)


@router.post("/projects/{pid}/tasks/status")
def bulk_status(pid: int, body: BulkStatusIn, user=Depends(access.proj("work")), db=Depends(get_db, scope="function")):
    lvl = access.level_of(db, user, pid)
    for tid in body.task_ids:
        if svc.project_of_task(db, tid)["project_id"] != pid:
            raise HTTPException(422, "Vorgang %s gehört zu anderem Projekt" % tid)
        if lvl < 3 and not access.is_assigned(db, user["id"], tid):           # Mitarbeiter: nur eigene Vorgänge
            raise HTTPException(403, "Keine Berechtigung (benötigt: Bearbeiter oder Zuordnung zu diesem Vorgang)")
    n = _set_status(db, body.task_ids, body.status, user)
    svc.bump(db, pid)
    svc.log(db, pid, user, "Status gesetzt", "%s: %d Vorgänge" % (body.status, n))
    return svc.load_project(db, pid, user)


@router.patch("/tasks/{tid}")
def patch_task(tid: int, body: TaskPatch, user=Depends(access.task_own()), db=Depends(get_db, scope="function")):
    t = svc.project_of_task(db, tid)
    pid = t["project_id"]
    d = body.model_dump(exclude_unset=True)
    if access.level_of(db, user, pid) < 3 and set(d) - {"status", "percent", "status_note"}:     # Mitarbeiter: nur Status/Fortschritt/Notiz
        raise HTTPException(403, "Keine Berechtigung (benötigt: Bearbeiter)")
    ctype = d.get("constraint_type", t["constraint_type"])
    cdate = t["constraint_date"]
    if "constraint_date" in d and d["constraint_date"] is not None:
        cdate = d["constraint_date"].isoformat()
    if d.get("clear_constraint_date") or ctype == "ASAP":
        cdate = None
    _check_constraint(ctype, cdate)
    changes = []
    status_event = None
    for col in ("name", "duration", "notes"):
        if col in d and d[col] is not None and d[col] != t[col]:
            db.execute("UPDATE tasks SET %s=? WHERE id=?" % col, (d[col], tid))
            changes.append("%s: %s → %s" % (col, t[col], d[col]))
    has_kids = db.execute("SELECT 1 FROM tasks WHERE parent_id=?", (tid,)).fetchone() is not None
    if d.get("status") is not None and has_kids:        # Sammelvorgang: gilt für alle Teilvorgänge
        n = _set_status(db, [tid], d["status"], user)
        changes.append("status → %s (%d Vorgänge)" % (d["status"], n))
    elif not has_kids and (d.get("status") is not None or d.get("percent") is not None):
        st, pc = svc.apply_status(t["status"], t["percent"], d.get("status"), d.get("percent"))
        if st != t["status"] or pc != t["percent"]:
            db.execute("UPDATE tasks SET status=?, percent=?, status_note=CASE WHEN ?='blocked' THEN status_note ELSE '' END WHERE id=?",
                       (st, pc, st, tid))
            changes.append("status/fortschritt: %s %s%% → %s %s%%" % (t["status"], t["percent"], st, pc))
            status_event = (t["status"], st)
    if d.get("pool") is not None and int(d["pool"]) != t["pool"]:
        if d["pool"] and has_kids:
            raise HTTPException(422, "Sammelvorgänge können nicht in den Pool gestellt werden")
        db.execute("UPDATE tasks SET pool=? WHERE id=?", (int(d["pool"]), tid))
        changes.append("Arbeitspaket-Pool: %s" % ("an" if d["pool"] else "aus"))
    if d.get("status_note") is not None and d["status_note"] != t["status_note"]:
        db.execute("UPDATE tasks SET status_note=? WHERE id=?", (d["status_note"], tid))
        changes.append("status-notiz")
    dl = t["deadline"]
    if d.get("clear_deadline"):
        dl = None
    elif d.get("deadline") is not None:
        dl = d["deadline"].isoformat()
    _check_window(ctype, cdate, dl)
    if dl != t["deadline"]:
        db.execute("UPDATE tasks SET deadline=? WHERE id=?", (dl, tid))
        changes.append("Frist: %s → %s" % (t["deadline"] or "–", dl or "–"))
    if ctype != t["constraint_type"] or cdate != t["constraint_date"]:
        db.execute("UPDATE tasks SET constraint_type=?, constraint_date=? WHERE id=?", (ctype, cdate, tid))
        changes.append("constraint: %s %s → %s %s" % (t["constraint_type"], t["constraint_date"] or "", ctype, cdate or ""))
    if changes:
        svc.bump(db, pid)
        svc.log(db, pid, user, "Vorgang geändert", "%s | %s" % (t["name"], "; ".join(changes)), tid)
        if status_event:                                   # erst nach allen Änderungen (Status-Notiz ist dann im Payload enthalten)
            webhooks.status_changed(db, pid, tid, status_event[0], status_event[1], user)
    return svc.load_project(db, pid, user)


@router.delete("/tasks/{tid}")
def delete_task(tid: int, user=Depends(access.task("edit")), db=Depends(get_db, scope="function")):
    t = svc.project_of_task(db, tid)
    files_api.remove_task_files(db, tid)                # Dateien von der Platte (DB-Zeilen: CASCADE)
    db.execute("DELETE FROM tasks WHERE id=?", (tid,))  # Kinder/Deps/Zuordnungen per CASCADE
    svc.renumber(db, t["project_id"], t["parent_id"])
    svc.bump(db, t["project_id"])
    svc.log(db, t["project_id"], user, "Vorgang gelöscht", t["name"], tid)
    return svc.load_project(db, t["project_id"], user)


@router.post("/tasks/{tid}/move")
def move_task(tid: int, body: MoveIn, user=Depends(access.task("edit")), db=Depends(get_db, scope="function")):
    t = svc.project_of_task(db, tid)
    pid = t["project_id"]
    if body.parent_id is not None:
        np = svc.project_of_task(db, body.parent_id)
        if np["project_id"] != pid:
            raise HTTPException(422, "Zielvorgang gehört zu anderem Projekt")
        if svc.is_descendant(db, tid, body.parent_id):
            raise HTTPException(422, "Vorgang kann nicht unter sich selbst verschoben werden")
    old_parent = t["parent_id"]
    # temporär ans Ende des Ziels, dann auf Index einsortieren
    db.execute("UPDATE tasks SET parent_id=?, position=-1 WHERE id=?", (body.parent_id, tid))
    sibs = [r["id"] for r in db.execute(
        "SELECT id FROM tasks WHERE project_id=? AND parent_id IS ? AND id<>? ORDER BY position, id",
        (pid, body.parent_id, tid))]
    sibs.insert(min(body.index, len(sibs)), tid)
    for i, sid in enumerate(sibs):
        db.execute("UPDATE tasks SET position=? WHERE id=?", (i, sid))
    if old_parent != body.parent_id:
        svc.renumber(db, pid, old_parent)
    svc.bump(db, pid)
    svc.log(db, pid, user, "Vorgang verschoben", t["name"], tid)
    return svc.load_project(db, pid, user)


@router.post("/tasks/{tid}/shift")
def shift_task(tid: int, body: ShiftIn, user=Depends(access.task("edit")), db=Depends(get_db, scope="function")):
    """Verschiebt einen Vorgang bzw. eine ganze Phase um ``days`` Kalendertage.

    Bei Sammelvorgängen werden die Einstiegs-Teilvorgänge (ohne Vorgänger innerhalb der Phase)
    per Constraint festgesetzt; die übrigen folgen über ihre Abhängigkeiten.
    """
    t = svc.project_of_task(db, tid)
    pid = t["project_id"]
    data = svc.load_project(db, pid, user)
    by_id = {x["id"]: x for x in data["tasks"]}
    under = set()
    stack = [tid]
    while stack:
        cur = stack.pop()
        for x in data["tasks"]:
            if x["parent_id"] == cur:
                under.add(x["id"])
                stack.append(x["id"])
    leaves = [by_id[i] for i in (under or {tid}) if not by_id[i]["summary"]]
    leaf_ids = {x["id"] for x in leaves}
    entries = [x for x in leaves if not any(d["succ_id"] == x["id"] and d["pred_id"] in leaf_ids for d in data["deps"])]
    if body.days == 0 or not entries:
        return data
    for x in entries:
        new = date.fromisoformat(x["start"]) + timedelta(days=body.days)
        ctype = "MSO" if x["constraint_type"] == "MSO" else "SNET"
        db.execute("UPDATE tasks SET constraint_type=?, constraint_date=? WHERE id=?", (ctype, new.isoformat(), x["id"]))
    svc.bump(db, pid)
    svc.log(db, pid, user, "Vorgang/Phase verschoben", "%s: %+d Tage" % (t["name"], body.days), tid)
    return svc.load_project(db, pid, user)


@router.put("/tasks/{tid}/predecessors")
def set_predecessors(tid: int, preds: List[PredIn], user=Depends(access.task("edit")), db=Depends(get_db, scope="function")):
    t = svc.project_of_task(db, tid)
    pid = t["project_id"]
    seen = set()
    for p in preds:
        if p.pred_id == tid:
            raise HTTPException(422, "Vorgang kann nicht sein eigener Vorgänger sein")
        if p.pred_id in seen:
            raise HTTPException(422, "Vorgänger doppelt angegeben")
        seen.add(p.pred_id)
        if svc.project_of_task(db, p.pred_id)["project_id"] != pid:
            raise HTTPException(422, "Vorgänger gehört zu anderem Projekt")
        if svc.is_descendant(db, tid, p.pred_id) or svc.is_descendant(db, p.pred_id, tid):
            raise HTTPException(422, "Abhängigkeit zwischen Sammelvorgang und seinem eigenen Teilvorgang nicht erlaubt")
    db.execute("DELETE FROM deps WHERE succ_id=?", (tid,))
    for p in preds:
        db.execute("INSERT INTO deps(project_id, pred_id, succ_id, type, lag) VALUES (?,?,?,?,?)",
                   (pid, p.pred_id, tid, p.type, p.lag))
    svc.validate_no_cycle(db, pid)
    svc.bump(db, pid)
    svc.log(db, pid, user, "Vorgänger geändert", t["name"], tid)
    return svc.load_project(db, pid, user)


# ── Ressourcen ──────────────────────────────────────────────────────────────
def _res_refs(db, pid: int, body: ResourceIn) -> None:
    for table, rid, what in (("cost_centers", body.cost_center_id, "Kostenstelle"), ("cost_types", body.cost_type_id, "Kostenart")):
        if rid is not None:
            row = db.execute("SELECT project_id FROM %s WHERE id=?" % table, (rid,)).fetchone()
            if not row or row["project_id"] != pid:
                raise HTTPException(422, "%s gehört nicht zum Projekt" % what)


def _res_user(db, pid: int, uid: Optional[int]) -> Optional[int]:
    """Jeder vorhandene Benutzer ist verknüpfbar (die Zuordnung an Vorgängen gibt ihm Mitarbeiter-Zugriff)."""
    if uid is None:
        return None
    if not db.execute("SELECT 1 FROM users WHERE id=?", (uid,)).fetchone():             # Zuordnung gibt dem Benutzer automatisch Mitarbeiter-Zugriff
        raise HTTPException(422, "Benutzer %s existiert nicht" % uid)
    return uid


def _res_parent(db, pid: int, rid: Optional[int], parent: Optional[int]) -> Optional[int]:
    """„Berichtet an“: Ressource desselben Projekts, nicht man selbst und kein Zirkelbezug."""
    if parent is None:
        return None
    row = db.execute("SELECT project_id FROM resources WHERE id=?", (parent,)).fetchone()
    if not row or row["project_id"] != pid:
        raise HTTPException(422, "Vorgesetzte Ressource gehört nicht zum Projekt")
    seen, cur = set(), parent
    while cur is not None and cur not in seen:           # Kette nach oben: darf nie bei der Ressource selbst ankommen
        if cur == rid:
            raise HTTPException(422, "Zirkelbezug im Organigramm")
        seen.add(cur)
        up = db.execute("SELECT reports_to FROM resources WHERE id=?", (cur,)).fetchone()
        cur = up["reports_to"] if up else None
    return parent


@router.post("/projects/{pid}/resources", status_code=201)
def create_resource(pid: int, body: ResourceIn, user=Depends(access.proj("edit")), db=Depends(get_db, scope="function")):
    svc.get_project_row(db, pid)
    rate, cc, ct = 0.0, None, None
    if access.cost_level(db, user, pid) == "edit":   # Kosten-Felder nur für Verantwortliche
        _res_refs(db, pid, body)
        rate, cc, ct = body.cost_rate or 0.0, body.cost_center_id, body.cost_type_id
    uid = _res_user(db, pid, body.user_id) if "user_id" in body.model_fields_set else None
    boss = _res_parent(db, pid, None, body.reports_to) if "reports_to" in body.model_fields_set else None
    db.execute("INSERT INTO resources(project_id, name, max_units, cost_rate, cost_center_id, cost_type_id, user_id, funktion, reports_to) "
               "VALUES (?,?,?,?,?,?,?,?,?)", (pid, body.name, body.max_units, rate, cc, ct, uid, body.funktion.strip(), boss))
    svc.bump(db, pid)
    svc.log(db, pid, user, "Ressource angelegt", body.name)
    return svc.load_project(db, pid, user)


@router.put("/resources/{rid}/reports-to")
def set_reports_to(rid: int, body: ReportsToIn, user=Depends(access.resource("edit")), db=Depends(get_db, scope="function")):
    """Organigramm: Ressource einer anderen Ressource unterstellen (None = Projektleitung); fasst sonst nichts an der Ressource an."""
    r = db.execute("SELECT project_id, name FROM resources WHERE id=?", (rid,)).fetchone()
    if not r:
        raise HTTPException(404, "Ressource nicht gefunden")
    db.execute("UPDATE resources SET reports_to=? WHERE id=?", (_res_parent(db, r["project_id"], rid, body.reports_to), rid))
    svc.bump(db, r["project_id"])
    svc.log(db, r["project_id"], user, "Organigramm geändert", r["name"])
    return svc.load_project(db, r["project_id"], user)


@router.put("/resources/{rid}")
def update_resource(rid: int, body: ResourceIn, user=Depends(access.resource("edit")), db=Depends(get_db, scope="function")):
    r = db.execute("SELECT * FROM resources WHERE id=?", (rid,)).fetchone()
    if not r:
        raise HTTPException(404, "Ressource nicht gefunden")
    db.execute("UPDATE resources SET name=?, max_units=? WHERE id=?", (body.name, body.max_units, rid))
    if "funktion" in body.model_fields_set:
        db.execute("UPDATE resources SET funktion=? WHERE id=?", (body.funktion.strip(), rid))
    if "reports_to" in body.model_fields_set:
        db.execute("UPDATE resources SET reports_to=? WHERE id=?", (_res_parent(db, r["project_id"], rid, body.reports_to), rid))
    if "user_id" in body.model_fields_set:
        db.execute("UPDATE resources SET user_id=? WHERE id=?", (_res_user(db, r["project_id"], body.user_id), rid))
    if access.cost_level(db, user, r["project_id"]) == "edit":
        _res_refs(db, r["project_id"], body)
        db.execute("UPDATE resources SET cost_rate=?, cost_center_id=?, cost_type_id=? WHERE id=?",
                   (body.cost_rate if body.cost_rate is not None else r["cost_rate"],
                    body.cost_center_id, body.cost_type_id, rid))
    svc.bump(db, r["project_id"])
    svc.log(db, r["project_id"], user, "Ressource geändert", body.name)
    return svc.load_project(db, r["project_id"], user)


@router.delete("/resources/{rid}")
def delete_resource(rid: int, user=Depends(access.resource("edit")), db=Depends(get_db, scope="function")):
    r = db.execute("SELECT * FROM resources WHERE id=?", (rid,)).fetchone()
    if not r:
        raise HTTPException(404, "Ressource nicht gefunden")
    db.execute("DELETE FROM resources WHERE id=?", (rid,))
    svc.bump(db, r["project_id"])
    svc.log(db, r["project_id"], user, "Ressource gelöscht", r["name"])
    return svc.load_project(db, r["project_id"], user)


def _absence_check(db, pid: int, user, body: AbsenceIn, rid: int) -> None:
    if body.end_date < body.start_date:
        raise HTTPException(422, "Das Ende liegt vor dem Beginn")
    if (body.end_date - body.start_date).days > 400:
        raise HTTPException(422, "Eine Abwesenheit darf höchstens 400 Tage dauern")
    r = db.execute("SELECT project_id, user_id FROM resources WHERE id=?", (rid,)).fetchone()
    if not r or r["project_id"] != pid:
        raise HTTPException(422, "Ressource %s gehört nicht zum Projekt" % rid)
    if access.level_of(db, user, pid) < 3 and r["user_id"] != user["id"]:      # Mitarbeiter: nur die eigene Ressource
        raise HTTPException(403, "Keine Berechtigung (benötigt: Bearbeiter oder eigene Abwesenheit)")


@router.post("/projects/{pid}/absences", status_code=201)
def create_absence(pid: int, body: AbsenceIn, user=Depends(access.proj("work")), db=Depends(get_db, scope="function")):
    svc.get_project_row(db, pid)
    if body.resource_id is None:
        raise HTTPException(422, "Ressource fehlt")
    _absence_check(db, pid, user, body, body.resource_id)
    db.execute("INSERT INTO absences(project_id, resource_id, start_date, end_date, kind, note) VALUES (?,?,?,?,?,?)",
               (pid, body.resource_id, body.start_date.isoformat(), body.end_date.isoformat(), body.kind, body.note.strip()))
    svc.bump(db, pid)
    svc.log(db, pid, user, "Abwesenheit angelegt", "%s – %s" % (body.start_date.isoformat(), body.end_date.isoformat()))
    return svc.load_project(db, pid, user)


@router.put("/absences/{aid}")
def update_absence(aid: int, body: AbsenceIn, user=Depends(access.absence_own()), db=Depends(get_db, scope="function")):
    a = db.execute("SELECT * FROM absences WHERE id=?", (aid,)).fetchone()
    _absence_check(db, a["project_id"], user, body, a["resource_id"])
    db.execute("UPDATE absences SET start_date=?, end_date=?, kind=?, note=? WHERE id=?",
               (body.start_date.isoformat(), body.end_date.isoformat(), body.kind, body.note.strip(), aid))
    svc.bump(db, a["project_id"])
    svc.log(db, a["project_id"], user, "Abwesenheit geändert", "%s – %s" % (body.start_date.isoformat(), body.end_date.isoformat()))
    return svc.load_project(db, a["project_id"], user)


@router.delete("/absences/{aid}")
def delete_absence(aid: int, user=Depends(access.absence_own()), db=Depends(get_db, scope="function")):
    a = db.execute("SELECT * FROM absences WHERE id=?", (aid,)).fetchone()
    db.execute("DELETE FROM absences WHERE id=?", (aid,))
    svc.bump(db, a["project_id"])
    svc.log(db, a["project_id"], user, "Abwesenheit gelöscht", "%s – %s" % (a["start_date"], a["end_date"]))
    return svc.load_project(db, a["project_id"], user)


@router.put("/tasks/{tid}/assignments")
def set_assignments(tid: int, items: List[AssignIn], request: Request, user=Depends(access.task("edit")), db=Depends(get_db, scope="function")):
    t = svc.project_of_task(db, tid)
    pid = t["project_id"]
    old_ids = {r["resource_id"] for r in db.execute("SELECT resource_id FROM assignments WHERE task_id=?", (tid,))}
    db.execute("DELETE FROM assignments WHERE task_id=?", (tid,))
    resolved = []
    for a in items:
        rid = a.resource_id
        if rid is None:                                    # Benutzer gewählt: verknüpfte Ressource bei Bedarf anlegen (nur wer wirklich Arbeit hat)
            u = db.execute("SELECT id, username, display_name FROM users WHERE id=?", (a.user_id,)).fetchone()
            if not u:
                raise HTTPException(422, "Benutzer %s existiert nicht" % a.user_id)
            rid = _own_resource(db, pid, u)
        r = db.execute("SELECT project_id FROM resources WHERE id=?", (rid,)).fetchone()
        if not r or r["project_id"] != pid:
            raise HTTPException(422, "Ressource %s gehört nicht zum Projekt" % rid)
        db.execute("INSERT OR REPLACE INTO assignments(task_id, resource_id, units) VALUES (?,?,?)", (tid, rid, a.units))
        resolved.append(rid)
    svc.bump(db, pid)
    svc.log(db, pid, user, "Zuordnung geändert", t["name"], tid)
    new_ids = set(resolved)
    if new_ids != old_ids:
        names = {r["id"]: r["name"] for r in db.execute("SELECT id, name FROM resources WHERE project_id=?", (pid,))}
        webhooks.emit(db, pid, "task.assigned", tid, user, extra={"assigned": [names.get(i, str(i)) for i in sorted(new_ids)],
                                                                   "previous_assigned": [names.get(i, str(i)) for i in sorted(old_ids)]})
        out = svc.load_project(db, pid, user)
        tt = next((x for x in out["tasks"] if x["id"] == tid), None)
        info = ("Termin: %s – %s (%d Arbeitstage)" % (tt["start"], tt["finish"], tt["duration"])) if tt else ""
        mailer.dispatch(db, notify.assignment_changes(db, t, old_ids, new_ids, user, str(request.base_url), info))
        return out
    return svc.load_project(db, pid, user)


# ── Audit-Log, Datensicherung, Erinnerungen (Verwaltung) ─────────────────────
@router.get("/admin/audit")
def get_audit(q: str = "", action: str = "", limit: int = 100, offset: int = 0, _=Depends(require_admin), db=Depends(get_db, scope="function")):
    return audit.query(db, q, action, limit, offset)


@router.get("/admin/audit/export")
def export_audit(q: str = "", action: str = "", _=Depends(require_admin), db=Depends(get_db, scope="function")):
    rows = audit.query(db, q, action, 500, 0)["items"]
    esc = lambda v: '"%s"' % str(v).replace('"', '""')  # noqa: E731
    csv = "\ufeffZeit;Benutzer;Aktion;Details;IP\r\n" + "".join(";".join(esc(r[k]) for k in ("ts", "username", "action", "detail", "ip")) + "\r\n" for r in rows)
    return Response(csv.encode("utf-8"), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="openplan-audit.csv"'})


def _backup_state(db):
    return {"settings": backup.settings(db), "backups": backup.list_backups(), "dir": str(backup.BACKUP_DIR)}


@router.get("/admin/backup")
def get_backup(_=Depends(require_admin), db=Depends(get_db, scope="function")):
    return _backup_state(db)


@router.put("/admin/backup")
def put_backup_settings(body: BackupSettingsIn, user=Depends(require_admin), db=Depends(get_db, scope="function")):
    try:
        s = backup.save_settings(db, body.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(422, str(e))
    audit.log(db, user, "backup.settings", "aktiv=%s, ab %d Uhr, %d behalten" % (s["enabled"], s["hour"], s["keep"]))
    return _backup_state(db)


@router.post("/admin/backup", status_code=201)
def create_backup(request: Request, user=Depends(require_admin), db=Depends(get_db, scope="function")):
    try:
        res = backup.create("manuell von %s" % user["username"])
    except Exception as e:                                            # Platte voll, Rechte …
        audit.log_now(user["username"], "backup.fail", str(e)[:300], audit.ip_of(request))
        raise HTTPException(500, "Sicherung fehlgeschlagen: %s" % e)
    res["pruned"] = backup.prune(int(backup.settings(db)["keep"]))
    audit.log(db, user, "backup.create", "%s (%d Bytes)" % (res["name"], res["size"]), audit.ip_of(request))
    return {**_backup_state(db), "created": res}


@router.post("/admin/backup/{name}/verify")
def verify_backup(name: str, _=Depends(require_admin)):
    try:
        return backup.verify(backup.path_of(name))
    except FileNotFoundError:
        raise HTTPException(404, "Sicherung nicht gefunden")


@router.get("/admin/backup/{name}/download")
def download_backup(name: str, request: Request, user=Depends(require_admin), db=Depends(get_db, scope="function")):
    try:
        p = backup.path_of(name)
    except FileNotFoundError:
        raise HTTPException(404, "Sicherung nicht gefunden")
    audit.log(db, user, "backup.download", name, audit.ip_of(request))
    return FileResponse(p, media_type="application/gzip", filename=name)


@router.delete("/admin/backup/{name}")
def delete_backup(name: str, user=Depends(require_admin), db=Depends(get_db, scope="function")):
    try:
        backup.path_of(name).unlink()
    except FileNotFoundError:
        raise HTTPException(404, "Sicherung nicht gefunden")
    audit.log(db, user, "backup.delete", name)
    return _backup_state(db)


@router.get("/admin/settings/reminders")
def get_reminders(_=Depends(require_admin), db=Depends(get_db, scope="function")):
    st = db.execute("SELECT value FROM app_settings WHERE key='reminders_state'").fetchone()
    return {**reminders.settings(db), "state": json.loads(st["value"]) if st else {}}


@router.put("/admin/settings/reminders")
def put_reminders(body: ReminderSettingsIn, user=Depends(require_admin), db=Depends(get_db, scope="function")):
    try:
        s = reminders.save_settings(db, body.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(422, str(e))
    audit.log(db, user, "settings.reminders", json.dumps(s))
    return get_reminders(None, db)


@router.post("/admin/reminders/run")
def run_reminders(request: Request, user=Depends(require_admin), db=Depends(get_db, scope="function")):
    """Prüfung sofort ausführen (z. B. zum Test); bereits gemeldete Vorgänge werden nicht erneut gemeldet."""
    res = reminders.check(db, base=str(request.base_url))
    audit.log(db, user, "reminders.run", json.dumps(res))
    return res


# ── Rückgängig / Wiederholen ────────────────────────────────────────────────
def _undo_redo(pid: int, kind: str, user, db):
    row = history.step(db, pid, kind)
    if not row:
        raise HTTPException(409, "Nichts zum %s" % ("Rückgängigmachen" if kind == "undo" else "Wiederholen"))
    if row["username"] and row["username"] != user["username"] and access.level_of(db, user, pid) < 4:
        raise HTTPException(409, "Die letzte Änderung stammt von %s – nur sie/er oder der Verantwortliche kann sie zurücknehmen" % row["username"])
    history.apply(db, pid, row, "redo" if kind == "undo" else "undo", user["username"])
    svc.bump(db, pid)
    svc.log(db, pid, user, "Rückgängig gemacht" if kind == "undo" else "Wiederholt", row["label"])
    return svc.load_project(db, pid, user)


@router.post("/projects/{pid}/undo")
def undo(pid: int, user=Depends(access.proj("edit")), db=Depends(get_db, scope="function")):
    return _undo_redo(pid, "undo", user, db)


@router.post("/projects/{pid}/redo")
def redo(pid: int, user=Depends(access.proj("edit")), db=Depends(get_db, scope="function")):
    return _undo_redo(pid, "redo", user, db)


# ── Arbeitspakete (Pool zur Selbstübernahme) ────────────────────────────────
def _own_resource(db, pid: int, user) -> int:
    """Ressource des angemeldeten Benutzers im Projekt; wird bei Bedarf angelegt (Name = Benutzername)."""
    row = db.execute("SELECT id FROM resources WHERE project_id=? AND user_id=? ORDER BY id LIMIT 1",
                     (pid, user["id"])).fetchone()
    if row:
        return row["id"]
    cur = db.execute("INSERT INTO resources(project_id, name, user_id) VALUES (?,?,?)", (pid, label(user), user["id"]))
    return cur.lastrowid


@router.post("/tasks/{tid}/claim")
def claim_task(tid: int, user=Depends(access.task("work")), db=Depends(get_db, scope="function")):
    t = svc.project_of_task(db, tid)
    pid = t["project_id"]
    if not t["pool"] or db.execute("SELECT 1 FROM tasks WHERE parent_id=?", (tid,)).fetchone():
        raise HTTPException(409, "Dieses Arbeitspaket steht nicht zur Selbstübernahme bereit")
    if t["status"] == "done":
        raise HTTPException(409, "Das Arbeitspaket ist bereits erledigt")
    if db.execute("SELECT 1 FROM assignments WHERE task_id=?", (tid,)).fetchone():
        raise HTTPException(409, "Das Arbeitspaket wurde bereits übernommen")
    rid = _own_resource(db, pid, user)
    db.execute("INSERT INTO assignments(task_id, resource_id, units) VALUES (?,?,100)", (tid, rid))
    if t["status"] == "open":
        st, pc = svc.apply_status(t["status"], t["percent"], "in_progress")
        db.execute("UPDATE tasks SET status=?, percent=? WHERE id=?", (st, pc, tid))
    svc.bump(db, pid)
    svc.log(db, pid, user, "Arbeitspaket übernommen", t["name"], tid)
    return svc.load_project(db, pid, user)


@router.post("/tasks/{tid}/release")
def release_task(tid: int, user=Depends(access.task("work")), db=Depends(get_db, scope="function")):
    t = svc.project_of_task(db, tid)
    pid = t["project_id"]
    if not t["pool"]:
        raise HTTPException(409, "Dies ist kein Arbeitspaket aus dem Pool")
    rows = db.execute("SELECT a.resource_id, r.user_id FROM assignments a JOIN resources r ON r.id=a.resource_id "
                      "WHERE a.task_id=?", (tid,)).fetchall()
    if not rows:
        raise HTTPException(409, "Das Arbeitspaket ist nicht zugeordnet")
    if access.level_of(db, user, pid) < 4 and any(r["user_id"] != user["id"] for r in rows):
        raise HTTPException(403, "Nur wer das Paket übernommen hat (oder der Verantwortliche) kann es zurückgeben")
    db.execute("DELETE FROM assignments WHERE task_id=?", (tid,))
    if t["status"] == "in_progress" and t["percent"] <= 0:
        db.execute("UPDATE tasks SET status='open' WHERE id=?", (tid,))
    svc.bump(db, pid)
    svc.log(db, pid, user, "Arbeitspaket zurückgegeben", t["name"], tid)
    return svc.load_project(db, pid, user)


# ── Import / Export ─────────────────────────────────────────────────────────
@router.get("/projects/{pid}/export")
def export_project(pid: int, fmt: str = "json", user=Depends(access.proj("view")), db=Depends(get_db, scope="function")):
    data = svc.load_project(db, pid, user)
    name = "".join(c if c.isalnum() or c in "-_" else "_" for c in data["project"]["name"]) or "projekt"
    if fmt == "json":
        body, mime, ext = io_formats.to_json(data), "application/json", "json"
    elif fmt == "csv":
        body, mime, ext = io_formats.to_csv(data), "text/csv; charset=utf-8", "csv"
    elif fmt == "xml":
        body, mime, ext = io_formats.to_msp_xml(data), "application/xml", "xml"
    else:
        raise HTTPException(400, "Format unbekannt (json, csv, xml)")
    return Response(body, media_type=mime,
                    headers={"Content-Disposition": 'attachment; filename="%s.%s"' % (name, ext)})


@router.post("/projects/demo", status_code=201)
def create_demo(kind: str = "network", user=Depends(require_editor), db=Depends(get_db, scope="function")):
    """Legt ein Beispielprojekt an (Nutzer wird Verantwortlicher): ``network`` (Netzwerk-Rollout Cisco → Extreme),
    ``migration`` (Server-Migration auf ein neues Cluster) oder ``release`` (Transition eines Release-Wechsels)."""
    if kind == "network":
        pid = demo.create_demo_project(db, user)
    elif kind in demo_kit.KINDS:
        pid = demo_kit.KINDS[kind](db, user)
    else:
        raise HTTPException(422, "Unbekanntes Beispielprojekt")
    svc.validate_no_cycle(db, pid)
    return svc.load_project(db, pid, user)


@router.post("/projects/import", status_code=201)
async def import_project(file: UploadFile = File(...), user=Depends(require_editor), db=Depends(get_db, scope="function")):
    raw = await file.read()
    if len(raw) > 20 * 1024 * 1024:
        raise HTTPException(413, "Datei zu groß (max. 20 MB)")
    try:
        if (file.filename or "").lower().endswith(".xml") or raw.lstrip()[:1] == b"<":
            parsed = io_formats.parse_msp_xml(raw)
        else:
            parsed = io_formats.parse_json(raw)
    except (ValueError, KeyError) as e:
        raise HTTPException(422, "Import fehlgeschlagen: %s" % e)
    pid = io_formats.store_import(db, parsed, user["id"])
    svc.validate_no_cycle(db, pid)
    svc.log(db, pid, user, "Projekt importiert", file.filename or "")
    return svc.load_project(db, pid, user)
