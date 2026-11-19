from test_api import _login, add, c, mk  # noqa: F401,E402  (setzt DATA_DIR/ADMIN_PASSWORD vor allen App-Importen)


def _device(c, pid, host="rf-sw-01"):
    tid = next(t["id"] for t in c.get("/api/templates").json() if t["name"] == "Firewall")
    d = c.post("/api/projects/%d/devices" % pid, json={"template_id": tid, "hostname": host, "standort": "Werk Süd"}).json()
    dev = next(t for t in d["tasks"] if t["name"] == host)
    return dev["id"], [t["id"] for t in d["tasks"] if t["parent_id"] == dev["id"]]


def test_put_get_delete_and_idempotent(c):
    pid = mk(c, "refs")["project"]["id"]
    _, tid = add(c, pid, "Change anlegen")
    rev0 = c.get("/api/projects/%d/revision" % pid).json()["revision"]
    r = c.put("/api/tasks/%d/refs/ServiceNow" % tid, json={"ref": "CHG0012345", "url": "https://sn.example/chg/CHG0012345"})
    assert r.status_code == 200 and r.json() == {"system": "servicenow", "ref": "CHG0012345", "url": "https://sn.example/chg/CHG0012345", "changed": True}
    rev1 = c.get("/api/projects/%d/revision" % pid).json()["revision"]
    assert rev1 > rev0                                                          # Live-Update für andere Clients
    again = c.put("/api/tasks/%d/refs/servicenow" % tid, json={"ref": "CHG0012345", "url": "https://sn.example/chg/CHG0012345"}).json()
    assert again["changed"] is False and c.get("/api/projects/%d/revision" % pid).json()["revision"] == rev1     # idempotent: keine neue Revision
    c.put("/api/tasks/%d/refs/servicenow" % tid, json={"ref": "CHG0099999"})     # ersetzt
    assert c.get("/api/tasks/%d/refs" % tid).json() == [{"system": "servicenow", "ref": "CHG0099999", "url": ""}]
    t = next(x for x in c.get("/api/projects/%d" % pid).json()["tasks"] if x["id"] == tid)
    assert t["refs"] == {"servicenow": {"ref": "CHG0099999", "url": ""}}
    log = c.get("/api/projects/%d/journal" % pid).json()
    assert any(j["action"] == "Referenz gesetzt" and j["task_id"] == tid and "servicenow: CHG0099999" in j["detail"] for j in log)
    assert c.delete("/api/tasks/%d/refs/servicenow" % tid).json()["removed"] is True
    assert c.delete("/api/tasks/%d/refs/servicenow" % tid).json()["removed"] is False
    assert c.get("/api/tasks/%d/refs" % tid).json() == []


def test_validation(c):
    pid = mk(c, "refs-val")["project"]["id"]
    _, tid = add(c, pid, "A")
    assert c.put("/api/tasks/%d/refs/Ungültig!" % tid, json={"ref": "x"}).status_code == 422
    assert c.put("/api/tasks/%d/refs/awx" % tid, json={"ref": "   "}).status_code == 422
    assert c.put("/api/tasks/%d/refs/awx" % tid, json={"ref": "a\nb"}).status_code == 422
    assert c.put("/api/tasks/%d/refs/awx" % tid, json={"ref": "x" * 201}).status_code == 422
    assert c.put("/api/tasks/%d/refs/awx" % tid, json={"ref": "job-1", "url": "javascript:alert(1)"}).status_code == 422
    assert c.put("/api/tasks/%d/refs/awx" % tid, json={"ref": "job-1", "url": "ftp://x/y"}).status_code == 422
    assert c.put("/api/tasks/99999999/refs/awx", json={"ref": "x"}).status_code == 404


def test_lookup_by_hostname_and_ref(c):
    pid = mk(c, "refs-lookup")["project"]["id"]
    dev, steps = _device(c, pid, "rf-fw-01")
    c.put("/api/tasks/%d/refs/servicenow" % steps[0], json={"ref": "CHG0000042"})
    c.put("/api/tasks/%d/refs/awx" % steps[1], json={"ref": "4711", "url": "https://awx.example/#/jobs/4711"})
    c.put("/api/tasks/%d/refs/checkmk" % dev, json={"ref": "rf-fw-01"})
    r = c.get("/api/projects/%d/lookup" % pid, params={"hostname": "RF-FW-01"}).json()["items"]          # Groß-/Kleinschreibung egal
    assert len(r) == 1 and r[0]["id"] == dev and r[0]["device"] and r[0]["refs"]["checkmk"]["ref"] == "rf-fw-01"
    assert [s["id"] for s in r[0]["steps"]] == steps and r[0]["steps"][0]["refs"] == {"servicenow": "CHG0000042"}
    r = c.get("/api/projects/%d/lookup" % pid, params={"ref": "chg0000042"}).json()["items"]
    assert [x["id"] for x in r] == [steps[0]] and not r[0]["device"]
    assert c.get("/api/projects/%d/lookup" % pid, params={"ref": "4711", "system": "servicenow"}).json()["items"] == []
    assert [x["id"] for x in c.get("/api/projects/%d/lookup" % pid, params={"ref": "4711", "system": "awx"}).json()["items"]] == [steps[1]]
    assert c.get("/api/projects/%d/lookup" % pid, params={"hostname": "gibt-es-nicht"}).json()["items"] == []
    assert c.get("/api/projects/%d/lookup" % pid).status_code == 422


def test_rights_and_other_project_isolated(c):
    pid = mk(c, "refs-rights")["project"]["id"]
    other = mk(c, "refs-other")["project"]["id"]
    _, tid = add(c, pid, "A")
    _, ot = add(c, other, "B")
    c.put("/api/tasks/%d/refs/servicenow" % ot, json={"ref": "CHG-OTHER"})
    c.post("/api/users", json={"username": "ref_view", "password": "passwort-ref_view", "role": "viewer"})
    uid = next(u["id"] for u in c.get("/api/users").json() if u["username"] == "ref_view")
    c.put("/api/projects/%d/members" % pid, json=[{"user_id": uid, "role": "viewer"}])
    v = _login("ref_view", "passwort-ref_view")
    assert v.get("/api/tasks/%d/refs" % tid).status_code == 200
    assert v.put("/api/tasks/%d/refs/awx" % tid, json={"ref": "x"}).status_code == 403
    assert v.delete("/api/tasks/%d/refs/awx" % tid).status_code == 403
    assert v.get("/api/tasks/%d/refs" % ot).status_code == 404                                  # fremdes Projekt unsichtbar
    assert c.get("/api/projects/%d/lookup" % pid, params={"ref": "CHG-OTHER"}).json()["items"] == []   # Suche bleibt im Projekt


def test_cascade_on_task_delete(c):
    pid = mk(c, "refs-del")["project"]["id"]
    _, tid = add(c, pid, "Weg damit")
    c.put("/api/tasks/%d/refs/awx" % tid, json={"ref": "1"})
    assert c.delete("/api/tasks/%d" % tid).status_code == 200
    from database import connect
    conn = connect()
    n = conn.execute("SELECT COUNT(*) FROM external_refs WHERE task_id=?", (tid,)).fetchone()[0]
    conn.close()
    assert n == 0
