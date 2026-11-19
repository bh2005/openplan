from test_api import _login, c, mk  # noqa: F401,E402  (setzt DATA_DIR/ADMIN_PASSWORD/WEBHOOK_WORKER vor allen App-Importen)
from test_devices import MAP, csv_file, do_import  # noqa: F401,E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import integrations  # noqa: E402
from main import app  # noqa: E402

DNS = {}


@pytest.fixture(autouse=True)
def fake_dns(monkeypatch):
    DNS.clear()
    monkeypatch.setattr(integrations, "resolve", lambda name: set(DNS.get(name.lower().rstrip("."), ())) or ({name} if name[:1].isdigit() else set()))


def _template(c):
    if not any(t["name"] == "Linux-Server" for t in c.get("/api/templates").json()):
        r = c.post("/api/templates", json={"name": "Linux-Server", "category": "Server", "steps": [
            {"name": "OS patchen", "role": "Linux-Team", "duration": 1}, {"name": "CVE-Check durchführen", "role": "Linux-Team", "duration": 1, "pred_pos": 1},
            {"name": "Abnahme", "role": "Linux-Team", "duration": 1, "pred_pos": 2}]})
        assert r.status_code == 201, r.text


def _project(c, name, hosts):
    _template(c)
    pid = mk(c, name)["project"]["id"]
    rows = ["%s;Werk Nord;Linux-Server;;;;;;;;;OK" % h for h in hosts]
    r = do_import(c, pid, csv_file(*rows), MAP, dry_run=False, create_missing=True)
    assert r.status_code == 200 and r.json()["imported"] == len(hosts), r.text
    return pid


def _task(c, pid, host, step):
    d = c.get("/api/projects/%d" % pid).json()
    dev = next(t for t in d["tasks"] if t["name"] == host and t["ext_key"])
    return next(t for t in d["tasks"] if t["parent_id"] == dev["id"] and t["name"] == step)


def _post(cl, pid, results, jtype="patch", job_id=7, **kw):
    body = {"job": {"id": job_id, "name": "Patch Mittwoch", "type": jtype, "url": "https://autopatch.example/jobs/%d" % job_id},
            "results": results, "project_id": pid, **kw}
    r = cl.post("/api/integrations/autopatch/results", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _h(name, status="success", ip=None, **kw):
    return {"hostname": name, "status": status, "ip": ip, **kw}


def test_success_by_name_with_dns_ok_sets_done_ref_and_is_idempotent(c):
    pid = _project(c, "ap-ok", ["srv-app-01"])
    DNS["srv-app-01"] = {"10.0.0.1"}
    res = _post(c, pid, [_h("SRV-APP-01", ip="10.0.0.1", packages_updated=12)])
    it = res["items"][0]
    assert res["applied"] == 1 and it["outcome"] == "applied" and it["match"] == "name" and it["dns"] == "ok" and it["step"] == "OS patchen"
    t = _task(c, pid, "srv-app-01", "OS patchen")
    assert t["status"] == "done" and t["percent"] == 100
    assert t["refs"]["autopatch"] == {"ref": "job-7", "url": "https://autopatch.example/jobs/7"}
    assert _task(c, pid, "srv-app-01", "CVE-Check durchführen")["status"] == "open"          # nur der passende Schritt
    rev = c.get("/api/projects/%d/revision" % pid).json()["revision"]
    again = _post(c, pid, [_h("srv-app-01", ip="10.0.0.1")])["items"][0]
    assert again["outcome"] == "already_done" and c.get("/api/projects/%d/revision" % pid).json()["revision"] == rev
    assert any(j["action"] == "Rückmeldung (AutoPatch)" for j in c.get("/api/projects/%d/journal" % pid).json())


def test_short_name_and_dns_only_match(c):
    pid = _project(c, "ap-match", ["srv-app-02", "srv-app-03"])
    DNS.update({"srv-app-02": {"10.0.0.2"}, "srv-app-03": {"10.0.0.3"}})
    it = _post(c, pid, [_h("srv-app-02.corp.example", ip="10.0.0.2")])["items"][0]               # FQDN ↔ Kurzname
    assert it["outcome"] == "applied" and it["match"] == "short" and it["dns"] == "ok"
    it = _post(c, pid, [_h("altername-xyz", ip="10.0.0.3")])["items"][0]                       # anderer Name, gleiche IP
    assert it["outcome"] == "applied" and it["match"] == "dns" and it["device"] == "srv-app-03"
    assert _post(c, pid, [_h("altername-xyz")])["items"][0]["outcome"] == "no_device"           # ohne IP keine DNS-Zuordnung
    assert _post(c, pid, [_h("unbekannt", ip="10.9.9.9")])["items"][0]["outcome"] == "no_device"


def test_dns_conflict_blocks_and_off_ignores(c):
    pid = _project(c, "ap-conf", ["srv-app-04"])
    DNS["srv-app-04"] = {"10.0.0.4"}
    it = _post(c, pid, [_h("srv-app-04", ip="10.0.0.99")])["items"][0]                          # gleicher Name, andere Maschine
    assert it["outcome"] == "dns_conflict" and it["dns"] == "mismatch" and "10.0.0.4" in it["message"] and "10.0.0.99" in it["message"]
    assert _task(c, pid, "srv-app-04", "OS patchen")["status"] == "open"
    it = _post(c, pid, [_h("srv-app-04", ip="10.0.0.99")], dns="off")["items"][0]
    assert it["outcome"] == "applied" and it["dns"] is None
    assert _task(c, pid, "srv-app-04", "OS patchen")["status"] == "done"


def test_unresolvable_is_applied_with_warning(c):
    pid = _project(c, "ap-unres", ["srv-app-05"])
    it = _post(c, pid, [_h("srv-app-05")])["items"][0]                                          # weder Gerät noch Server auflösbar
    assert it["outcome"] == "applied" and it["dns"] == "unresolved"


def test_ambiguous_device(c):
    pid = _project(c, "ap-amb", ["srv-dup.a.example", "srv-dup.b.example"])
    it = _post(c, pid, [_h("srv-dup")], dns="off")["items"][0]
    assert it["outcome"] == "ambiguous_device" and "srv-dup.a.example" in it["message"]
    assert _post(c, pid, [_h("srv-dup.b.example")], dns="off")["items"][0]["outcome"] == "applied"      # exakter Name löst es auf


def test_failed_running_skipped_and_recovery(c):
    pid = _project(c, "ap-states", ["srv-app-06"])
    DNS["srv-app-06"] = {"10.0.0.6"}
    ip = "10.0.0.6"
    assert _post(c, pid, [_h("srv-app-06", "running", ip)])["items"][0]["outcome"] == "applied"
    assert _task(c, pid, "srv-app-06", "OS patchen")["status"] == "in_progress"
    res = _post(c, pid, [_h("srv-app-06", "failed", ip, error="TASK [apt]\nfatal: Paket kaputt")], job_id=8)
    t = _task(c, pid, "srv-app-06", "OS patchen")
    assert res["items"][0]["outcome"] == "applied" and t["status"] == "blocked"
    assert t["status_note"] == "AutoPatch-Job #8 fehlgeschlagen: fatal: Paket kaputt" and t["refs"]["autopatch"]["ref"] == "job-8"
    assert _post(c, pid, [_h("srv-app-06", "skipped", ip)], job_id=9)["items"][0]["outcome"] == "skipped"
    assert _task(c, pid, "srv-app-06", "OS patchen")["status"] == "blocked"
    _post(c, pid, [_h("srv-app-06", "success", ip, reboot_required=True)], job_id=10)
    t = _task(c, pid, "srv-app-06", "OS patchen")
    assert t["status"] == "done" and t["status_note"] == "Neustart nötig" and t["refs"]["autopatch"]["ref"] == "job-10"


def test_cve_job_step_default_and_override(c):
    pid = _project(c, "ap-cve", ["srv-app-07"])
    DNS["srv-app-07"] = {"10.0.0.7"}
    it = _post(c, pid, [_h("srv-app-07", ip="10.0.0.7")], jtype="cve_check")["items"][0]
    assert it["step"] == "CVE-Check durchführen" and _task(c, pid, "srv-app-07", "CVE-Check durchführen")["status"] == "done"
    assert _task(c, pid, "srv-app-07", "OS patchen")["status"] == "open"
    it = _post(c, pid, [_h("srv-app-07", ip="10.0.0.7")], step="^Abnahme$")["items"][0]          # Schrittname überschrieben
    assert it["step"] == "Abnahme" and it["outcome"] == "applied"
    assert _post(c, pid, [_h("srv-app-07", ip="10.0.0.7")], step="gibtesnicht")["items"][0]["outcome"] == "no_step"
    it = _post(c, pid, [_h("srv-app-07", ip="10.0.0.7")], step="CVE|patchen")["items"][0]           # zwei Schritte passen: nichts raten
    assert it["outcome"] == "ambiguous_step" and "OS patchen" in it["message"] and "CVE-Check durchführen" in it["message"]
    r = c.post("/api/integrations/autopatch/results", json={"job": {"id": 1}, "results": [], "step": "(["})
    assert r.status_code == 422


def test_rights_and_scope(c):
    pid = _project(c, "ap-rights", ["srv-app-08"])
    DNS["srv-app-08"] = {"10.0.0.8"}
    ro = c.post("/api/admin/tokens", json={"name": "ro", "username": "svc-ap-ro", "scope": "read"}).json()
    rw = c.post("/api/admin/tokens", json={"name": "rw", "username": "svc-ap-rw", "scope": "write"}).json()
    vw = c.post("/api/admin/tokens", json={"name": "vw", "username": "svc-ap-vw", "scope": "write", "role": "viewer"}).json()
    uid = {u["username"]: u["id"] for u in c.get("/api/users").json()}
    c.put("/api/projects/%d/members" % pid, json=[{"user_id": uid["svc-ap-ro"], "role": "editor"}, {"user_id": uid["svc-ap-rw"], "role": "editor"},
                                                  {"user_id": uid["svc-ap-vw"], "role": "viewer"}])

    def cl(tok):
        x = TestClient(app)
        x.headers["Authorization"] = "Bearer " + tok["token"]
        return x
    body = {"job": {"id": 1}, "results": [_h("srv-app-08", ip="10.0.0.8")], "project_id": pid}
    assert cl(ro).post("/api/integrations/autopatch/results", json=body).status_code == 403          # read-Token darf nicht senden
    assert cl(vw).post("/api/integrations/autopatch/results", json=body).status_code == 403          # Leser im Projekt: kein Bearbeiterzugriff
    r = cl(rw).post("/api/integrations/autopatch/results", json=body).json()
    assert r["applied"] == 1 and _task(c, pid, "srv-app-08", "OS patchen")["status"] == "done"
    # ohne project_id: nur Projekte mit Bearbeiterzugriff werden durchsucht
    r = cl(rw).post("/api/integrations/autopatch/results", json={"job": {"id": 2}, "results": [_h("srv-app-08", ip="10.0.0.8")]}).json()
    assert r["items"][0]["outcome"] == "already_done" and r["items"][0]["project_id"] == pid
    assert cl(rw).post("/api/integrations/autopatch/results", json={**body, "project_id": 99999999}).status_code == 404
    with TestClient(app) as anon:
        assert anon.post("/api/integrations/autopatch/results", json=body).status_code == 401
