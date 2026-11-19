from test_api import _login, c, mk  # noqa: F401,E402  (setzt DATA_DIR/ADMIN_PASSWORD vor allen App-Importen)

PW = "passwort-"


def mkres(c, pid, name="Anna", **kw):
    d = c.post("/api/projects/%d/resources" % pid, json={"name": name, **kw}).json()
    return [r for r in d["resources"] if r["name"] == name][0]["id"]


def test_absence_crud_and_validation(c):
    pid = mk(c, "Abw")["project"]["id"]
    rid = mkres(c, pid)
    r = c.post("/api/projects/%d/absences" % pid, json={"resource_id": rid, "start_date": "2026-12-21", "end_date": "2026-12-31", "kind": "vacation", "note": "Urlaub"})
    assert r.status_code == 201
    ab = r.json()["absences"]
    assert len(ab) == 1 and ab[0]["resource_id"] == rid and ab[0]["kind"] == "vacation"
    aid = ab[0]["id"]
    assert c.post("/api/projects/%d/absences" % pid, json={"resource_id": rid, "start_date": "2026-12-31", "end_date": "2026-12-21"}).status_code == 422
    assert c.post("/api/projects/%d/absences" % pid, json={"start_date": "2026-12-01", "end_date": "2026-12-02"}).status_code == 422
    assert c.post("/api/projects/%d/absences" % pid, json={"resource_id": 999999, "start_date": "2026-12-01", "end_date": "2026-12-02"}).status_code == 422
    assert c.post("/api/projects/%d/absences" % pid, json={"resource_id": rid, "start_date": "2026-12-01", "end_date": "2028-12-02"}).status_code == 422
    r = c.put("/api/absences/%d" % aid, json={"start_date": "2026-12-22", "end_date": "2026-12-23", "kind": "training"})
    assert r.json()["absences"][0]["kind"] == "training" and r.json()["absences"][0]["start_date"] == "2026-12-22"
    r = c.delete("/api/absences/%d" % aid)
    assert r.status_code == 200 and r.json()["absences"] == []


def test_absence_undo_and_cascade(c):
    pid = mk(c, "AbwUndo")["project"]["id"]
    rid = mkres(c, pid)
    c.post("/api/projects/%d/absences" % pid, json={"resource_id": rid, "start_date": "2026-11-02", "end_date": "2026-11-03"})
    d = c.post("/api/projects/%d/undo" % pid).json()
    assert d["absences"] == []
    d = c.post("/api/projects/%d/redo" % pid).json()
    assert len(d["absences"]) == 1
    d = c.delete("/api/resources/%d" % rid).json()          # Ressource löschen entfernt ihre Abwesenheiten
    assert d["absences"] == []


def test_absence_member_only_own(c):
    for n in ("ab_anna", "ab_ben"):
        c.post("/api/users", json={"username": n, "password": PW + n, "role": "editor"})
    anna, ben = _login("ab_anna", PW + "ab_anna"), _login("ab_ben", PW + "ab_ben")
    uid = {u["username"]: u["id"] for u in c.get("/api/users").json()}
    pid = mk(c, "AbwOwn")["project"]["id"]
    c.put("/api/projects/%d/members" % pid, json=[{"user_id": uid["ab_anna"], "role": "viewer"}, {"user_id": uid["ab_ben"], "role": "viewer"}])
    ra = mkres(c, pid, "Anna", user_id=uid["ab_anna"])
    rb = mkres(c, pid, "Ben", user_id=uid["ab_ben"])
    t = c.post("/api/projects/%d/tasks" % pid, json={"name": "T"}).json()
    tid = [x for x in t["tasks"] if x["name"] == "T"][0]["id"]
    c.put("/api/tasks/%d/assignments" % tid, json=[{"resource_id": ra, "units": 100}, {"resource_id": rb, "units": 100}])
    body = {"start_date": "2026-11-09", "end_date": "2026-11-13", "kind": "vacation"}
    # Leser mit Zuordnung = Mitarbeiter: nur eigene Ressource
    assert anna.post("/api/projects/%d/absences" % pid, json={**body, "resource_id": ra}).status_code == 201
    assert anna.post("/api/projects/%d/absences" % pid, json={**body, "resource_id": rb}).status_code == 403
    own = [a for a in anna.get("/api/projects/%d" % pid).json()["absences"] if a["resource_id"] == ra][0]["id"]
    bens = c.post("/api/projects/%d/absences" % pid, json={**body, "resource_id": rb}).json()["absences"]
    bid = [a for a in bens if a["resource_id"] == rb][0]["id"]
    assert anna.put("/api/absences/%d" % bid, json=body).status_code == 403
    assert anna.delete("/api/absences/%d" % bid).status_code == 403
    assert anna.delete("/api/absences/%d" % own).status_code == 200
