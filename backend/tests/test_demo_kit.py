from test_api import c  # noqa: F401,E402  (setzt DATA_DIR/ADMIN_PASSWORD vor allen App-Importen)


def _check(d, expect_tasks):
    t = d["tasks"]
    assert len(t) >= expect_tasks and d["project"]["finish"]
    st = {x["status"] for x in t}
    assert {"done", "in_progress", "blocked"} <= st                            # Fortschritt + Blockade
    assert any(x["baseline_start"] for x in t) and d["resources"]            # Basisplan
    assert sum(1 for x in t if x["milestone"]) >= 3                            # Gates/Meilensteine
    return d


def test_migration_and_release_demo_projects_de_en(c):
    c.put("/api/auth/profile", json={"lang": "de"})
    m = _check(c.post("/api/projects/demo?kind=migration").json(), 45)
    assert m["project"]["name"].startswith("Beispiel: Server-Migration") and any("Welle 1" in x["name"] for x in m["tasks"])
    r = _check(c.post("/api/projects/demo?kind=release").json(), 40)
    assert r["project"]["name"].startswith("Beispiel: Transition Release-Wechsel")
    c.put("/api/auth/profile", json={"lang": "en"})
    me = _check(c.post("/api/projects/demo?kind=migration").json(), 45)
    assert me["project"]["name"].startswith("Sample: Server migration") and any("Wave 1" in x["name"] for x in me["tasks"])
    re_ = _check(c.post("/api/projects/demo?kind=release").json(), 40)
    assert any("Go-live" in x["name"] for x in re_["tasks"])
    # Budget vorhanden, Ist-Kosten gebucht
    fin = c.get("/api/projects/%d/budget" % me["project"]["id"]).json()
    assert fin["summary"]["budget"] and fin["summary"]["ac"] > 0
    assert c.post("/api/projects/demo?kind=gibtsnicht").status_code == 422
    c.put("/api/auth/profile", json={"lang": "de"})


def test_english_default_templates_are_copies(c):
    names = {t["name"] for t in c.get("/api/templates").json()}
    assert {"Switch", "Access Point", "Firewall", "Switch (English)", "Access Point (English)", "Firewall (English)"} <= names


def test_project_wizard_templates_members_and_report(c):
    from test_api import _login
    ids = {}
    for n in ("wz_ed", "wz_mem", "wz_view"):
        ids[n] = c.post("/api/users", json={"username": n, "password": "passwort-" + n, "role": "viewer" if n == "wz_view" else "editor"}).json()["id"]
    ed = _login("wz_ed", "passwort-wz_ed")
    body = {"kind": "migration", "name": "Wizard Migration", "description": "Test", "start_date": "2026-11-02", "work_days": [0, 1, 2, 3, 4],
            "members": [{"user_id": ids["wz_mem"], "role": "editor"}], "report_enabled": True, "report_weekday": 1, "report_hour": 8, "report_to": "members"}
    d = ed.post("/api/projects/wizard", json=body)
    assert d.status_code == 201, d.text
    d = d.json()
    p = d["project"]
    assert p["name"] == "Wizard Migration" and p["start_date"] == "2026-11-02" and p["report_enabled"] == 1 and p["report_to"] == "members" and p["report_hour"] == 8
    assert p["owner"]["username"] == "wz_ed" and [m["username"] for m in d["members"]] == ["wz_mem"]
    # Nur Struktur: Phasen, Vorgänge, Meilensteine – keine Ressourcen/Zuordnungen/Kosten/Basisplan/Fortschritt
    assert len(d["tasks"]) >= 45 and not d["resources"] and not d["assignments"]
    assert all(t["status"] == "open" and t["percent"] == 0 and not t["baseline_start"] for t in d["tasks"])
    assert sum(1 for t in d["tasks"] if t["milestone"]) >= 3 and min(t["start"] for t in d["tasks"]) >= "2026-11-02"
    assert any(t["name"].startswith("Migrationsstrategie") for t in d["tasks"])
    for kind, marker in (("network", "Standort 1"), ("release", "Cutover")):
        r = ed.post("/api/projects/wizard", json={**body, "kind": kind, "members": [], "name": "W " + kind}).json()
        assert any(marker in t["name"] for t in r["tasks"]), kind
    # Patchfelder/Verkabelung: Vertrag mit Portwerk – ein Sammelvorgang, dessen Name „Portwerk“ enthält, darunter hängt Portwerk seine Aufträge ein
    pp = ed.post("/api/projects/wizard", json={**body, "kind": "patchpanel", "members": [], "name": "W patchpanel"})
    assert pp.status_code == 201, pp.text
    sec = [t for t in pp.json()["tasks"] if t["summary"] and "portwerk" in t["name"].lower()]
    assert len(sec) == 1 and sec[0]["name"] == "Patchaufträge (aus Portwerk)"
    assert any(t["parent_id"] == sec[0]["id"] and t["milestone"] for t in pp.json()["tasks"])          # Meilenstein „Alle Patchaufträge bestätigt“
    e = ed.post("/api/projects/wizard", json={"kind": "empty", "name": "Leer", "start_date": "2026-11-02"}).json()
    assert e["tasks"] == [] and e["project"]["report_enabled"] == 0
    # Prüfungen: Mitglied = Verantwortlicher, doppelt, unbekannter Benutzer, fremder Verantwortlicher nur als Admin
    assert ed.post("/api/projects/wizard", json={**body, "members": [{"user_id": ids["wz_ed"], "role": "editor"}]}).status_code == 422
    assert ed.post("/api/projects/wizard", json={**body, "members": [{"user_id": ids["wz_mem"]}, {"user_id": ids["wz_mem"]}]}).status_code == 422
    assert ed.post("/api/projects/wizard", json={**body, "members": [{"user_id": 999999}]}).status_code == 422
    assert ed.post("/api/projects/wizard", json={**body, "owner_id": ids["wz_mem"]}).status_code == 403
    a = c.post("/api/projects/wizard", json={**body, "owner_id": ids["wz_mem"], "members": [], "kind": "empty"})
    assert a.status_code == 201 and a.json()["project"]["owner"]["username"] == "wz_mem"
    assert c.post("/api/projects/wizard", json={**body, "owner_id": ids["wz_view"], "members": []}).status_code == 422          # viewer kann nicht Verantwortlicher sein
    assert _login("wz_view", "passwort-wz_view").post("/api/projects/wizard", json=body).status_code == 403                    # viewer darf keine Projekte anlegen
