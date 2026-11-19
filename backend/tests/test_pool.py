from test_api import _login, c, mk, add  # noqa: F401


_IDS = {}


def _team(c):
    if not _IDS:
        for n in ("pool_pia", "pool_paul", "pool_vera"):
            r = c.post("/api/users", json={"username": n, "password": "passwort-" + n, "role": "editor"}); assert r.status_code == 201, r.text; _IDS[n] = r.json()["id"]
    ids = _IDS
    pia, paul, vera = (_login(n, "passwort-" + n) for n in ("pool_pia", "pool_paul", "pool_vera"))
    pid = pia.post("/api/projects", json={"name": "Pool", "start_date": "2026-10-12"}).json()["project"]["id"]
    pia.put("/api/projects/%d/members" % pid, json=[{"user_id": ids["pool_paul"], "role": "editor"}, {"user_id": ids["pool_vera"], "role": "viewer"}])
    return ids, pia, paul, vera, pid


def test_claim_and_release(c):
    ids, pia, paul, vera, pid = _team(c)
    d = pia.post("/api/projects/%d/tasks" % pid, json={"name": "Paket A", "duration": 3, "pool": True}).json()
    tid = max(t["id"] for t in d["tasks"])
    assert next(t for t in d["tasks"] if t["id"] == tid)["pool"] is True

    # Leser dürfen nicht übernehmen
    assert vera.post("/api/tasks/%d/claim" % tid).status_code == 403
    # Mitglied übernimmt: Ressource wird angelegt/verknüpft, Status wechselt auf "in Arbeit"
    d = paul.post("/api/tasks/%d/claim" % tid).json()
    res = next(r for r in d["resources"] if r["user_id"] == ids["pool_paul"])
    assert [a["resource_id"] for a in d["assignments"] if a["task_id"] == tid] == [res["id"]]
    assert next(t for t in d["tasks"] if t["id"] == tid)["status"] == "in_progress"
    # Nur einer pro Paket
    assert pia.post("/api/tasks/%d/claim" % tid).status_code == 409
    # Fremder Bearbeiter darf nicht zurückgeben, Verantwortlicher schon
    assert vera.post("/api/tasks/%d/release" % tid).status_code == 403
    d = pia.post("/api/tasks/%d/release" % tid).json()
    t = next(t for t in d["tasks"] if t["id"] == tid)
    assert not [a for a in d["assignments"] if a["task_id"] == tid] and t["status"] == "open" and t["pool"]
    # Erneut übernehmen: vorhandene Ressource wird wiederverwendet; Rückgabe durch Übernehmer
    d = paul.post("/api/tasks/%d/claim" % tid).json()
    assert len([r for r in d["resources"] if r["user_id"] == ids["pool_paul"]]) == 1
    assert paul.post("/api/tasks/%d/release" % tid).status_code == 200
    # Journal
    acts = [j["action"] for j in pia.get("/api/projects/%d/journal" % pid).json()]
    assert "Arbeitspaket übernommen" in acts and "Arbeitspaket zurückgegeben" in acts


def test_claim_rules(c):
    ids, pia, paul, vera, pid = _team(c)
    _, normal = add(pia, pid, "Normal")
    assert paul.post("/api/tasks/%d/claim" % normal).status_code == 409            # kein Pool-Paket
    d = pia.patch("/api/tasks/%d" % normal, json={"pool": True}).json()
    assert next(t for t in d["tasks"] if t["id"] == normal)["pool"] is True
    # bereits direkt zugeordnet -> nicht übernehmbar
    rid = pia.post("/api/projects/%d/resources" % pid, json={"name": "Extern"}).json()["resources"][0]["id"]
    pia.put("/api/tasks/%d/assignments" % normal, json=[{"resource_id": rid, "units": 100}])
    assert paul.post("/api/tasks/%d/claim" % normal).status_code == 409
    # Sammelvorgang kann nicht in den Pool
    _, kid = add(pia, pid, "Kind", parent_id=normal)
    assert pia.patch("/api/tasks/%d" % normal, json={"pool": True}).json()  # Flag bleibt, wirkt aber nicht
    d = pia.get("/api/projects/%d" % pid).json()
    assert next(t for t in d["tasks"] if t["id"] == normal)["pool"] is False


def test_resource_user_link(c):
    ids, pia, paul, vera, pid = _team(c)
    d = pia.post("/api/projects/%d/resources" % pid, json={"name": "Paul P.", "user_id": ids["pool_paul"]}).json()
    r = d["resources"][0]
    assert r["user_id"] == ids["pool_paul"]
    # Jeder vorhandene Benutzer ist verknüpfbar (die Zuordnung gibt ihm Mitarbeiter-Zugriff); unbekannte nicht
    other = c.post("/api/users", json={"username": "pool_otto", "password": "passwort-pool_otto", "role": "editor"}).json()["id"]  # nur in diesem Test
    assert pia.put("/api/resources/%d" % r["id"], json={"name": "Paul P.", "user_id": 99999}).status_code == 422
    assert pia.put("/api/resources/%d" % r["id"], json={"name": "Paul P.", "user_id": other}).status_code == 200
    assert pia.put("/api/resources/%d" % r["id"], json={"name": "Paul P.", "user_id": ids["pool_paul"]}).status_code == 200
    # Update ohne user_id lässt die Verknüpfung unberührt
    d = pia.put("/api/resources/%d" % r["id"], json={"name": "Paul Pauli"}).json()
    assert d["resources"][0]["user_id"] == ids["pool_paul"]
    # Claim nutzt die verknüpfte Ressource
    tid = pia.post("/api/projects/%d/tasks" % pid, json={"name": "P", "pool": True}).json()["tasks"][0]["id"]
    d = paul.post("/api/tasks/%d/claim" % tid).json()
    assert len(d["resources"]) == 1 and d["assignments"][0]["resource_id"] == r["id"]
    # Verknüpfung entfernen
    d = pia.put("/api/resources/%d" % r["id"], json={"name": "Paul Pauli", "user_id": None}).json()
    assert d["resources"][0]["user_id"] is None


def test_undo_redo(c):
    ids, pia, paul, vera, pid = _team(c)
    _, a = add(pia, pid, "Eins")
    _, b = add(pia, pid, "Zwei")
    d = pia.get("/api/projects/%d" % pid).json()
    assert d["history"]["undo"]["label"].startswith("Vorgang angelegt") and d["history"]["redo"] is None
    # Änderung + Zuordnung, dann zurück
    rid = pia.post("/api/projects/%d/resources" % pid, json={"name": "R"}).json()["resources"][0]["id"]
    pia.put("/api/tasks/%d/assignments" % a, json=[{"resource_id": rid, "units": 50}])
    pia.patch("/api/tasks/%d" % a, json={"name": "Eins neu", "duration": 4})
    d = pia.post("/api/projects/%d/undo" % pid).json()
    assert next(t for t in d["tasks"] if t["id"] == a)["name"] == "Eins" and d["history"]["redo"]
    d = pia.post("/api/projects/%d/undo" % pid).json()
    assert d["assignments"] == []
    d = pia.post("/api/projects/%d/redo" % pid).json()
    assert d["assignments"][0]["units"] == 50
    # Löschen eines Vorgangs rückgängig machen (inkl. Abhängigkeit)
    pia.put("/api/tasks/%d/predecessors" % b, json=[{"pred_id": a}])
    d = pia.delete("/api/tasks/%d" % a).json()
    assert a not in [t["id"] for t in d["tasks"]] and d["deps"] == []
    d = pia.post("/api/projects/%d/undo" % pid).json()
    assert a in [t["id"] for t in d["tasks"]] and len(d["deps"]) == 1
    # Neue Änderung leert den Redo-Stapel; Fehlschläge werden nicht gespeichert
    assert pia.patch("/api/tasks/%d" % b, json={"constraint_type": "SNET"}).status_code == 422
    d = pia.patch("/api/tasks/%d" % b, json={"notes": "x"}).json()
    assert d["history"]["redo"] is None and d["history"]["undo"]["label"].startswith("Vorgang geändert")


def test_undo_permissions(c):
    ids, pia, paul, vera, pid = _team(c)
    _, a = add(pia, pid, "Von Pia")
    assert paul.post("/api/projects/%d/undo" % pid).status_code == 409        # Änderung von Pia
    assert vera.post("/api/projects/%d/undo" % pid).status_code == 403        # Leser
    assert pia.post("/api/projects/%d/undo" % pid).status_code == 200
    d = paul.post("/api/projects/%d/tasks" % pid, json={"name": "Von Paul"}).json()
    assert pia.post("/api/projects/%d/undo" % pid).status_code == 200         # Verantwortlicher darf fremde zurücknehmen
    assert pia.post("/api/projects/%d/undo" % pid).status_code in (200, 409)


def test_events_stream(c, monkeypatch):
    import api
    monkeypatch.setattr(api, "EVENT_MAX_SECONDS", 2)
    ids, pia, paul, vera, pid = _team(c)
    with pia.stream("GET", "/api/projects/%d/events" % pid) as r:
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
        body = "".join(r.iter_text())
    rev = pia.get("/api/projects/%d/revision" % pid).json()["revision"]
    assert "event: revision" in body and '"revision": %d' % rev in body
    # Fremde bekommen 404, Anonyme 401
    stranger = _login("pool_pia", "passwort-pool_pia")
    other = c.post("/api/projects", json={"name": "Fremd", "start_date": "2026-10-12"}).json()["project"]["id"]
    assert stranger.get("/api/projects/%d/events" % other).status_code == 404
