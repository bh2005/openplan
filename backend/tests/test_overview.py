from test_api import _login, c, mk  # noqa: F401,E402  (setzt DATA_DIR/ADMIN_PASSWORD vor allen App-Importen)

import datetime as dt  # noqa: E402

import overview  # noqa: E402

PW = "passwort-"


def test_overview_people_and_scoping(c):
    overview._today = lambda: dt.date(2026, 10, 14)
    for n, role in (("ov_boss", "viewer"), ("ov_anna", "editor"), ("ov_ben", "editor"), ("ov_lead", "editor")):
        c.post("/api/users", json={"username": n, "password": PW + n, "role": role})
    uid = {u["username"]: u["id"] for u in c.get("/api/users").json()}
    c.put("/api/users/%d/see-all" % uid["ov_boss"], json={"see_all": True})
    lead = _login("ov_lead", PW + "ov_lead")
    p1 = lead.post("/api/projects", json={"name": "OV Alpha", "start_date": "2026-10-12"}).json()["project"]["id"]
    p2 = c.post("/api/projects", json={"name": "OV Beta", "start_date": "2026-10-12"}).json()["project"]["id"]
    r1 = lead.post("/api/projects/%d/resources" % p1, json={"name": "Anna", "user_id": uid["ov_anna"]}).json()["resources"][0]["id"]
    rb = c.post("/api/projects/%d/resources" % p2, json={"name": "Anna", "user_id": uid["ov_anna"]}).json()["resources"][0]["id"]
    extern = c.post("/api/projects/%d/resources" % p2, json={"name": "Externer Dienstleister"}).json()
    rx = [r for r in extern["resources"] if r["name"] == "Externer Dienstleister"][0]["id"]

    def task(cl, pid, name, rid, units=100, dur=5):
        t = [x for x in cl.post("/api/projects/%d/tasks" % pid, json={"name": name, "duration": dur}).json()["tasks"] if x["name"] == name][0]["id"]
        cl.put("/api/tasks/%d/assignments" % t, json=[{"resource_id": rid, "units": units}])
        return t
    task(lead, p1, "T1", r1)
    task(c, p2, "T2", rb)                                              # Anna 200 % an Tag 1 -> überlastet
    task(c, p2, "T3", rx, 50)
    lead.post("/api/me/absences", json={"start_date": "2026-10-20", "end_date": "2026-10-21", "kind": "vacation"})
    anna = _login("ov_anna", PW + "ov_anna")
    anna.post("/api/me/absences", json={"start_date": "2026-10-22", "end_date": "2026-10-23", "kind": "sick", "note": "x"})

    boss = _login("ov_boss", PW + "ov_boss")
    d = boss.get("/api/overview/people").json()
    names = {p["name"]: p for p in d["people"]}
    assert {"OV Alpha", "OV Beta"} <= {p["name"] for p in d["projects"]}
    a = names["ov_anna"]
    assert a["load_now"] == 200 and a["over"] is True and len(a["projects"]) == 2
    assert a["next_absence"]["kind"] == "other"                                       # Krank für andere maskiert
    assert names["ov_lead"]["projects"][0]["roles"] == ["lead"] and names["ov_lead"]["next_absence"]["kind"] == "vacation"
    ext = names["Externer Dienstleister"]
    assert ext["user_id"] is None and ext["load_now"] == 50 and ext["over"] is False
    alpha = [p for p in d["projects"] if p["name"] == "OV Alpha"][0]
    assert alpha["tasks_total"] == 1 and {x["name"] for x in alpha["people"]} == {"ov_lead", "ov_anna"}
    # Anna selbst sieht ihre Krankheit ungefiltert, ein normaler Editor ohne Zugriff sieht Alpha/Beta nicht
    mine = {p["name"]: p for p in anna.get("/api/overview/people").json()["people"]}
    assert mine["ov_anna"]["next_absence"]["kind"] == "sick"
    ben = _login("ov_ben", PW + "ov_ben")
    assert ben.get("/api/overview/people").json()["projects"] == [] or all(p["name"] not in ("OV Alpha", "OV Beta") for p in ben.get("/api/overview/people").json()["projects"])
