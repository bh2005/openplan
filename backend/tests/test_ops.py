from test_api import _login, c  # noqa: F401,E402  (setzt DATA_DIR/ADMIN_PASSWORD vor allen App-Importen)

import datetime as dt  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import sqlite3  # noqa: E402
import tarfile  # noqa: E402

import pytest  # noqa: E402

import backup  # noqa: E402
import database  # noqa: E402
import mailer  # noqa: E402
import reminders  # noqa: E402

PW = "passwort-"
_IDS = {}


@pytest.fixture()
def mails(monkeypatch):
    sent = []
    monkeypatch.setattr(mailer, "run_async", False)
    monkeypatch.setattr(mailer, "send_now", lambda s, to, subject, text, html=None: sent.append({"to": to, "subject": subject, "text": text}))
    return sent


def team(c):
    if not _IDS:
        for n in ("op_owner", "op_anna", "op_ben", "op_viewer"):
            _IDS[n] = c.post("/api/users", json={"username": n, "password": PW + n, "role": "viewer" if n == "op_viewer" else "editor"}).json()["id"]
            c.put("/api/users/%d/email" % _IDS[n], json={"email": n + "@corp.test"})
    owner, anna, ben, viewer = (_login(n, PW + n) for n in ("op_owner", "op_anna", "op_ben", "op_viewer"))
    pid = owner.post("/api/projects", json={"name": "Ops", "start_date": "2026-10-12"}).json()["project"]["id"]
    owner.put("/api/projects/%d/members" % pid, json=[{"user_id": _IDS["op_anna"], "role": "editor"}, {"user_id": _IDS["op_ben"], "role": "editor"},
                                                      {"user_id": _IDS["op_viewer"], "role": "viewer"}])
    c.put("/api/admin/settings/mail", json={"enabled": True, "host": "smtp.corp.test", "from_addr": "openplan@corp.test", "public_url": "https://openplan.corp.test"})
    return owner, anna, ben, viewer, pid


def add_task(owner, pid, name, **kw):
    d = owner.post("/api/projects/%d/tasks" % pid, json={"name": name, **kw}).json()
    return max(t["id"] for t in d["tasks"])


# ── Audit-Log ───────────────────────────────────────────────────────────────
def test_audit_log(c):
    team(c)
    assert c.post("/api/auth/login", json={"username": "op_owner", "password": "falsch"}).status_code == 401
    assert c.post("/api/auth/login", json={"username": "gibtsnicht", "password": "x"}).status_code == 401
    _login("op_owner", PW + "op_owner")
    c.put("/api/admin/settings/mail", json={"public_url": "https://openplan.corp.test"})
    items = c.get("/api/admin/audit?limit=200").json()["items"]
    acts = [(i["action"], i["username"]) for i in items]
    assert ("login.fail", "op_owner") in acts and ("login.fail", "gibtsnicht") in acts and ("login", "op_owner") in acts
    assert any(a == "settings.mail.save" for a, _u in acts) and any(a == "user.create" for a, _u in acts)
    fail = next(i for i in items if i["action"] == "login.fail" and i["username"] == "op_owner")
    assert fail["detail"] == "falsches Passwort" and fail["ip"]                           # IP wird mitgeschrieben, Passwort nie
    assert "falsch" not in json.dumps([i for i in items if i["action"] == "login"])
    r = c.get("/api/admin/audit?q=gibtsnicht").json()
    assert r["total"] >= 1 and all("gibtsnicht" in (i["username"] + i["detail"] + i["ip"]) for i in r["items"])
    assert all(i["action"].startswith("login") for i in c.get("/api/admin/audit?action=login").json()["items"])
    assert "login.fail" in c.get("/api/admin/audit").json()["actions"]
    csv = c.get("/api/admin/audit/export")
    assert csv.status_code == 200 and "Zeit;Benutzer;Aktion" in csv.text and "login.fail" in csv.text
    owner = _login("op_owner", PW + "op_owner")
    assert owner.get("/api/admin/audit").status_code == 403
    # Projekt löschen wird festgehalten
    pid = owner.post("/api/projects", json={"name": "Wegwerf", "start_date": "2026-10-12"}).json()["project"]["id"]
    owner.delete("/api/projects/%d" % pid)
    assert any(i["action"] == "project.delete" and "Wegwerf" in i["detail"] for i in c.get("/api/admin/audit?action=project").json()["items"])


# ── Datensicherung ──────────────────────────────────────────────────────────
def test_backup_create_verify_restore(c, tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "BACKUP_DIR", tmp_path / "bk")
    owner, anna, ben, viewer, pid = team(c)
    add_task(owner, pid, "Sicherungstest")
    import config
    config.FILES_DIR.mkdir(parents=True, exist_ok=True)
    (config.FILES_DIR / "doku.txt").write_text("wichtig")
    r = c.post("/api/admin/backup")
    assert r.status_code == 201 and r.json()["created"]["files"] >= 1
    name = r.json()["backups"][0]["name"]
    v = c.post("/api/admin/backup/%s/verify" % name).json()
    assert v["ok"] and v["counts"]["tasks"] >= 1 and v["files"] >= 1
    dl = c.get("/api/admin/backup/%s/download" % name)
    assert dl.status_code == 200 and dl.content[:2] == b"\x1f\x8b"
    # Geheimnisse sind nicht im Archiv
    with tarfile.open(fileobj=io.BytesIO(dl.content), mode="r:gz") as t:
        names = t.getnames()
    assert "openplan.db" in names and "manifest.json" in names and not any("jwt_secret" in n or "privkey" in n or "account.key" in n for n in names)
    # Pfadtricks werden abgelehnt
    for bad in ("../openplan.db", "openplan-backup-x.tar.gz", "%2e%2e%2fopenplan.db"):
        assert c.post("/api/admin/backup/%s/verify" % bad).status_code in (404, 405)
        assert c.get("/api/admin/backup/%s/download" % bad).status_code in (404, 405)
    # Wiederherstellen in ein leeres Zielverzeichnis
    target = tmp_path / "restore"
    target.mkdir()
    msg = backup.restore(backup.path_of(name), target)
    assert "Vorgänge" in msg and (target / "files" / "doku.txt").read_text() == "wichtig"
    conn = sqlite3.connect(str(target / "openplan.db"))
    assert conn.execute("SELECT COUNT(*) FROM tasks WHERE name='Sicherungstest'").fetchone()[0] == 1
    conn.close()
    # Defektes Archiv erkennen
    bad = tmp_path / "bk" / "openplan-backup-20200101-000000.tar.gz"
    bad.write_bytes(b"kaputt")
    assert not backup.verify(bad)["ok"]
    # Archiv mit Pfadausbruch wird nicht akzeptiert
    evil = tmp_path / "bk" / "openplan-backup-20200102-000000.tar.gz"
    with tarfile.open(evil, "w:gz") as t:
        ti = tarfile.TarInfo("../evil.txt"); ti.size = 1
        t.addfile(ti, io.BytesIO(b"x"))
    assert not backup.verify(evil)["ok"]
    # Löschen
    assert c.delete("/api/admin/backup/%s" % name).status_code == 200 and c.delete("/api/admin/backup/%s" % name).status_code == 404
    assert any(i["action"] == "backup.create" for i in c.get("/api/admin/audit?action=backup").json()["items"])
    assert _login("op_owner", PW + "op_owner").post("/api/admin/backup").status_code == 403


def test_backup_schedule_and_retention(c, tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "BACKUP_DIR", tmp_path / "bk2")
    now = dt.datetime.now()
    c.put("/api/admin/backup", json={"enabled": True, "hour": 23, "keep": 2})
    assert backup.run_scheduled(now.replace(hour=22, minute=0)) is None                   # vor der Uhrzeit
    c.put("/api/admin/backup", json={"hour": 0})
    first = backup.run_scheduled(now)
    assert first and backup.run_scheduled(now) is None                                     # nur einmal pro Tag
    for i in range(4):                                                                     # Aufbewahrung
        backup.create("test")
    assert backup.prune(2) >= 2 and len(backup.list_backups()) == 2
    assert c.put("/api/admin/backup", json={"hour": 30}).status_code == 422
    c.put("/api/admin/backup", json={"enabled": False})


# ── Kommentare / @-Erwähnung ────────────────────────────────────────────────
def test_comments_and_mentions(c, mails):
    owner, anna, ben, viewer, pid = team(c)
    r_ben = owner.post("/api/projects/%d/resources" % pid, json={"name": "Ben", "user_id": _IDS["op_ben"]}).json()["resources"][0]["id"]
    tid = add_task(owner, pid, "Verkabelung")
    owner.put("/api/tasks/%d/assignments" % tid, json=[{"resource_id": r_ben, "units": 100}])
    mails.clear()
    d = anna.post("/api/tasks/%d/comments" % tid, json={"body": "Hallo @op_owner und @OP_VIEWER, bitte prüfen. @niemand @op_anna"}).json()
    assert d["items"][-1]["username"] == "op_anna" and "op_owner" in d["people"] and d["items"][-1]["can_delete"]
    own = owner.get("/api/notifications").json()["items"]
    m = next(n for n in own if n["kind"] == "mention")
    assert "op_anna hat dich erwähnt" in m["title"] and m["link"] == "/project/%d?task=%d" % (pid, tid)
    assert any(n["kind"] == "mention" for n in viewer.get("/api/notifications").json()["items"])          # Groß-/Kleinschreibung egal
    assert not any(n["kind"] == "mention" for n in anna.get("/api/notifications").json()["items"])        # nicht an sich selbst
    bn = ben.get("/api/notifications").json()["items"]                                                    # Bearbeiter, nicht erwähnt
    assert any(n["kind"] == "comment" for n in bn) and not any(n["kind"] == "mention" for n in bn)
    assert {m["to"] for m in mails} == {"op_owner@corp.test", "op_viewer@corp.test", "op_ben@corp.test"}
    assert any("Hallo @op_owner" in m["text"] and "/project/%d?task=%d" % (pid, tid) in m["text"] for m in mails)
    # Anzahl im Plan, Rechte
    assert next(t for t in owner.get("/api/projects/%d" % pid).json()["tasks"] if t["id"] == tid)["comment_count"] == 1
    assert viewer.post("/api/tasks/%d/comments" % tid, json={"body": "darf nicht"}).status_code == 403
    assert viewer.get("/api/tasks/%d/comments" % tid).status_code == 200
    assert _login("op_ben", PW + "op_ben").post("/api/tasks/%d/comments" % tid, json={"body": "   "}).status_code == 422
    cid = d["items"][-1]["id"]
    assert ben.delete("/api/comments/%d" % cid).status_code == 403                                        # fremder Kommentar
    assert anna.delete("/api/comments/%d" % cid).status_code == 200
    d2 = ben.post("/api/tasks/%d/comments" % tid, json={"body": "Erledigt."}).json()
    assert owner.delete("/api/comments/%d" % d2["items"][-1]["id"]).status_code == 200                    # Verantwortlicher darf
    assert c.get("/api/tasks/%d/comments" % tid).json()["items"] == []


# ── Erinnerungen / Eskalation ───────────────────────────────────────────────
def test_reminders_due_overdue_escalation_blocked(c, mails):
    owner, anna, ben, viewer, pid = team(c)
    r_anna = owner.post("/api/projects/%d/resources" % pid, json={"name": "Anna", "user_id": _IDS["op_anna"]}).json()["resources"][0]["id"]
    t_due = add_task(owner, pid, "Fällig-Test", duration=3)
    t_blk = add_task(owner, pid, "Blockiert-Test", duration=20)
    t_pool = add_task(owner, pid, "Pool-Test", duration=2, pool=True)
    owner.put("/api/tasks/%d/assignments" % t_due, json=[{"resource_id": r_anna, "units": 100}])
    owner.put("/api/tasks/%d/assignments" % t_blk, json=[{"resource_id": r_anna, "units": 100}])
    d = owner.get("/api/projects/%d" % pid).json()
    fin = {t["id"]: dt.date.fromisoformat(t["finish"]) for t in d["tasks"]}
    conn = database.connect()
    conn.execute("DELETE FROM reminder_log"); conn.commit()
    reminders.save_settings(conn, {"due_days": 2, "escalate_days": 3, "blocked_days": 3}); conn.commit()
    anna_before = anna.get("/api/notifications").json()["unread"]
    mails.clear()
    # 1) kurz vor Fälligkeit
    r = reminders.check(conn, fin[t_due] - dt.timedelta(days=1), "https://openplan.corp.test"); conn.commit()
    assert r["due"] >= 1
    assert conn.execute("SELECT COUNT(*) FROM reminder_log WHERE key LIKE ?", ("overdue:%d:%%" % t_due,)).fetchone()[0] == 0
    n = [x for x in anna.get("/api/notifications").json()["items"] if x["kind"] == "due"]
    assert n and "Fällig morgen: Fällig-Test" in [x["title"] for x in n] and n[0]["link"].endswith("?task=%d" % t_due) or any(x["link"].endswith("?task=%d" % t_due) for x in n)
    pool_n = [x for x in owner.get("/api/notifications").json()["items"] if x["kind"] == "due" and "Pool-Test" in x["title"]]
    assert pool_n                                                                         # Pool-Paket ohne Bearbeiter -> Verantwortlicher
    assert any(m["to"] == "op_anna@corp.test" and "Fällig morgen" in m["subject"] for m in mails)
    # 2) nicht doppelt
    again = reminders.check(conn, fin[t_due] - dt.timedelta(days=1)); conn.commit()
    assert again["due"] == 0
    # 3) überfällig -> Bearbeiter; nach 3 Tagen zusätzlich Eskalation an den Verantwortlichen
    r = reminders.check(conn, fin[t_due] + dt.timedelta(days=1)); conn.commit()
    assert r["overdue"] >= 1
    assert conn.execute("SELECT COUNT(*) FROM reminder_log WHERE key LIKE ?", ("esc:%d:%%" % t_due,)).fetchone()[0] == 0     # noch keine Eskalation (nur 1 Tag)
    assert any(x["kind"] == "overdue" and "Fällig-Test" in x["title"] for x in anna.get("/api/notifications").json()["items"])
    r = reminders.check(conn, fin[t_due] + dt.timedelta(days=4)); conn.commit()
    assert r["escalation"] >= 1
    esc = [x for x in owner.get("/api/notifications").json()["items"] if x["kind"] == "escalation" and "Fällig-Test" in x["title"]]
    assert esc and "seit 4 Tagen überfällig" in esc[0]["title"]
    assert any(m["to"] == "op_owner@corp.test" and "Eskalation" in m["subject"] for m in mails)
    # 4) blockiert seit n Tagen
    owner.patch("/api/tasks/%d" % t_blk, json={"status": "blocked", "status_note": "Teil fehlt"})
    since = conn.execute("SELECT status_since FROM tasks WHERE id=?", (t_blk,)).fetchone()[0]
    assert since == dt.date.today().isoformat()                                           # Trigger setzt „seit"
    reminders.check(conn, dt.date.today() + dt.timedelta(days=1)); conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM reminder_log WHERE key LIKE ?", ("blk:%d:%%" % t_blk,)).fetchone()[0] == 0   # erst nach 3 Tagen
    r = reminders.check(conn, dt.date.today() + dt.timedelta(days=3)); conn.commit()
    assert r["blocked"] >= 1
    assert any(x["kind"] == "blocked" and "Teil fehlt" in x["body"] for x in owner.get("/api/notifications").json()["items"])
    conn.close()
    assert anna.get("/api/notifications").json()["unread"] > anna_before


def test_reminder_settings_and_schedule(c):
    conn = database.connect()
    conn.execute("DELETE FROM app_settings WHERE key IN ('reminders','reminders_state')"); conn.commit()
    s = c.get("/api/admin/settings/reminders").json()
    assert s["enabled"] and s["due_days"] == 2 and s["escalate_days"] == 3
    assert c.put("/api/admin/settings/reminders", json={"due_days": 99}).status_code == 422
    assert c.put("/api/admin/settings/reminders", json={"hour": 6, "enabled": True}).json()["hour"] == 6
    assert reminders.run_due(dt.datetime(2026, 10, 20, 5, 0)) is None                         # vor der Uhrzeit
    assert reminders.run_due(dt.datetime(2026, 10, 20, 6, 30)) is not None                    # läuft
    assert reminders.run_due(dt.datetime(2026, 10, 20, 12, 0)) is None                        # nur einmal am Tag
    assert reminders.run_due(dt.datetime(2026, 10, 21, 6, 30)) is not None
    c.put("/api/admin/settings/reminders", json={"enabled": False})
    assert reminders.run_due(dt.datetime(2026, 10, 22, 8, 0)) is None
    assert c.post("/api/admin/reminders/run").status_code == 200
    c.put("/api/admin/settings/reminders", json={"enabled": True})
    conn.close()


# ── Erledigungszeitraum (von = Beginn frühestens, bis = Frist) ──────────────
def test_completion_window(c, mails):
    owner, anna, ben, viewer, pid = team(c)
    d = owner.post("/api/projects/%d/tasks" % pid, json={"name": "Zeitraum-Paket", "duration": 3, "pool": True, "constraint_type": "SNET",
                                                         "constraint_date": "2026-11-02", "deadline": "2026-11-04"}).json()
    t = next(x for x in d["tasks"] if x["name"] == "Zeitraum-Paket")
    assert t["start"] >= "2026-11-02" and t["deadline"] == "2026-11-04" and t["pool"]
    assert t["deadline_missed"] is False or t["finish"] > "2026-11-04"
    tid = t["id"]
    # „von“ nach „bis“ wird abgelehnt (Anlegen und Ändern)
    assert owner.post("/api/projects/%d/tasks" % pid, json={"name": "x", "constraint_type": "SNET", "constraint_date": "2026-11-10", "deadline": "2026-11-01"}).status_code == 422
    assert owner.patch("/api/tasks/%d" % tid, json={"deadline": "2026-10-01"}).status_code == 422
    # Länger als der Zeitraum -> Frist überschritten
    d = owner.patch("/api/tasks/%d" % tid, json={"duration": 10}).json()
    t = next(x for x in d["tasks"] if x["id"] == tid)
    assert t["deadline_missed"] is True and t["finish"] > "2026-11-04"
    # erledigt -> kein Verstoß mehr; Frist entfernen
    d = owner.patch("/api/tasks/%d" % tid, json={"status": "done"}).json()
    assert next(x for x in d["tasks"] if x["id"] == tid)["deadline_missed"] is False
    d = owner.patch("/api/tasks/%d" % tid, json={"clear_deadline": True}).json()
    assert next(x for x in d["tasks"] if x["id"] == tid)["deadline"] is None
    # Rückgängig stellt die Frist wieder her
    d = owner.post("/api/projects/%d/undo" % pid).json()
    assert next(x for x in d["tasks"] if x["id"] == tid)["deadline"] == "2026-11-04"
    assert any("Frist" in j["detail"] for j in owner.get("/api/projects/%d/journal" % pid).json())


def test_reminders_use_deadline(c, mails):
    owner, anna, ben, viewer, pid = team(c)
    r = owner.post("/api/projects/%d/resources" % pid, json={"name": "Anna", "user_id": _IDS["op_anna"]}).json()["resources"][0]["id"]
    d = owner.post("/api/projects/%d/tasks" % pid, json={"name": "Frist-Paket", "duration": 20, "deadline": "2026-12-07"}).json()
    tid = max(t["id"] for t in d["tasks"])
    finish = next(t for t in d["tasks"] if t["id"] == tid)["finish"]
    assert finish != "2026-12-07"
    owner.put("/api/tasks/%d/assignments" % tid, json=[{"resource_id": r, "units": 100}])
    conn = database.connect()
    conn.execute("DELETE FROM reminder_log"); conn.commit()
    mails.clear()
    reminders.check(conn, dt.date(2026, 12, 6)); conn.commit()                      # einen Tag vor der FRIST (nicht vor dem Planende)
    assert conn.execute("SELECT COUNT(*) FROM reminder_log WHERE key=?", ("due:%d:2026-12-07" % tid,)).fetchone()[0] == 1
    assert any(m["to"] == "op_anna@corp.test" and "Fällig morgen: Frist-Paket" in m["subject"] and "Frist: 2026-12-07" in m["text"] for m in mails)
    conn.close()
