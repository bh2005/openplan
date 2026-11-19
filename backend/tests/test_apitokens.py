from test_api import _login, c, mk  # noqa: F401,E402  (setzt DATA_DIR/ADMIN_PASSWORD vor allen App-Importen)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import auth  # noqa: E402
from main import app  # noqa: E402


def _client(token):
    cl = TestClient(app)
    cl.headers["Authorization"] = "Bearer " + token
    return cl


def _new(c, **kw):
    body = {"name": "awx", "username": "svc-awx", "role": "editor", "scope": "write", "project_ids": [], "expires_days": 30}
    body.update(kw)
    r = c.post("/api/admin/tokens", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _member(c, pid, username, role="editor"):
    uid = next(u["id"] for u in c.get("/api/users").json() if u["username"] == username)
    assert c.put("/api/projects/%d/members" % pid, json=[{"user_id": uid, "role": role}]).status_code == 200
    return uid


def test_create_list_and_secret_only_once(c):
    t = _new(c, name="erstes", username="svc-once")
    assert t["token"].startswith("op_") and len(t["token"]) > 30 and t["token"].startswith(t["prefix"])
    lst = c.get("/api/admin/tokens").json()
    row = next(x for x in lst if x["id"] == t["id"])
    assert "token" not in row and row["username"] == "svc-once" and row["scope"] == "write" and row["expires_at"] and not row["expired"]
    assert t["token"] not in str(lst)
    log = str(c.get("/api/admin/audit?action=token.create").json())
    assert "erstes" in log and t["token"] not in log
    me = _client(t["token"]).get("/api/auth/me").json()
    assert me["username"] == "svc-once" and me["role"] == "editor" and me["token"]["scope"] == "write"


def test_only_admin_manages_tokens(c):
    t = _new(c, name="adm", username="svc-adm")
    svc = _client(t["token"])
    assert svc.get("/api/admin/tokens").status_code == 403
    assert svc.post("/api/admin/tokens", json={"name": "x", "username": "svc-zwei"}).status_code == 403
    c.post("/api/users", json={"username": "tok_ed", "password": "passwort-tok_ed", "role": "editor"})
    assert _login("tok_ed", "passwort-tok_ed").get("/api/admin/tokens").status_code == 403


def test_service_account_cannot_login_and_name_clash(c):
    _new(c, name="login", username="svc-login")
    with TestClient(app) as anon:
        assert anon.post("/api/auth/login", json={"username": "svc-login", "password": ""}).status_code == 401
        assert anon.post("/api/auth/login", json={"username": "svc-login", "password": "service$"}).status_code == 401
    r = c.post("/api/admin/tokens", json={"name": "x", "username": "admin"})
    assert r.status_code == 409
    uid = next(u["id"] for u in c.get("/api/users").json() if u["username"] == "svc-login")
    assert c.put("/api/users/%d/password" % uid, json={"new_password": "irgendwas-123"}).status_code == 400
    assert c.put("/api/users/%d/role" % uid, json={"role": "admin"}).status_code == 400


def test_read_scope_blocks_writes(c):
    pid = mk(c, "tok-read")["project"]["id"]
    t = _new(c, name="ro", username="svc-ro", scope="read")
    _member(c, pid, "svc-ro")
    ro = _client(t["token"])
    assert ro.get("/api/projects/%d" % pid).status_code == 200
    r = ro.post("/api/projects/%d/tasks" % pid, json={"name": "nein"})
    assert r.status_code == 403 and "nur lesen" in r.text


def test_write_scope_edits_in_member_project_only(c):
    pid = mk(c, "tok-write")["project"]["id"]
    other = mk(c, "tok-other")["project"]["id"]
    t = _new(c, name="rw", username="svc-rw", scope="write")
    _member(c, pid, "svc-rw")
    rw = _client(t["token"])
    assert rw.post("/api/projects/%d/tasks" % pid, json={"name": "per Token"}).status_code == 201
    assert rw.get("/api/projects/%d" % other).status_code == 404            # kein Mitglied -> Projekt unsichtbar
    assert [p["id"] for p in rw.get("/api/projects").json()] == [pid]


def test_project_restriction(c):
    a = mk(c, "tok-a")["project"]["id"]
    b = mk(c, "tok-b")["project"]["id"]
    t = _new(c, name="eng", username="svc-eng", scope="write", project_ids=[a])
    uid = next(u["id"] for u in c.get("/api/users").json() if u["username"] == "svc-eng")
    for pid in (a, b):                                                         # Mitglied in beiden, Token nur für a
        c.put("/api/projects/%d/members" % pid, json=[{"user_id": uid, "role": "editor"}])
    eng = _client(t["token"])
    assert eng.get("/api/projects/%d" % a).status_code == 200
    assert eng.get("/api/projects/%d" % b).status_code == 404
    assert b not in [p["id"] for p in eng.get("/api/projects").json()]
    assert eng.post("/api/projects", json={"name": "neu", "start_date": "2026-10-12"}).status_code == 403
    assert c.post("/api/admin/tokens", json={"name": "x", "username": "svc-eng", "project_ids": [999999]}).status_code == 422


def test_revoke_expired_and_unknown(c):
    t = _new(c, name="weg", username="svc-weg")
    cl = _client(t["token"])
    assert cl.get("/api/auth/me").status_code == 200
    assert c.delete("/api/admin/tokens/%d" % t["id"]).status_code == 200
    assert cl.get("/api/auth/me").status_code == 401
    assert c.delete("/api/admin/tokens/%d" % t["id"]).status_code == 404
    assert _client("op_gibtesnicht").get("/api/auth/me").status_code == 401

    t2 = _new(c, name="alt", username="svc-alt")
    from database import connect
    conn = connect()
    conn.execute("UPDATE api_tokens SET expires_at=datetime('now','-1 day') WHERE id=?", (t2["id"],))
    conn.commit()
    conn.close()
    r = _client(t2["token"]).get("/api/auth/me")
    assert r.status_code == 401 and "abgelaufen" in r.text
    assert next(x for x in c.get("/api/admin/tokens").json() if x["id"] == t2["id"])["expired"]


def test_last_used_and_rate_limit(c, monkeypatch):
    t = _new(c, name="rate", username="svc-rate")
    cl = _client(t["token"])
    assert cl.get("/api/auth/me").status_code == 200
    assert next(x for x in c.get("/api/admin/tokens").json() if x["id"] == t["id"])["last_used_at"]
    monkeypatch.setattr(auth, "RATE_LIMIT", 3)
    codes = [cl.get("/api/auth/me").status_code for _ in range(5)]
    assert codes.count(429) >= 2 and codes[0] == 200


def test_jwt_still_works_and_bad_jwt_rejected(c):
    assert c.get("/api/auth/me").status_code == 200
    assert _client("kein.gueltiges.jwt").get("/api/auth/me").status_code == 401
