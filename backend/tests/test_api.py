import os
import sys
import tempfile

import pytest

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["ADMIN_PASSWORD"] = "testpass123"
os.environ["WEBHOOK_WORKER"] = "0"       # Zustellung in Tests nur ausdrücklich per webhooks.run_due()
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        tok = client.post("/api/auth/login", json={"username": "admin", "password": "testpass123"}).json()["token"]
        client.headers["Authorization"] = "Bearer " + tok
        yield client


def mk(c, name="P"):
    return c.post("/api/projects", json={"name": name, "start_date": "2026-10-12"}).json()


def add(c, pid, name, **kw):
    d = c.post("/api/projects/%d/tasks" % pid, json={"name": name, **kw}).json()
    return d, max(t["id"] for t in d["tasks"])


def test_auth_required():
    with TestClient(app) as anon:
        assert anon.get("/api/projects").status_code == 401
        assert anon.post("/api/auth/login", json={"username": "admin", "password": "x"}).status_code == 401


def test_schedule_via_api(c):
    pid = mk(c)["project"]["id"]
    _, a = add(c, pid, "A", duration=3)
    d, b = add(c, pid, "B", duration=2)
    d = c.put("/api/tasks/%d/predecessors" % b, json=[{"pred_id": a, "type": "FS", "lag": 0}]).json()
    tb = next(t for t in d["tasks"] if t["id"] == b)
    assert tb["start"] == "2026-10-15" and tb["finish"] == "2026-10-16" and tb["critical"]
    assert d["project"]["finish"] == "2026-10-16"


def test_cycle_rejected_and_rolled_back(c):
    pid = mk(c)["project"]["id"]
    _, a = add(c, pid, "A")
    _, b = add(c, pid, "B")
    assert c.put("/api/tasks/%d/predecessors" % b, json=[{"pred_id": a}]).status_code == 200
    r = c.put("/api/tasks/%d/predecessors" % a, json=[{"pred_id": b}])
    assert r.status_code == 422
    assert len(c.get("/api/projects/%d" % pid).json()["deps"]) == 1


def test_hierarchy_move_and_wbs(c):
    pid = mk(c)["project"]["id"]
    _, a = add(c, pid, "Phase")
    _, b = add(c, pid, "Task")
    d = c.post("/api/tasks/%d/move" % b, json={"parent_id": a, "index": 0}).json()
    tb = next(t for t in d["tasks"] if t["id"] == b)
    ta = next(t for t in d["tasks"] if t["id"] == a)
    assert tb["wbs"] == "1.1" and ta["summary"]
    assert c.post("/api/tasks/%d/move" % a, json={"parent_id": b, "index": 0}).status_code == 422


def test_baseline_and_resources(c):
    pid = mk(c)["project"]["id"]
    _, a = add(c, pid, "A", duration=2)
    d = c.post("/api/projects/%d/resources" % pid, json={"name": "Anna"}).json()
    rid = d["resources"][0]["id"]
    d = c.put("/api/tasks/%d/assignments" % a, json=[{"resource_id": rid, "units": 50}]).json()
    assert d["tasks"][0]["resource_ids"] == [rid]
    d = c.post("/api/projects/%d/baseline" % pid).json()
    assert d["tasks"][0]["baseline_start"] == "2026-10-12"


def test_export_import_roundtrip(c):
    pid = mk(c, "RT")["project"]["id"]
    _, a = add(c, pid, "A", duration=3)
    _, b = add(c, pid, "B", duration=2)
    c.put("/api/tasks/%d/predecessors" % b, json=[{"pred_id": a, "type": "SS", "lag": 1}])
    for fmt, fname in (("json", "x.json"), ("xml", "x.xml")):
        raw = c.get("/api/projects/%d/export?fmt=%s" % (pid, fmt)).content
        r = c.post("/api/projects/import", files={"file": (fname, raw)})
        assert r.status_code == 201, r.text
        d = r.json()
        assert [t["name"] for t in d["tasks"]] == ["A", "B"]
        assert d["deps"][0]["type"] == "SS" and d["deps"][0]["lag"] == 1
        assert [t["duration"] for t in d["tasks"]] == [3, 2]
    assert c.get("/api/projects/%d/export?fmt=csv" % pid).content.startswith(b"\xef\xbb\xbf")


def test_viewer_cannot_write(c):
    c.post("/api/users", json={"username": "vera", "password": "viewerpass1", "role": "viewer"})
    with TestClient(app) as v:
        tok = v.post("/api/auth/login", json={"username": "vera", "password": "viewerpass1"}).json()["token"]
        v.headers["Authorization"] = "Bearer " + tok
        assert v.get("/api/projects").status_code == 200
        assert v.post("/api/projects", json={"name": "x", "start_date": "2026-10-12"}).status_code == 403


def _login(username, password):
    cl = TestClient(app)
    tok = cl.post("/api/auth/login", json={"username": username, "password": password}).json()["token"]
    cl.headers["Authorization"] = "Bearer " + tok
    return cl


def test_project_owner_and_membership(c):
    uid = {}
    for n, role in (("olga", "editor"), ("max", "editor"), ("vic", "editor")):
        r = c.post("/api/users", json={"username": n, "password": "passwort-" + n, "role": role})
        uid[n] = r.json()["id"]
    olga, mx, vic = (_login(n, "passwort-" + n) for n in ("olga", "max", "vic"))

    d = olga.post("/api/projects", json={"name": "Olgas Projekt", "start_date": "2026-10-12"}).json()
    pid = d["project"]["id"]
    assert d["project"]["owner"]["username"] == "olga" and d["access"] == "owner"

    # Fremde sehen/ändern nichts (404 statt 403: Existenz wird nicht verraten)
    assert mx.get("/api/projects/%d" % pid).status_code == 404
    assert pid not in [p["id"] for p in mx.get("/api/projects").json()]
    assert mx.post("/api/projects/%d/tasks" % pid, json={"name": "x"}).status_code == 404

    # Mitglieder: editor darf Vorgänge ändern, viewer nur lesen, beide nicht verwalten
    d = olga.put("/api/projects/%d/members" % pid, json=[
        {"user_id": uid["max"], "role": "editor"}, {"user_id": uid["vic"], "role": "viewer"}]).json()
    assert [m["username"] for m in d["members"]] == ["max", "vic"]
    assert mx.post("/api/projects/%d/tasks" % pid, json={"name": "T"}).status_code == 201
    assert vic.get("/api/projects/%d" % pid).json()["access"] == "view"
    assert vic.post("/api/projects/%d/tasks" % pid, json={"name": "T"}).status_code == 403
    assert mx.put("/api/projects/%d/members" % pid, json=[]).status_code == 403
    assert mx.patch("/api/projects/%d" % pid, json={"name": "hack"}).status_code == 403
    assert mx.delete("/api/projects/%d" % pid).status_code == 403
    tid = mx.get("/api/projects/%d" % pid).json()["tasks"][0]["id"]
    assert vic.patch("/api/tasks/%d" % tid, json={"name": "y"}).status_code == 403

    # Admin sieht alles; Verantwortlicher kann nicht gelöscht werden; Übertragung funktioniert
    assert c.get("/api/projects/%d" % pid).json()["access"] == "owner"
    assert c.delete("/api/users/%d" % uid["olga"]).status_code == 409
    assert olga.patch("/api/projects/%d" % pid, json={"owner_id": uid["max"]}).json() == {"transferred": True}
    assert olga.get("/api/projects/%d" % pid).status_code == 404
    assert mx.get("/api/projects/%d" % pid).json()["access"] == "owner"
    assert c.delete("/api/users/%d" % uid["olga"]).status_code == 200


def test_owner_rules(c):
    uid = c.post("/api/users", json={"username": "ben", "password": "passwort-ben", "role": "editor"}).json()["id"]
    ben = _login("ben", "passwort-ben")
    # Nicht-Admin darf keinen anderen als Verantwortlichen setzen
    r = ben.post("/api/projects", json={"name": "B", "start_date": "2026-10-12", "owner_id": 1})
    assert r.status_code == 403
    # Admin legt Projekt für ben an
    d = c.post("/api/projects", json={"name": "FürBen", "start_date": "2026-10-12", "owner_id": uid}).json()
    assert d["project"]["owner"]["username"] == "ben"
    assert [p["name"] for p in ben.get("/api/projects").json()].count("FürBen") == 1


def test_shift_phase(c):
    pid = mk(c)["project"]["id"]
    _, ph = add(c, pid, "Phase")
    _, a = add(c, pid, "A", duration=2)
    _, b = add(c, pid, "B", duration=2)
    for i, x in enumerate((a, b)):
        c.post("/api/tasks/%d/move" % x, json={"parent_id": ph, "index": i})
    c.put("/api/tasks/%d/predecessors" % b, json=[{"pred_id": a}])
    d = c.post("/api/tasks/%d/shift" % ph, json={"days": 7}).json()
    t = {x["id"]: x for x in d["tasks"]}
    assert t[a]["start"] == "2026-10-19" and t[b]["start"] == "2026-10-21"   # B folgt A (nur A wurde festgesetzt)
    assert t[a]["constraint_type"] == "SNET" and t[b]["constraint_type"] == "ASAP"
    assert t[ph]["start"] == "2026-10-19"
    d = c.post("/api/tasks/%d/shift" % ph, json={"days": -7}).json()
    assert {x["id"]: x for x in d["tasks"]}[ph]["start"] == "2026-10-12"


def test_status_coupling_and_summary(c):
    pid = mk(c)["project"]["id"]
    _, ph = add(c, pid, "Phase")
    _, a = add(c, pid, "A", duration=2)
    _, b = add(c, pid, "B", duration=2)
    for i, x in enumerate((a, b)):
        c.post("/api/tasks/%d/move" % x, json={"parent_id": ph, "index": i})
    t = lambda d, i: next(x for x in d["tasks"] if x["id"] == i)  # noqa: E731
    d = c.get("/api/projects/%d" % pid).json()
    assert t(d, a)["status"] == "open" and t(d, ph)["status"] == "open"
    # Fortschritt -> Status
    d = c.patch("/api/tasks/%d" % a, json={"percent": 40}).json()
    assert t(d, a)["status"] == "in_progress" and t(d, ph)["status"] == "in_progress"
    d = c.patch("/api/tasks/%d" % a, json={"percent": 100}).json()
    assert t(d, a)["status"] == "done" and t(d, ph)["status"] == "in_progress"
    # Status -> Fortschritt; Blockiert mit Notiz; Sammelvorgang übernimmt "blockiert"
    d = c.patch("/api/tasks/%d" % b, json={"status": "blocked", "status_note": "wartet auf Lieferant"}).json()
    assert t(d, b)["status"] == "blocked" and t(d, b)["status_note"] == "wartet auf Lieferant" and t(d, ph)["status"] == "blocked"
    d = c.patch("/api/tasks/%d" % a, json={"status": "in_progress"}).json()
    assert t(d, a)["percent"] == 90                                   # 100 % passt nicht zu „in Arbeit"
    d = c.patch("/api/tasks/%d" % a, json={"status": "open"}).json()
    assert t(d, a)["percent"] == 0
    # Sammelvorgang erledigen -> alle Teilvorgänge; Notiz wird verworfen
    d = c.patch("/api/tasks/%d" % ph, json={"status": "done"}).json()
    assert t(d, a)["status"] == t(d, b)["status"] == t(d, ph)["status"] == "done" and t(d, b)["percent"] == 100
    assert t(d, b)["status_note"] == ""
    # Mehrfach-Status
    d = c.post("/api/projects/%d/tasks/status" % pid, json={"task_ids": [a, b], "status": "open"}).json()
    assert t(d, a)["status"] == t(d, b)["status"] == "open"
    assert c.post("/api/projects/%d/tasks/status" % pid, json={"task_ids": [999999], "status": "open"}).status_code == 404


def test_status_import_derivation(c):
    pid = mk(c, "S")["project"]["id"]
    _, a = add(c, pid, "A")
    c.patch("/api/tasks/%d" % a, json={"percent": 100})
    raw = c.get("/api/projects/%d/export?fmt=json" % pid).content
    d = c.post("/api/projects/import", files={"file": ("x.json", raw)}).json()
    assert d["tasks"][0]["status"] == "done"
