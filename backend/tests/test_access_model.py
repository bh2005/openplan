from test_api import _login, c  # noqa: F401,E402  (setzt DATA_DIR/ADMIN_PASSWORD vor allen App-Importen)

PW = "passwort-"


def _mk(c, name, role="editor", **kw):
    return c.post("/api/users", json={"username": name, "password": PW + name, "role": role, **kw}).json()["id"]


def test_worker_access_via_assignment_and_view_all(c):
    ids = {n: _mk(c, n) for n in ("am_owner", "am_carla")}
    ids["am_auditor"] = _mk(c, "am_auditor", "viewer", see_all=True)
    ids["am_plain"] = _mk(c, "am_plain", "viewer")
    owner, carla, auditor, plain = (_login(n, PW + n) for n in ("am_owner", "am_carla", "am_auditor", "am_plain"))
    pid = owner.post("/api/projects", json={"name": "AccessModel", "start_date": "2026-10-12"}).json()["project"]["id"]
    t1 = max(t["id"] for t in owner.post("/api/projects/%d/tasks" % pid, json={"name": "Eigene Aufgabe", "duration": 2}).json()["tasks"])
    t2 = max(t["id"] for t in owner.post("/api/projects/%d/tasks" % pid, json={"name": "Fremde Aufgabe", "duration": 2}).json()["tasks"])
    pool = max(t["id"] for t in owner.post("/api/projects/%d/tasks" % pid, json={"name": "Pool", "duration": 1, "pool": True}).json()["tasks"])

    # ohne Zuordnung: unsichtbar (A sieht nur seine Projekte)
    assert carla.get("/api/projects/%d" % pid).status_code == 404
    assert pid not in [p["id"] for p in carla.get("/api/projects").json()]

    # Zuordnung per Benutzer: Ressource entsteht bei Bedarf, Mitarbeiter-Zugriff ergibt sich daraus
    d = owner.put("/api/tasks/%d/assignments" % t1, json=[{"user_id": ids["am_carla"], "units": 100}]).json()
    res = [r for r in d["resources"] if r["user_id"] == ids["am_carla"]]
    assert len(res) == 1 and res[0]["name"] == "am_carla"
    owner.put("/api/tasks/%d/assignments" % t1, json=[{"resource_id": res[0]["id"], "units": 50}])   # erneut per Ressource: keine zweite
    assert len([r for r in owner.get("/api/projects/%d" % pid).json()["resources"] if r["user_id"] == ids["am_carla"]]) == 1
    g = carla.get("/api/projects/%d" % pid)
    assert g.status_code == 200 and g.json()["access"] == "work"
    assert pid in [p["id"] for p in carla.get("/api/projects").json()]

    # Mitarbeiter darf: Status/Fortschritt/Notiz eigener Vorgänge, Kommentare, Dokumente, Pool übernehmen
    assert carla.patch("/api/tasks/%d" % t1, json={"status": "in_progress", "percent": 40}).status_code == 200
    assert carla.post("/api/projects/%d/tasks/status" % pid, json={"task_ids": [t1], "status": "blocked"}).status_code == 200
    assert carla.post("/api/tasks/%d/comments" % t1, json={"body": "Läuft"}).status_code in (200, 201)
    assert carla.post("/api/tasks/%d/links" % t1, json={"url": "https://example.sharepoint.com/doc"}).status_code == 201
    assert carla.post("/api/tasks/%d/claim" % pool).status_code == 200
    # … aber nicht: planen, fremde Vorgänge, zuordnen, Projekt ändern
    assert carla.patch("/api/tasks/%d" % t1, json={"name": "Umbenannt"}).status_code == 403
    assert carla.patch("/api/tasks/%d" % t1, json={"duration": 9}).status_code == 403
    assert carla.patch("/api/tasks/%d" % t2, json={"status": "done"}).status_code == 403
    assert carla.post("/api/projects/%d/tasks/status" % pid, json={"task_ids": [t2], "status": "done"}).status_code == 403
    assert carla.post("/api/tasks/%d/comments" % t2, json={"body": "x"}).status_code == 403
    assert carla.put("/api/tasks/%d/assignments" % t2, json=[]).status_code == 403
    assert carla.post("/api/projects/%d/tasks" % pid, json={"name": "Neu"}).status_code == 403
    assert carla.get("/api/projects/%d/budget" % pid).status_code == 403                               # keine Kosten

    # Zuordnung entfernt -> Zugriff weg (Pool-Zuordnung bleibt: noch Mitarbeiter über Pool-Paket)
    carla.post("/api/tasks/%d/release" % pool)
    owner.put("/api/tasks/%d/assignments" % t1, json=[])
    assert carla.get("/api/projects/%d" % pid).status_code == 404

    # B: „Betrachter alle Projekte“ sieht alles, ändert nichts, Kosten nur bei Freigabe
    assert auditor.get("/api/projects/%d" % pid).json()["access"] == "view"
    assert pid in [p["id"] for p in auditor.get("/api/projects").json()]
    assert auditor.patch("/api/tasks/%d" % t1, json={"status": "done"}).status_code == 403
    assert auditor.post("/api/projects", json={"name": "x", "start_date": "2026-10-12"}).status_code == 403
    assert auditor.get("/api/projects/%d/budget" % pid).status_code == 403
    assert plain.get("/api/projects/%d" % pid).status_code == 404                                       # normaler viewer: nur eigene
    # Admin schaltet das Flag um
    assert c.put("/api/users/%d/see-all" % ids["am_plain"], json={"see_all": True}).status_code == 200
    assert plain.get("/api/projects/%d" % pid).status_code == 200
    assert c.put("/api/users/%d/see-all" % ids["am_plain"], json={"see_all": False}).status_code == 200
    assert plain.get("/api/projects/%d" % pid).status_code == 404
    assert owner.put("/api/users/%d/see-all" % ids["am_plain"], json={"see_all": True}).status_code == 403   # nur Admin


def test_user_directory_search(c):
    _mk(c, "dir_zora"); _mk(c, "dir_zeno")
    names = [u["username"] for u in c.get("/api/users/directory?q=dir_z&limit=5").json()]
    assert names == ["dir_zeno", "dir_zora"]
    assert len(c.get("/api/users/directory?limit=1").json()) == 1
    assert len(c.get("/api/users/directory").json()) >= 2


def test_admin_changes_role(c):
    uid = _mk(c, "rc_user", "viewer", see_all=True)
    user = _login("rc_user", PW + "rc_user")
    assert user.post("/api/projects", json={"name": "RC", "start_date": "2026-10-12"}).status_code == 403   # viewer darf nicht anlegen
    assert user.put("/api/users/%d/role" % uid, json={"role": "admin"}).status_code == 403                 # nur Admin
    assert c.put("/api/users/%d/role" % uid, json={"role": "editor"}).status_code == 200                     # wirkt sofort
    row = next(u for u in c.get("/api/users").json() if u["id"] == uid)
    assert row["role"] == "editor" and not row["see_all"]                                                    # see_all gilt nur für viewer
    pid = user.post("/api/projects", json={"name": "RC", "start_date": "2026-10-12"}).json()["project"]["id"]
    assert c.put("/api/users/%d/role" % uid, json={"role": "viewer"}).status_code == 409                    # Verantwortlicher
    assert c.put("/api/users/%d/role" % uid, json={"role": "chef"}).status_code == 422
    assert c.put("/api/users/99999/role", json={"role": "editor"}).status_code == 404
    admin_id = next(u["id"] for u in c.get("/api/users").json() if u["username"] == "admin")
    assert c.put("/api/users/%d/role" % admin_id, json={"role": "editor"}).status_code == 400               # nicht die eigene Rolle
    assert pid


def test_admin_sets_local_password(c):
    uid = _mk(c, "pw_user")
    user = _login("pw_user", PW + "pw_user")
    assert user.put("/api/users/%d/password" % uid, json={"new_password": "irgendwas-123"}).status_code == 403   # nur Admin
    assert c.put("/api/users/%d/password" % uid, json={"new_password": "kurz"}).status_code == 422
    assert c.put("/api/users/%d/password" % uid, json={"new_password": "neues-passwort-1"}).status_code == 200
    assert c.post("/api/auth/login", json={"username": "pw_user", "password": PW + "pw_user"}).status_code == 401
    assert c.post("/api/auth/login", json={"username": "pw_user", "password": "neues-passwort-1"}).status_code == 200
    assert c.put("/api/users/99999/password", json={"new_password": "neues-passwort-1"}).status_code == 404
    admin_id = next(u["id"] for u in c.get("/api/users").json() if u["username"] == "admin")
    assert c.put("/api/users/%d/password" % admin_id, json={"new_password": "neues-passwort-1"}).status_code == 400   # eigenes: Altpasswort nötig
    ldap_id = c.post("/api/users", json={"username": "pw_ad", "role": "editor", "source": "ldap"}).json()["id"]
    assert c.put("/api/users/%d/password" % ldap_id, json={"new_password": "neues-passwort-1"}).status_code == 400   # AD verwaltet es selbst


def test_display_name_search_and_edit(c):
    uid = c.post("/api/users", json={"username": "dn_k001", "display_name": "Zacharias Quirl", "password": PW + "dn", "role": "editor"}).json()["id"]
    hits = c.get("/api/users/directory?q=quirl&limit=5").json()                       # Suche nach Anzeigename
    assert [h["username"] for h in hits] == ["dn_k001"] and hits[0]["display_name"] == "Zacharias Quirl"
    assert [h["username"] for h in c.get("/api/users/directory?q=dn_k0&limit=5").json()] == ["dn_k001"]   # ... und nach ID
    assert c.put("/api/users/%d/display-name" % uid, json={"display_name": "  Zack Quirl "}).status_code == 200
    assert next(u for u in c.get("/api/users").json() if u["id"] == uid)["display_name"] == "Zack Quirl"
    user = _login("dn_k001", PW + "dn")
    assert user.get("/api/auth/me").json()["display_name"] == "Zack Quirl"
    assert user.put("/api/users/%d/display-name" % uid, json={"display_name": "x"}).status_code == 403   # nur Admin
    ad = c.post("/api/users", json={"username": "dn_ad", "role": "editor", "source": "ldap"}).json()["id"]
    assert c.put("/api/users/%d/display-name" % ad, json={"display_name": "x"}).status_code == 400       # AD liefert ihn selbst
    pid = user.post("/api/projects", json={"name": "DN", "start_date": "2026-10-12"}).json()["project"]["id"]
    assert user.get("/api/projects/%d" % pid).json()["project"]["owner"]["display_name"] == "Zack Quirl"
    rid = user.post("/api/projects/%d/resources" % pid, json={"name": "Zack", "user_id": uid}).json()["resources"][0]["id"]
    assert rid


def test_resource_link_to_any_user_has_label(c):
    uid = c.post("/api/users", json={"username": "rl_k001", "display_name": "Holzer, Bernd", "password": PW + "rl", "role": "editor"}).json()["id"]
    plain = _mk(c, "rl_plain")
    pid = c.post("/api/projects", json={"name": "RL", "start_date": "2026-10-12"}).json()["project"]["id"]
    d = c.post("/api/projects/%d/resources" % pid, json={"name": "Holzer, Bernd", "user_id": uid}).json()          # kein Mitglied, trotzdem verknüpfbar
    r1 = d["resources"][0]
    assert r1["user_id"] == uid and r1["user_label"] == "Holzer, Bernd (rl_k001)"
    d = c.post("/api/projects/%d/resources" % pid, json={"name": "Ohne Anzeigenamen", "user_id": plain}).json()
    assert next(r for r in d["resources"] if r["user_id"] == plain)["user_label"] == "rl_plain"
    d = c.post("/api/projects/%d/resources" % pid, json={"name": "Extern"}).json()
    assert next(r for r in d["resources"] if r["name"] == "Extern")["user_label"] == ""


def test_resource_function_per_project(c):
    uid = _mk(c, "fn_user")
    p1 = c.post("/api/projects", json={"name": "FN1", "start_date": "2026-10-12"}).json()["project"]["id"]
    p2 = c.post("/api/projects", json={"name": "FN2", "start_date": "2026-10-12"}).json()["project"]["id"]
    r1 = c.post("/api/projects/%d/resources" % p1, json={"name": "A", "user_id": uid, "funktion": " Projektleiter "}).json()["resources"][0]
    r2 = c.post("/api/projects/%d/resources" % p2, json={"name": "A", "user_id": uid, "funktion": "Netzwerktechniker"}).json()["resources"][0]
    assert r1["funktion"] == "Projektleiter" and r2["funktion"] == "Netzwerktechniker"                 # je Projekt eine andere Funktion
    d = c.put("/api/resources/%d" % r1["id"], json={"name": "A2", "max_units": 80}).json()               # ohne Feld: bleibt erhalten
    assert next(r for r in d["resources"] if r["id"] == r1["id"])["funktion"] == "Projektleiter"
    d = c.put("/api/resources/%d" % r1["id"], json={"name": "A2", "max_units": 80, "funktion": "Netzwerk-Lead"}).json()
    assert next(r for r in d["resources"] if r["id"] == r1["id"])["funktion"] == "Netzwerk-Lead"
    d = c.put("/api/resources/%d" % r1["id"], json={"name": "A2", "max_units": 80, "funktion": ""}).json()   # leeren
    assert next(r for r in d["resources"] if r["id"] == r1["id"])["funktion"] == ""
    c.put("/api/resources/%d" % r1["id"], json={"name": "A2", "max_units": 80, "funktion": "Projektleiter"})
    ppl = c.get("/api/overview/people").json()
    person = next(p for p in ppl["people"] if p["user_id"] == uid)
    assert {s["name"]: s["funktion"] for s in person["projects"]}["FN1"] == "Projektleiter"
    assert {s["name"]: s["funktion"] for s in person["projects"]}["FN2"] == "Netzwerktechniker"


def test_org_chart_reports_to(c):
    pid = c.post("/api/projects", json={"name": "ORG", "start_date": "2026-10-12"}).json()["project"]["id"]
    other = c.post("/api/projects", json={"name": "ORG2", "start_date": "2026-10-12"}).json()["project"]["id"]
    mk = lambda p, n, **kw: c.post("/api/projects/%d/resources" % p, json={"name": n, **kw}).json()
    a = mk(pid, "Lead")["resources"][0]["id"]
    b = next(r for r in mk(pid, "Tech", reports_to=a)["resources"] if r["name"] == "Tech")
    assert b["reports_to"] == a
    x = mk(other, "Fremd")["resources"][0]["id"]
    assert c.post("/api/projects/%d/resources" % pid, json={"name": "Q", "reports_to": x}).status_code == 422     # anderes Projekt
    assert c.put("/api/resources/%d" % a, json={"name": "Lead", "max_units": 100, "reports_to": a}).status_code == 422   # nicht an sich selbst
    assert c.put("/api/resources/%d" % a, json={"name": "Lead", "max_units": 100, "reports_to": b["id"]}).status_code == 422   # Zirkel
    d = c.put("/api/resources/%d" % b["id"], json={"name": "Tech", "max_units": 100}).json()                      # ohne Feld: bleibt
    assert next(r for r in d["resources"] if r["id"] == b["id"])["reports_to"] == a
    d = c.put("/api/resources/%d" % b["id"], json={"name": "Tech", "max_units": 100, "reports_to": None}).json()    # lösen
    assert next(r for r in d["resources"] if r["id"] == b["id"])["reports_to"] is None
    c.put("/api/resources/%d" % b["id"], json={"name": "Tech", "max_units": 100, "reports_to": a})
    d = c.delete("/api/resources/%d" % a).json()                                                                  # Chef weg -> Untergebene hängen an der Projektleitung
    assert next(r for r in d["resources"] if r["id"] == b["id"])["reports_to"] is None


def test_sessions_end_on_password_change_reset_and_force_logout(c):
    uid = _mk(c, "ss_user")
    other = _mk(c, "ss_other")
    # eigener Passwortwechsel: andere Sitzungen enden, die aktuelle bekommt ein neues Token
    a, b = _login("ss_user", PW + "ss_user"), _login("ss_user", PW + "ss_user")
    r = a.post("/api/auth/password", json={"old_password": PW + "ss_user", "new_password": "neues-passwort-1"})
    assert r.status_code == 200 and r.json()["token"]
    assert b.get("/api/auth/me").status_code == 401                                                       # alte Sitzung ungültig
    assert a.get("/api/auth/me").status_code == 401                                                       # altes Token der aktuellen auch ...
    a.headers["Authorization"] = "Bearer " + r.json()["token"]
    assert a.get("/api/auth/me").status_code == 200                                                       # ... das neue gilt
    # Admin setzt Passwort zurück: Sitzungen des Benutzers enden
    assert c.put("/api/users/%d/password" % uid, json={"new_password": "noch-ein-passwort-2"}).status_code == 200
    assert a.get("/api/auth/me").status_code == 401
    # Admin beendet Sitzungen
    u = _login("ss_user", "noch-ein-passwort-2")
    assert u.get("/api/auth/me").status_code == 200
    assert c.post("/api/users/%d/logout" % uid).status_code == 200
    assert u.get("/api/auth/me").status_code == 401
    assert _login("ss_user", "noch-ein-passwort-2").get("/api/auth/me").status_code == 200                # Neuanmeldung klappt
    assert _login("ss_other", PW + "ss_other").post("/api/users/%d/logout" % uid).status_code == 403      # nur Admin
    admin_id = next(x["id"] for x in c.get("/api/users").json() if x["username"] == "admin")
    assert c.post("/api/users/%d/logout" % admin_id).status_code == 400
    assert c.post("/api/users/99999/logout").status_code == 404
    assert other


def test_org_chart_move_endpoint(c):
    pid = c.post("/api/projects", json={"name": "MV", "start_date": "2026-10-12"}).json()["project"]["id"]
    mk = lambda n, **kw: max(c.post("/api/projects/%d/resources" % pid, json={"name": n, **kw}).json()["resources"], key=lambda r: r["id"])["id"]
    a, b = mk("A"), mk("B")
    d = c.put("/api/resources/%d/reports-to" % b, json={"reports_to": a}).json()
    assert next(r for r in d["resources"] if r["id"] == b)["reports_to"] == a
    assert c.put("/api/resources/%d/reports-to" % a, json={"reports_to": b}).status_code == 422             # Zirkel
    d = c.put("/api/resources/%d/reports-to" % b, json={"reports_to": None}).json()
    assert next(r for r in d["resources"] if r["id"] == b)["reports_to"] is None
    viewer = _mk(c, "mv_viewer", "viewer")
    assert _login("mv_viewer", PW + "mv_viewer").put("/api/resources/%d/reports-to" % b, json={"reports_to": a}).status_code in (403, 404)
    assert viewer
