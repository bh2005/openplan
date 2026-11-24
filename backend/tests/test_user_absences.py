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


def test_all_absences_for_admins_and_released_tokens(c):
    from test_apitokens import _client, _new
    for n in ("ua_carl", "ua_dora"):
        c.post("/api/users", json={"username": n, "password": PW + n, "role": "editor"})
    carl, dora = _login("ua_carl", PW + "ua_carl"), _login("ua_dora", PW + "ua_dora")
    assert carl.put("/api/auth/profile", json={"email": "ua_carl@example.test"}).status_code == 200
    carl.post("/api/me/absences", json={"start_date": "2030-03-02", "end_date": "2030-03-06", "kind": "sick", "note": "geheim"})
    carl.post("/api/me/absences", json={"start_date": "2031-07-01", "end_date": "2031-07-02"})               # außerhalb des Zeitraums
    dora.post("/api/me/absences", json={"start_date": "2030-02-25", "end_date": "2030-03-01", "kind": "training"})
    q = "/api/absences?start=2030-03-01&end=2030-03-31"
    r = c.get(q)
    assert r.status_code == 200, r.text
    mine = [a for a in r.json()["absences"] if a["username"] in ("ua_carl", "ua_dora")]
    assert [(a["username"], a["start_date"], a["kind"]) for a in mine] == [("ua_carl", "2030-03-02", "other"), ("ua_dora", "2030-02-25", "training")]
    assert mine[0]["email"] == "ua_carl@example.test" and "note" not in mine[0] and "geheim" not in r.text   # krank maskiert, keine Notiz
    assert carl.get(q).status_code == 403                                               # normale Benutzer nicht
    tok = _new(c, name="pw-abw", username="svc-pw-abw", scope="read")
    svc = _client(tok["token"])
    assert not tok["absences"] and svc.get(q).status_code == 403                        # Token ohne Freigabe nicht
    r = c.patch("/api/admin/tokens/%d" % tok["id"], json={"absences": True})
    assert r.status_code == 200 and r.json()["absences"] is True
    assert len([a for a in svc.get(q).json()["absences"] if a["username"].startswith("ua_")]) == 2
    assert svc.patch("/api/admin/tokens/%d" % tok["id"], json={"absences": False}).status_code == 403
    assert c.get("/api/absences?start=2030-03-31&end=2030-03-01").status_code == 422
    assert _new(c, name="pw-abw2", username="svc-pw-abw2", absences=True)["absences"] is True
    assert "pw-abw: Abwesenheiten freigegeben" in str(c.get("/api/admin/audit?action=token.update").json())
