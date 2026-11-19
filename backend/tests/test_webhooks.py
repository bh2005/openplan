from test_api import _login, add, c, mk  # noqa: F401,E402  (setzt DATA_DIR/ADMIN_PASSWORD/WEBHOOK_WORKER vor allen App-Importen)
from test_devices import HEAD, MAP, csv_file, do_import  # noqa: F401,E402

import hashlib  # noqa: E402
import hmac  # noqa: E402
import http.server  # noqa: E402
import json  # noqa: E402
import threading  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import database  # noqa: E402
import webhooks  # noqa: E402
from main import app  # noqa: E402


class Receiver:
    """Lokaler HTTP-Empfänger, der Anfragen mitschreibt und einen einstellbaren Statuscode liefert."""

    def __init__(self):
        self.calls, self.code = [], 200
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                outer.calls.append({"headers": {k.lower(): v for k, v in self.headers.items()}, "body": body})
                self.send_response(outer.code)
                self.end_headers()

            def log_message(self, *a):
                pass

        self.srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        self.url = "https://hook.test:%d/in" % self.srv.server_port
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    @property
    def real(self):
        return "http://127.0.0.1:%d/in" % self.srv.server_port


@pytest.fixture()
def rx(monkeypatch):
    r = Receiver()
    monkeypatch.setattr(webhooks, "check_url", lambda u: None)          # Zielprüfung wird separat getestet (lokaler Empfänger wäre Loopback)
    orig = webhooks._send

    def send(url, secret, event, did, body):                           # Phantom-URL auf den lokalen Server umbiegen
        return orig(r.real, secret, event, did, body)

    monkeypatch.setattr(webhooks, "_send", send)
    yield r
    r.srv.shutdown()


def _hook(c, name="h", **kw):
    body = {"name": name, "url": "https://10.20.30.40/in", "events": ["*"]}
    body.update(kw)
    r = c.post("/api/admin/webhooks", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _clear(c):
    for h in c.get("/api/admin/webhooks").json()["items"]:
        c.delete("/api/admin/webhooks/%d" % h["id"])


def _db(sql, *args):
    conn = database.connect()
    try:
        r = conn.execute(sql, args).fetchall()
        conn.commit()
        return r
    finally:
        conn.close()


# ── Zieladresse ───────────────────────────────────────────────────────────────────────────────────────
def test_url_rules(c, monkeypatch):
    for bad in ("http://example.com/x", "https://127.0.0.1/x", "https://localhost/x", "https://169.254.169.254/latest/meta-data",
                "https://[::1]/x", "https://user:pw@8.8.8.8/x", "ftp://8.8.8.8/x", "https:///x"):
        r = c.post("/api/admin/webhooks", json={"name": "x", "url": bad})
        assert r.status_code == 422, bad
    ok = c.post("/api/admin/webhooks", json={"name": "intern", "url": "https://10.20.30.40/hook"})        # privates Netz ist erlaubt
    assert ok.status_code == 201
    monkeypatch.setenv("WEBHOOK_ALLOW_HTTP", "1")
    assert c.post("/api/admin/webhooks", json={"name": "http", "url": "http://10.20.30.40/hook"}).status_code == 201
    monkeypatch.setenv("WEBHOOK_ALLOWED_HOSTS", "corp.example")
    assert c.post("/api/admin/webhooks", json={"name": "fremd", "url": "https://10.20.30.40/hook"}).status_code == 422
    _clear(c)


def test_admin_only_secret_once_and_events_validation(c):
    h = _hook(c, "sec")
    assert h["secret"].startswith("whsec_") and len(h["secret"]) > 30
    lst = c.get("/api/admin/webhooks").json()
    assert "secret" not in str(lst["items"]) and h["secret"] not in str(lst) and "task.status" in lst["events"]
    assert c.post("/api/admin/webhooks", json={"name": "x", "url": "https://10.1.1.1/", "events": ["gibt.es.nicht"]}).status_code == 422
    assert c.post("/api/admin/webhooks", json={"name": "x", "url": "https://10.1.1.1/", "project_id": 99999999}).status_code == 422
    c.post("/api/users", json={"username": "wh_ed", "password": "passwort-wh_ed", "role": "editor"})
    ed = _login("wh_ed", "passwort-wh_ed")
    assert ed.get("/api/admin/webhooks").status_code == 403 and ed.post("/api/admin/webhooks", json={"name": "x", "url": "https://10.1.1.1/"}).status_code == 403
    assert "sec" in str(c.get("/api/admin/audit?action=webhook.create").json()) and h["secret"] not in str(c.get("/api/admin/audit").json())
    u = c.put("/api/admin/webhooks/%d" % h["id"], json={"name": "sec2", "url": "https://10.1.1.1/", "events": ["task.status"], "rotate_secret": True}).json()
    assert u["secret"] != h["secret"] and u["name"] == "sec2" and u["events"] == ["task.status"]
    assert "secret" not in c.put("/api/admin/webhooks/%d" % h["id"], json={"name": "sec2", "url": "https://10.1.1.1/"}).json()
    _clear(c)


# ── Ereignisse und Zustellung ────────────────────────────────────────────────────────────────────────
def test_status_event_signed_delivery(c, rx):
    _clear(c)
    h = _hook(c, "sig", events=["task.status"])
    pid = mk(c, "wh-status")["project"]["id"]
    _, tid = add(c, pid, "Konfiguration ausrollen")
    c.put("/api/tasks/%d/refs/servicenow" % tid, json={"ref": "CHG0001"})
    assert c.patch("/api/tasks/%d" % tid, json={"status": "in_progress"}).status_code == 200
    assert webhooks.run_due() == 1 and len(rx.calls) == 1
    call = rx.calls[0]
    sig = "sha256=" + hmac.new(h["secret"].encode(), call["body"], hashlib.sha256).hexdigest()
    assert call["headers"]["x-openplan-signature"] == sig and call["headers"]["x-openplan-event"] == "task.status"
    assert call["headers"]["x-openplan-delivery"].isdigit() and call["headers"]["x-openplan-timestamp"].isdigit()
    p = json.loads(call["body"])
    assert p["event"] == "task.status" and p["id"].startswith("evt_") and p["actor"] == "admin" and p["previous"] == {"status": "open"}
    assert p["project"] == {"id": pid, "name": "wh-status"} and p["task"]["id"] == tid and p["task"]["status"] == "in_progress"
    assert p["task"]["refs"] == {"servicenow": "CHG0001"} and p["task"]["device"] is None
    d = c.get("/api/admin/webhooks/%d/deliveries" % h["id"]).json()
    assert d[0]["status"] == "ok" and d[0]["last_code"] == 200 and d[0]["attempts"] == 1
    # derselbe Status noch einmal / nur Notiz ändern: kein Ereignis
    c.patch("/api/tasks/%d" % tid, json={"status": "in_progress"})
    assert webhooks.run_due() == 0
    _clear(c)


def test_blocked_filter_project_and_enabled(c, rx):
    _clear(c)
    pid = mk(c, "wh-blk")["project"]["id"]
    other = mk(c, "wh-oth")["project"]["id"]
    _, tid = add(c, pid, "A")
    _, ot = add(c, other, "B")
    only_blocked = _hook(c, "nur-blockiert", events=["task.blocked"])
    both = _hook(c, "beide", events=["task.status", "task.blocked"], project_id=pid)
    off = _hook(c, "aus", enabled=False)
    c.patch("/api/tasks/%d" % tid, json={"status": "blocked", "status_note": "Lieferung fehlt"})
    c.patch("/api/tasks/%d" % ot, json={"status": "blocked"})                   # anderes Projekt: nur der projektübergreifende Hook
    assert webhooks.run_due() == 4
    by = {}
    for call in rx.calls:
        by.setdefault(call["headers"]["x-openplan-event"], []).append(json.loads(call["body"]))
    assert len(by["task.blocked"]) == 3 and len(by["task.status"]) == 1                     # 1 (nur-blockiert, pid) + 1 (nur-blockiert, other) + 1 (beide)
    assert next(p for p in by["task.blocked"] if p["project"]["id"] == pid)["task"]["status_note"] == "Lieferung fehlt"   # Notiz ist im Payload
    assert c.get("/api/admin/webhooks/%d/deliveries" % off["id"]).json() == []
    _clear(c)


def test_assignment_and_bulk_status_events(c, rx):
    _clear(c)
    _hook(c, "assign", events=["task.assigned", "task.status"])
    pid = mk(c, "wh-asg")["project"]["id"]
    _, t1 = add(c, pid, "A")
    _, t2 = add(c, pid, "B")
    rid = c.post("/api/projects/%d/resources" % pid, json={"name": "Anna"}).json()["resources"][0]["id"]
    c.put("/api/tasks/%d/assignments" % t1, json=[{"resource_id": rid, "units": 100}])
    c.put("/api/tasks/%d/assignments" % t1, json=[{"resource_id": rid, "units": 50}])        # gleiche Person: kein weiteres Ereignis
    c.post("/api/projects/%d/tasks/status" % pid, json={"task_ids": [t1, t2], "status": "done"})
    assert webhooks.run_due() == 3
    evs = sorted((json.loads(x["body"])["event"], json.loads(x["body"])["task"]["id"]) for x in rx.calls)
    assert evs == sorted([("task.assigned", t1), ("task.status", t1), ("task.status", t2)])
    asg = next(json.loads(x["body"]) for x in rx.calls if x["headers"]["x-openplan-event"] == "task.assigned")
    assert asg["assigned"] == ["Anna"] and asg["previous_assigned"] == []
    _clear(c)


def test_device_created_and_dry_run_silent(c, rx):
    _clear(c)
    _hook(c, "dev", events=["device.created"])
    pid = mk(c, "wh-dev")["project"]["id"]
    files = csv_file("wh-sw-01;Werk Nord;Switch;X;;;;;;;;OK")
    r = do_import(c, pid, files, MAP, dry_run=True, create_missing=True)
    assert r.status_code == 200 and webhooks.run_due() == 0                                  # Trockenlauf: nichts gesendet
    files = csv_file("wh-sw-01;Werk Nord;Switch;X;;;;;;;;OK")
    r = do_import(c, pid, files, MAP, dry_run=False, create_missing=True)
    assert r.status_code == 200 and r.json()["imported"] == 1
    assert webhooks.run_due() == 1
    p = json.loads(rx.calls[0]["body"])
    assert p["event"] == "device.created" and p["task"]["name"] == "wh-sw-01" and p["steps"] > 0
    assert p["task"]["device"]["hostname"] == "wh-sw-01" and p["task"]["device"]["standort"] == "Werk Nord"
    _clear(c)


def test_retry_backoff_and_give_up(c, rx):
    _clear(c)
    h = _hook(c, "retry", events=["task.status"])
    pid = mk(c, "wh-retry")["project"]["id"]
    _, tid = add(c, pid, "A")
    rx.code = 500
    c.patch("/api/tasks/%d" % tid, json={"status": "done"})
    assert webhooks.run_due() == 1
    d = _db("SELECT id, attempts, status, last_code, last_error, next_try > datetime('now') AS later FROM webhook_deliveries WHERE webhook_id=?", h["id"])[0]
    assert (d["attempts"], d["status"], d["last_code"], d["last_error"], d["later"]) == (1, "pending", 500, "HTTP 500", 1)
    assert webhooks.run_due() == 0                                                            # noch nicht fällig
    for n in range(2, 6):
        _db("UPDATE webhook_deliveries SET next_try=datetime('now','-1 minute') WHERE id=?", d["id"])
        assert webhooks.run_due() == 1
        row = _db("SELECT attempts, status FROM webhook_deliveries WHERE id=?", d["id"])[0]
        assert row["attempts"] == n
    assert row["status"] == "failed"
    assert webhooks.run_due() == 0 and len(rx.calls) == 5
    h2 = c.get("/api/admin/webhooks").json()["items"][0]
    assert h2["failed"] == 1 and h2["pending"] == 0
    _clear(c)


def test_test_button_and_unreachable(c, rx, monkeypatch):
    _clear(c)
    h = _hook(c, "ping", events=["task.status"])                                              # ping geht unabhängig von der Auswahl
    r = c.post("/api/admin/webhooks/%d/test" % h["id"]).json()
    assert r["status"] == "ok" and r["code"] == 200 and json.loads(rx.calls[0]["body"])["event"] == "ping"
    rx.srv.shutdown()
    monkeypatch.setattr(webhooks, "_send", lambda *a: (_ for _ in ()).throw(ConnectionRefusedError("refused")))
    r = c.post("/api/admin/webhooks/%d/test" % h["id"]).json()
    assert r["status"] == "pending" and "ConnectionRefusedError" in r["error"]
    assert c.post("/api/admin/webhooks/99999/test").status_code == 404
    _clear(c)


def test_no_redirect_and_ssrf_recheck_at_send(c, monkeypatch):
    _clear(c)
    h = _hook(c, "ssrf", events=["task.status"])
    pid = mk(c, "wh-ssrf")["project"]["id"]
    _, tid = add(c, pid, "A")
    c.patch("/api/tasks/%d" % tid, json={"status": "done"})
    _db("UPDATE webhooks SET url='https://127.0.0.1:9/x' WHERE id=?", h["id"])                  # Ziel nachträglich auf Loopback gebogen
    assert webhooks.run_due() == 1
    d = _db("SELECT status, last_error FROM webhook_deliveries WHERE webhook_id=?", h["id"])[0]
    assert d["status"] == "pending" and "nicht zulässig" in d["last_error"]
    assert webhooks._NoRedirect().redirect_request(None, None, 302, "", {}, "http://x") is None
    _clear(c)


def test_delete_removes_deliveries_and_prune(c, rx):
    _clear(c)
    h = _hook(c, "weg", events=["task.status"])
    pid = mk(c, "wh-del")["project"]["id"]
    _, tid = add(c, pid, "A")
    c.patch("/api/tasks/%d" % tid, json={"status": "done"})
    webhooks.run_due()
    _db("UPDATE webhook_deliveries SET ts=datetime('now','-15 days') WHERE webhook_id=?", h["id"])
    webhooks.prune()
    assert _db("SELECT COUNT(*) AS n FROM webhook_deliveries WHERE webhook_id=?", h["id"])[0]["n"] == 0
    c.patch("/api/tasks/%d" % tid, json={"status": "open"})
    assert c.delete("/api/admin/webhooks/%d" % h["id"]).status_code == 200
    assert c.delete("/api/admin/webhooks/%d" % h["id"]).status_code == 404
    assert _db("SELECT COUNT(*) AS n FROM webhook_deliveries")[0]["n"] == 0


# ── Callback-Endpunkt ─────────────────────────────────────────────────────────────────────────────
def test_callback_sets_status_ref_and_is_idempotent(c, rx):
    _clear(c)
    _hook(c, "cb", events=["task.status"])
    pid = mk(c, "wh-cb")["project"]["id"]
    _, tid = add(c, pid, "Konfig ausrollen")
    body = {"status": "done", "note": "AWX-Job 4711 erfolgreich", "system": "awx", "ref": "4711", "url": "https://awx.example/#/jobs/4711"}
    r = c.post("/api/tasks/%d/events" % tid, json=body)
    assert r.status_code == 200 and r.json()["changed"] and r.json()["task"]["status"] == "done" and r.json()["task"]["percent"] == 100
    assert c.get("/api/tasks/%d/refs" % tid).json() == [{"system": "awx", "ref": "4711", "url": "https://awx.example/#/jobs/4711"}]
    rev = c.get("/api/projects/%d/revision" % pid).json()["revision"]
    again = c.post("/api/tasks/%d/events" % tid, json=body).json()
    assert again["changed"] is False and c.get("/api/projects/%d/revision" % pid).json()["revision"] == rev      # idempotent
    assert webhooks.run_due() == 1 and json.loads(rx.calls[0]["body"])["task"]["refs"] == {"awx": "4711"}
    assert any(j["action"] == "Rückmeldung (API)" for j in c.get("/api/projects/%d/journal" % pid).json())
    # Sammelvorgang, halbe Referenz, unbekanntes System
    parent, _ = add(c, pid, "Phase")
    _, kid = add(c, pid, "Kind", parent_id=next(t["id"] for t in parent["tasks"] if t["name"] == "Phase"))
    assert c.post("/api/tasks/%d/events" % next(t["id"] for t in parent["tasks"] if t["name"] == "Phase"), json={"status": "done"}).status_code == 422
    assert c.post("/api/tasks/%d/events" % tid, json={"system": "awx"}).status_code == 422
    assert c.post("/api/tasks/%d/events" % tid, json={"system": "evil", "ref": "x"}).status_code == 422
    assert c.post("/api/tasks/99999999/events", json={"status": "done"}).status_code == 404
    _clear(c)


def test_callback_with_service_token_rights(c):
    pid = mk(c, "wh-cb-tok")["project"]["id"]
    _, tid = add(c, pid, "A")
    ro = c.post("/api/admin/tokens", json={"name": "ro", "username": "svc-cb-ro", "scope": "read"}).json()
    rw = c.post("/api/admin/tokens", json={"name": "rw", "username": "svc-cb-rw", "scope": "write"}).json()
    members = [{"user_id": u["id"], "role": "editor"} for u in c.get("/api/users").json() if u["username"] in ("svc-cb-ro", "svc-cb-rw")]
    assert c.put("/api/projects/%d/members" % pid, json=members).status_code == 200

    def cl(tok):
        x = TestClient(app)
        x.headers["Authorization"] = "Bearer " + tok["token"]
        return x
    assert cl(ro).post("/api/tasks/%d/events" % tid, json={"status": "done"}).status_code == 403          # read-Token darf nicht melden
    r = cl(rw).post("/api/tasks/%d/events" % tid, json={"status": "in_progress", "system": "awx", "ref": "1"})
    assert r.status_code == 200 and r.json()["task"]["status"] == "in_progress"
    assert cl(rw).get("/api/admin/webhooks").status_code == 403                                           # Token verwaltet keine Webhooks
