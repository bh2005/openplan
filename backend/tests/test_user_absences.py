from test_api import _login, c, mk  # noqa: F401,E402  (setzt DATA_DIR/ADMIN_PASSWORD vor allen App-Importen)

PW = "passwort-"


def test_user_absence_shows_in_all_projects_masked(c):
    for n in ("ua_anna", "ua_ben"):
        c.post("/api/users", json={"username": n, "password": PW + n, "role": "editor"})
    uid = {u["username"]: u["id"] for u in c.get("/api/users").json()}
    anna, ben = _login("ua_anna", PW + "ua_anna"), _login("ua_ben", PW + "ua_ben")
    p1, p2 = mk(c, "UA1")["project"]["id"], mk(c, "UA2")["project"]["id"]
    res = {}
    for p in (p1, p2):
        d = c.post("/api/projects/%d/resources" % p, json={"name": "Anna", "user_id": uid["ua_anna"]}).json()
        res[p] = d["resources"][0]["id"]
    rev = c.get("/api/projects/%d" % p1).json()["project"]["revision"]
    r = anna.post("/api/me/absences", json={"start_date": "2026-11-09", "end_date": "2026-11-13", "kind": "sick", "note": "Arzt"})
    assert r.status_code == 201 and len(r.json()) == 1
    aid = r.json()[0]["id"]
    for p in (p1, p2):
        ab = c.get("/api/projects/%d" % p).json()["absences"]
        assert len(ab) == 1 and ab[0]["source"] == "user" and ab[0]["resource_id"] == res[p] and ab[0]["id"] < 0
        assert ab[0]["kind"] == "other" and ab[0]["note"] == ""             # Krank wird für andere maskiert
    assert c.get("/api/projects/%d" % p1).json()["project"]["revision"] > rev    # Live-Update
    assert c.get("/api/me/absences").json() == []                               # fremde Einträge nicht in der eigenen Liste
    c.post("/api/projects/%d/absences" % p1, json={"resource_id": res[p1], "start_date": "2026-12-01", "end_date": "2026-12-02"})
    sources = sorted(a["source"] for a in c.get("/api/projects/%d" % p1).json()["absences"])
    assert sources == ["project", "user"]
    assert ben.put("/api/me/absences/%d" % aid, json={"start_date": "2026-11-09", "end_date": "2026-11-10"}).status_code == 404
    assert ben.delete("/api/me/absences/%d" % aid).status_code == 404
    assert anna.post("/api/me/absences", json={"start_date": "2026-11-14", "end_date": "2026-11-10"}).status_code == 422
    r = anna.put("/api/me/absences/%d" % aid, json={"start_date": "2026-11-09", "end_date": "2026-11-10", "kind": "vacation"})
    assert r.json()[0]["end_date"] == "2026-11-10"
    own = anna.get("/api/projects/%d" % p1)                                     # Anna ist nur über die Ressource nicht automatisch Mitglied
    assert own.status_code in (200, 404)
    assert anna.delete("/api/me/absences/%d" % aid).json() == []
    assert [a["source"] for a in c.get("/api/projects/%d" % p1).json()["absences"]] == ["project"]
