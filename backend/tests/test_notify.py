from test_api import _login, c  # noqa: F401,E402  (setzt DATA_DIR/ADMIN_PASSWORD vor allen App-Importen)

import datetime as dt  # noqa: E402

import pytest  # noqa: E402

import database  # noqa: E402
import mailer  # noqa: E402
import portfolio  # noqa: E402
import reports  # noqa: E402

PW = "passwort-"
_IDS = {}


@pytest.fixture()
def mails(monkeypatch):
    """Mailversand abfangen (synchron)."""
    sent = []
    monkeypatch.setattr(mailer, "run_async", False)
    monkeypatch.setattr(mailer, "send_now", lambda s, to, subject, text, html=None: sent.append({"to": to, "subject": subject, "text": text, "html": html}))
    return sent


def team(c):
    if not _IDS:
        for n, mail in (("nt_owner", "owner@corp.test"), ("nt_anna", "anna@corp.test"), ("nt_ben", "")):
            _IDS[n] = c.post("/api/users", json={"username": n, "password": PW + n, "role": "editor"}).json()["id"]
            if mail:
                c.put("/api/users/%d/email" % _IDS[n], json={"email": mail})
    owner, anna, ben = (_login(n, PW + n) for n in ("nt_owner", "nt_anna", "nt_ben"))
    pid = owner.post("/api/projects", json={"name": "Notify", "start_date": "2026-10-12"}).json()["project"]["id"]
    owner.put("/api/projects/%d/members" % pid, json=[{"user_id": _IDS["nt_anna"], "role": "editor"}, {"user_id": _IDS["nt_ben"], "role": "editor"}])
    return owner, anna, ben, pid


def setup_mail(c, **kw):
    c.put("/api/admin/settings/mail", json={"enabled": True, "host": "smtp.corp.test", "port": 25, "from_addr": "openplan@corp.test",
                                           "public_url": "https://openplan.corp.test", **kw})


def test_assignment_notification_with_link_and_mail(c, mails):
    owner, anna, ben, pid = team(c)
    setup_mail(c)
    r_anna = owner.post("/api/projects/%d/resources" % pid, json={"name": "Anna", "user_id": _IDS["nt_anna"]}).json()["resources"][0]["id"]
    d = owner.post("/api/projects/%d/tasks" % pid, json={"name": "Switch tauschen", "duration": 2}).json()
    tid = max(t["id"] for t in d["tasks"])
    owner.put("/api/tasks/%d/assignments" % tid, json=[{"resource_id": r_anna, "units": 100}])
    n = anna.get("/api/notifications").json()
    assert n["unread"] == 1 and n["items"][0]["kind"] == "assigned" and n["items"][0]["link"] == "/project/%d?task=%d" % (pid, tid)
    assert "Switch tauschen" in n["items"][0]["title"] and n["items"][0]["project_name"] == "Notify"
    assert len(mails) == 1 and mails[0]["to"] == "anna@corp.test"
    assert "https://openplan.corp.test/project/%d?task=%d" % (pid, tid) in mails[0]["text"] and "nt_owner" in mails[0]["text"]
    assert 'href="https://openplan.corp.test/project/%d?task=%d"' % (pid, tid) in mails[0]["html"]
    # erneutes Speichern ohne Änderung: keine zweite Nachricht
    owner.put("/api/tasks/%d/assignments" % tid, json=[{"resource_id": r_anna, "units": 50}])
    assert anna.get("/api/notifications").json()["unread"] == 1 and len(mails) == 1
    # Entzug wird gemeldet; eigene Änderungen nicht
    owner.put("/api/tasks/%d/assignments" % tid, json=[])
    items = anna.get("/api/notifications").json()["items"]
    assert items[0]["kind"] == "unassigned" and len(mails) == 2
    anna.put("/api/tasks/%d/assignments" % tid, json=[{"resource_id": r_anna, "units": 100}])
    assert anna.get("/api/notifications").json()["unread"] == 2                      # nichts Neues für sich selbst
    # Lesen
    nid = items[0]["id"]
    assert anna.post("/api/notifications/%d/read" % nid).json()["unread"] == 1
    assert ben.post("/api/notifications/%d/read" % nid).json()["unread"] == 0        # fremde Benachrichtigung bleibt unberührt
    assert anna.get("/api/notifications").json()["unread"] == 1
    assert anna.post("/api/notifications/read-all").json()["unread"] == 0


def test_no_mail_without_address_optout_or_config(c, mails):
    owner, anna, ben, pid = team(c)
    setup_mail(c)
    r_ben = owner.post("/api/projects/%d/resources" % pid, json={"name": "Ben", "user_id": _IDS["nt_ben"]}).json()["resources"][0]["id"]
    tid = max(t["id"] for t in owner.post("/api/projects/%d/tasks" % pid, json={"name": "A"}).json()["tasks"])
    owner.put("/api/tasks/%d/assignments" % tid, json=[{"resource_id": r_ben, "units": 100}])
    assert ben.get("/api/notifications").json()["unread"] == 1 and mails == []        # Glocke ja, Mail mangels Adresse nein
    ben.put("/api/auth/profile", json={"email": "ben@corp.test", "notify_email": False})
    owner.put("/api/tasks/%d/assignments" % tid, json=[])
    owner.put("/api/tasks/%d/assignments" % tid, json=[{"resource_id": r_ben, "units": 100}])
    assert mails == []                                                                 # Opt-out
    ben.put("/api/auth/profile", json={"notify_email": True})
    c.put("/api/admin/settings/mail", json={"enabled": False})
    owner.put("/api/tasks/%d/assignments" % tid, json=[])
    owner.put("/api/tasks/%d/assignments" % tid, json=[{"resource_id": r_ben, "units": 100}])
    assert mails == []                                                                 # Mailversand abgeschaltet
    assert ben.put("/api/auth/profile", json={"email": "kaputt"}).status_code == 422


def test_mail_settings_api(c, mails):
    assert c.put("/api/admin/settings/mail", json={"enabled": True, "host": "", "from_addr": "x@y.de"}).status_code == 422
    assert c.put("/api/admin/settings/mail", json={"public_url": "ftp://x"}).status_code == 422
    s = c.put("/api/admin/settings/mail", json={"enabled": True, "host": "smtp.corp.test", "from_addr": "op@corp.test", "username": "u", "password": "geheim"}).json()
    assert s["password_set"] is True and "password" not in s
    s = c.put("/api/admin/settings/mail", json={"password": ""}).json()           # leer = unverändert
    assert s["password_set"] is True and mailer.settings(database.connect())["password"] == "geheim"
    t = c.post("/api/admin/settings/mail/test", json={"to": "admin@corp.test"}).json()
    assert t["ok"] and mails[-1]["to"] == "admin@corp.test"
    assert c.post("/api/admin/settings/mail/test", json={"to": "nix"}).status_code == 422

    def boom(*a, **k):
        raise OSError("Connection refused")
    mailer.send_now = boom
    t = c.post("/api/admin/settings/mail/test", json={"to": "admin@corp.test"}).json()
    assert not t["ok"] and "Connection refused" in t["message"]
    assert c.put("/api/admin/settings/mail", json={"clear_password": True}).json()["password_set"] is False


def test_project_report_and_schedule(c, mails):
    owner, anna, ben, pid = team(c)
    setup_mail(c)
    r_anna = owner.post("/api/projects/%d/resources" % pid, json={"name": "Anna", "user_id": _IDS["nt_anna"]}).json()["resources"][0]["id"]
    past = (dt.date.today() - dt.timedelta(days=30)).isoformat()
    owner.patch("/api/projects/%d" % pid, json={"start_date": past})
    t1 = max(t["id"] for t in owner.post("/api/projects/%d/tasks" % pid, json={"name": "Überfälliges", "duration": 3}).json()["tasks"])
    t2 = max(t["id"] for t in owner.post("/api/projects/%d/tasks" % pid, json={"name": "Blockiertes", "duration": 3}).json()["tasks"])
    owner.patch("/api/tasks/%d" % t2, json={"status": "blocked", "status_note": "wartet auf Lieferant"})
    owner.post("/api/projects/%d/tasks" % pid, json={"name": "Pool-Paket", "duration": 2, "pool": True})
    owner.put("/api/tasks/%d/assignments" % t1, json=[{"resource_id": r_anna, "units": 100}])
    prev = owner.get("/api/projects/%d/report/preview" % pid).json()
    assert "Überfälliges" in prev["html"] and "wartet auf Lieferant" in prev["html"] and "Pool-Paket" in prev["html"]
    assert anna.get("/api/projects/%d/report/preview" % pid).status_code == 403          # nur Verantwortliche
    # Einstellungen + Versand an alle Mitglieder
    d = owner.patch("/api/projects/%d" % pid, json={"report_enabled": True, "report_weekday": 0, "report_hour": 6, "report_to": "members"}).json()
    assert d["project"]["report_enabled"] == 1 and d["project"]["report_to"] == "members"
    ben.put("/api/auth/profile", json={"email": ""})                                      # Ben ohne Adresse (Zustand aus Vortests unabhängig machen)
    mails.clear()
    r = owner.post("/api/projects/%d/report/send" % pid).json()
    assert r["notified"] == 3 and r["mails"] == 2 and r["without_email"] == 1              # Ben hat keine Adresse
    to = {m["to"]: m for m in mails}
    assert "Deine offenen Vorgänge" in to["anna@corp.test"]["text"] and "Deine offenen Vorgänge" not in to["owner@corp.test"]["text"]
    assert "/project/%d?task=%d" % (pid, t1) in to["anna@corp.test"]["text"]
    rep = anna.get("/api/notifications").json()["items"][0]
    assert rep["kind"] == "report" and rep["link"] == "/project/%d" % pid
    # Zeitplan: montags ab 6 Uhr, einmal pro Tag
    conn = database.connect()
    conn.execute("UPDATE projects SET report_last=NULL WHERE id=?", (pid,)); conn.commit()
    monday = dt.datetime(2026, 10, 19, 6, 30)
    assert pid in reports.due(conn, monday)
    assert pid not in reports.due(conn, dt.datetime(2026, 10, 19, 5, 59)) and pid not in reports.due(conn, dt.datetime(2026, 10, 20, 8, 0))
    assert reports.run_due(monday) >= 1
    assert pid not in reports.due(database.connect(), monday)
    conn.close()


def test_portfolio_and_costcenter_reports(c, mails):
    owner, anna, ben, pid = team(c)
    setup_mail(c)
    past = (dt.date.today() - dt.timedelta(days=20)).isoformat()
    owner.patch("/api/projects/%d" % pid, json={"start_date": past})
    t1 = max(t["id"] for t in owner.post("/api/projects/%d/tasks" % pid, json={"name": "Alt", "duration": 3}).json()["tasks"])   # überfällig
    cc = owner.post("/api/projects/%d/cost-centers" % pid, json={"code": "0000777001", "name": "Netz"}).json()["cost_centers"][0]["id"]
    owner.put("/api/projects/%d/budget-lines" % pid, json=[{"cost_center_id": cc, "amount": 1000}])
    owner.post("/api/projects/%d/actuals" % pid, json={"booking_date": past, "amount": 1200, "task_id": t1, "cost_center_id": cc})

    boss = c.post("/api/users", json={"username": "nt_boss", "password": PW + "boss", "role": "viewer"}).json()["id"]
    c.put("/api/users/%d/email" % boss, json={"email": "boss@corp.test"})
    # Vorgesetzter (kein Projektmitglied): Portfolio nur für dieses Projekt, mit Kosten
    sub = c.post("/api/admin/reports", json={"user_id": boss, "kind": "portfolio", "name": "Wochenbericht Abteilung", "project_ids": [pid], "include_costs": True, "weekday": -1}).json()
    boss_c = _login("nt_boss", PW + "boss")
    assert boss_c.get("/api/projects/%d" % pid).status_code == 404                           # Projektzugriff hat er nicht …
    v = boss_c.get("/api/reports/%d" % sub["id"]).json()                                       # … aber den Report
    assert "Notify" in v["html"] and "überfällig" in v["html"] and "Budget" in v["html"]
    assert anna.get("/api/reports/%d" % sub["id"]).status_code == 404                        # fremder Report
    assert c.get("/api/reports/%d" % sub["id"]).status_code == 200                           # Admin darf
    lines = portfolio.build_portfolio(database.connect(), {"project_ids": str(pid), "include_costs": 1, "name": "x"})
    pl = lines["projects"][0]
    assert pl["rag"] == "red" and pl["cost"]["over"] is True and pl["overdue"] == 1          # Ist 1200 > Budget 1000
    nocost = c.post("/api/admin/reports", json={"user_id": boss, "kind": "portfolio", "project_ids": [pid]}).json()
    assert "Budget" not in boss_c.get("/api/reports/%d" % nocost["id"]).json()["html"].replace("Projektbudget", "")

    # Kostenstellenverantwortlicher: sieht nur Summen seiner Kostenstelle (führende Nullen egal)
    cco = c.post("/api/users", json={"username": "nt_cc", "password": PW + "cc", "role": "viewer"}).json()["id"]
    c.put("/api/users/%d/email" % cco, json={"email": "cc@corp.test"})
    assert c.put("/api/admin/cost-owners", json=[{"code": "777001", "name": "Netzwerk", "user_id": cco}, {"code": "0777001", "user_id": cco}]).status_code == 422
    o = c.put("/api/admin/cost-owners", json=[{"code": "777001", "name": "Netzwerk", "user_id": cco}]).json()
    assert o["owners"][0]["username"] == "nt_cc" and "0000777001" in o["known_codes"]
    cs = c.post("/api/admin/reports", json={"user_id": cco, "kind": "costcenter", "name": "Kostenstelle 777001", "weekday": 0}).json()
    cc_c = _login("nt_cc", PW + "cc")
    rep = portfolio.build_costcenter(database.connect(), {"user_id": cco, "project_ids": "", "name": "k"})
    rows = [r for r in rep["rows"] if not r.get("total")]
    tot = [r for r in rep["rows"] if r.get("total")][0]
    assert rows[0]["project"] == "Notify" and rows[0]["budget"] == 1000 and rows[0]["actual"] == 1200 and rows[0]["over"]
    assert tot["remaining"] == -200 and tot["over"]
    html = cc_c.get("/api/reports/%d" % cs["id"]).json()["html"]
    assert "Notify" in html and "1.200 €" in html and "Alt" not in html                          # keine Vorgangsdetails
    assert cc_c.get("/api/reports/%d" % sub["id"]).status_code == 404
    assert cc_c.get("/api/admin/reports").status_code == 403
    # Versand: Glocke mit Link auf den Online-Report, Mail mit absolutem Link
    mails.clear()
    assert c.post("/api/admin/reports/%d/send" % cs["id"]).json()["mails"] == 1
    n = cc_c.get("/api/notifications").json()["items"][0]
    assert n["link"] == "/reports/%d" % cs["id"] and "https://openplan.corp.test/reports/%d" % cs["id"] in mails[0]["text"]
    assert cc_c.get("/api/reports/mine").json()[0]["id"] == cs["id"]
    # Zeitplan: werktäglich / Wochentag
    conn = database.connect()
    assert sub["id"] in portfolio.due(conn, dt.datetime(2026, 10, 21, 8, 0)) and sub["id"] not in portfolio.due(conn, dt.datetime(2026, 10, 24, 8, 0))   # Mi ja, Sa nein
    c.delete("/api/admin/reports/%d" % nocost["id"])
    conn.close()


def test_profile_language_and_theme(c):
    me = c.get("/api/auth/me").json()
    assert me["lang"] in (None, "de") and me["theme"] in (None, "auto")                                  # Standard: Deutsch, Systemmodus
    r = c.put("/api/auth/profile", json={"lang": "en", "theme": "dark"}).json()
    assert r["lang"] == "en" and r["theme"] == "dark" and c.get("/api/auth/me").json()["lang"] == "en"
    assert c.put("/api/auth/profile", json={"lang": "fr"}).status_code == 422
    assert c.put("/api/auth/profile", json={"theme": "blau"}).status_code == 422
    c.put("/api/auth/profile", json={"lang": "de", "theme": "auto"})


def test_texts_follow_recipient_language(c, mails):
    """Glocke, Mail, Report und Erinnerung entstehen in der Sprache des Empfängers (users.lang)."""
    owner, anna, ben, pid = team(c)
    setup_mail(c)
    r_anna = owner.post("/api/projects/%d/resources" % pid, json={"name": "Anna", "user_id": _IDS["nt_anna"]}).json()["resources"][0]["id"]
    past = (dt.date.today() - dt.timedelta(days=30)).isoformat()
    owner.patch("/api/projects/%d" % pid, json={"start_date": past})
    tid = max(t["id"] for t in owner.post("/api/projects/%d/tasks" % pid, json={"name": "Sprachtest", "duration": 3}).json()["tasks"])
    anna.put("/api/auth/profile", json={"lang": "en", "email": "anna@corp.test", "notify_email": True})
    mails.clear()
    owner.put("/api/tasks/%d/assignments" % tid, json=[{"resource_id": r_anna, "units": 100}])
    n = anna.get("/api/notifications").json()["items"][0]
    assert n["title"] == "Task assigned: Sprachtest" and "Assigned by" in n["body"]
    assert mails[0]["subject"] == "Task assigned: Sprachtest" and "Open in OpenPlan" in mails[0]["html"]
    # Erinnerung (überfällig) – Anna englisch, Eskalation an den Verantwortlichen deutsch
    import reminders
    conn = database.connect()
    try:
        reminders.check(conn, base="https://openplan.corp.test")
        conn.commit()
    finally:
        conn.close()
    titles = [i["title"] for i in anna.get("/api/notifications").json()["items"]]
    assert any(t.startswith("Overdue for") for t in titles)
    assert any(i["title"].startswith("Eskalation") for i in owner.get("/api/notifications").json()["items"])
    # Projektreport: Empfänger Anna (Mitglied) englisch
    owner.patch("/api/projects/%d" % pid, json={"report_to": "members"})
    mails.clear()
    owner.post("/api/projects/%d/report/send" % pid)
    to = {m["to"]: m for m in mails}
    assert "Your open tasks" in to["anna@corp.test"]["text"] and "Project report" in to["anna@corp.test"]["subject"]
    assert "Projektreport" in to["owner@corp.test"]["subject"]
    anna.put("/api/auth/profile", json={"lang": "de"})


def test_my_tasks_across_projects(c):
    owner, anna, ben, pid = team(c)
    r_anna = owner.post("/api/projects/%d/resources" % pid, json={"name": "AnnaT", "user_id": _IDS["nt_anna"]}).json()["resources"][0]["id"]
    owner.patch("/api/projects/%d" % pid, json={"start_date": (dt.date.today() - dt.timedelta(days=30)).isoformat()})
    t_late = max(t["id"] for t in owner.post("/api/projects/%d/tasks" % pid, json={"name": "Todo-Überfällig", "duration": 3}).json()["tasks"])
    t_done = max(t["id"] for t in owner.post("/api/projects/%d/tasks" % pid, json={"name": "Todo-Fertig", "duration": 1}).json()["tasks"])
    t_other = max(t["id"] for t in owner.post("/api/projects/%d/tasks" % pid, json={"name": "Todo-Fremd", "duration": 1}).json()["tasks"])
    for t in (t_late, t_done):
        owner.put("/api/tasks/%d/assignments" % t, json=[{"resource_id": r_anna, "units": 100}])
    owner.patch("/api/tasks/%d" % t_done, json={"status": "done"})
    mine = anna.get("/api/my-tasks").json()
    names = [i["name"] for i in mine["items"] if i["project"] == "Notify"]
    assert "Todo-Überfällig" in names and "Todo-Fertig" not in names and "Todo-Fremd" not in names       # nur offene, nur eigene
    late = next(i for i in mine["items"] if i["name"] == "Todo-Überfällig")
    assert late["bucket"] == "overdue" and late["pid"] == pid
    assert ben.get("/api/my-tasks").json()["items"] == [] or all(i["name"] != "Todo-Überfällig" for i in ben.get("/api/my-tasks").json()["items"])
    # Erledigen über den Status-Endpunkt entfernt sie aus der Liste
    anna.post("/api/projects/%d/tasks/status" % pid, json={"task_ids": [t_late], "status": "done"})
    assert all(i["name"] != "Todo-Überfällig" for i in anna.get("/api/my-tasks").json()["items"])
