import io
import os
import sys
import tempfile

import pytest

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
os.environ.setdefault("ADMIN_PASSWORD", "testpass123")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient  # noqa: E402

import files_api  # noqa: E402
from main import app  # noqa: E402


def login(u, p):
    cl = TestClient(app)
    cl.headers["Authorization"] = "Bearer " + cl.post("/api/auth/login", json={"username": u, "password": p}).json()["token"]
    return cl


@pytest.fixture(scope="module")
def c():
    with TestClient(app):
        pass
    return login("admin", os.environ["ADMIN_PASSWORD"])


@pytest.fixture()
def tk(c):
    pid = c.post("/api/projects", json={"name": "Docs", "start_date": "2026-10-12"}).json()["project"]["id"]
    tid = c.post("/api/projects/%d/tasks" % pid, json={"name": "Lieferung"}).json()["tasks"][0]["id"]
    return {"pid": pid, "tid": tid}


def up(c, tid, name="Lieferschein.pdf", data=b"%PDF-1.4 test", mime="application/pdf", **kw):
    return c.post("/api/tasks/%d/files" % tid, files=[("files", (name, io.BytesIO(data), mime))], data=kw)


def test_upload_list_download_delete(c, tk):
    r = up(c, tk["tid"], comment="Palette 1")
    assert r.status_code == 201
    f = r.json()[0]
    assert f["filename"] == "Lieferschein.pdf" and f["size"] == 13 and f["comment"] == "Palette 1" and f["kind"] == "file"
    d = c.get("/api/files/%d/download" % f["id"])
    assert d.content == b"%PDF-1.4 test" and "attachment" in d.headers["content-disposition"]
    assert d.headers["x-content-type-options"] == "nosniff" and d.headers["content-type"].startswith("application/octet-stream")
    inl = c.get("/api/files/%d/download?inline=true" % f["id"])
    assert "inline" in inl.headers["content-disposition"] and inl.headers["content-type"] == "application/pdf"
    proj = c.get("/api/projects/%d" % tk["pid"]).json()
    assert proj["tasks"][0]["file_count"] == 1
    assert c.delete("/api/files/%d" % f["id"]).status_code == 200
    assert c.get("/api/tasks/%d/files" % tk["tid"]).json() == []
    assert c.get("/api/files/%d/download" % f["id"]).status_code == 404


def test_filename_sanitized_and_blocked_types(c, tk):
    f = up(c, tk["tid"], name="../../etc/pass wd.xlsx", mime="application/vnd.ms-excel").json()[0]
    assert f["filename"] == "pass wd.xlsx"                              # keine Pfadanteile
    assert files_api.clean_name("C:\\Temp\\a\x00b\x1f.txt") == "ab.txt" and files_api.clean_name("..") == "datei"
    stored = [n for n in os.listdir(os.path.join(str(files_api.FILES_DIR), str(tk["pid"])))]
    assert all(len(n) == 32 for n in stored)                            # nur UUID-Namen auf der Platte
    for bad in ("virus.exe", "x.HTML", "bild.svg", "run.ps1"):
        assert up(c, tk["tid"], name=bad).status_code == 415
    assert up(c, tk["tid"], data=b"").status_code == 422


def test_size_limit_is_all_or_nothing(c, tk, monkeypatch):
    monkeypatch.setattr(files_api, "MAX_BYTES", 10)
    r = c.post("/api/tasks/%d/files" % tk["tid"], files=[("files", ("a.txt", io.BytesIO(b"1234"), "text/plain")),
                                                         ("files", ("b.txt", io.BytesIO(b"x" * 50), "text/plain"))])
    assert r.status_code == 413
    assert c.get("/api/tasks/%d/files" % tk["tid"]).json() == []
    d = os.path.join(str(files_api.FILES_DIR), str(tk["pid"]))
    assert not os.path.isdir(d) or os.listdir(d) == []                  # auch a.txt wurde wieder entfernt


def test_permissions(c, tk):
    for n, role in (("doc_ed", "editor"), ("doc_vw", "editor"), ("doc_x", "editor")):
        c.post("/api/users", json={"username": n, "password": "passwort-" + n, "role": role})
    uid = {u["username"]: u["id"] for u in c.get("/api/users").json()}
    c.put("/api/projects/%d/members" % tk["pid"], json=[{"user_id": uid["doc_ed"], "role": "editor"}, {"user_id": uid["doc_vw"], "role": "viewer"}])
    f = up(c, tk["tid"]).json()[0]
    ed, vw, xx = login("doc_ed", "passwort-doc_ed"), login("doc_vw", "passwort-doc_vw"), login("doc_x", "passwort-doc_x")
    assert up(ed, tk["tid"], name="stunden.xlsx").status_code == 201
    assert vw.get("/api/files/%d/download" % f["id"]).status_code == 200
    assert vw.post("/api/tasks/%d/files" % tk["tid"], files=[("files", ("a.txt", io.BytesIO(b"x"), "text/plain"))]).status_code == 403
    assert vw.delete("/api/files/%d" % f["id"]).status_code == 403
    assert xx.get("/api/files/%d/download" % f["id"]).status_code == 404   # Fremde erfahren nichts
    assert xx.get("/api/tasks/%d/files" % tk["tid"]).status_code == 404


def test_cleanup_on_task_and_project_delete(c, tk):
    ph = c.post("/api/projects/%d/tasks" % tk["pid"], json={"name": "Phase"}).json()["tasks"][-1]["id"]
    kid = c.post("/api/projects/%d/tasks" % tk["pid"], json={"name": "Kind"}).json()["tasks"][-1]["id"]
    c.post("/api/tasks/%d/move" % kid, json={"parent_id": ph, "index": 0})
    up(c, kid, name="kind.xlsx")
    up(c, tk["tid"])
    d = os.path.join(str(files_api.FILES_DIR), str(tk["pid"]))
    n0 = len(os.listdir(d))
    c.delete("/api/tasks/%d" % ph)                                         # Phase samt Kind -> deren Datei weg
    assert len(os.listdir(d)) == n0 - 1
    c.delete("/api/projects/%d" % tk["pid"])
    assert not os.path.exists(d)


def test_links(c, tk):
    url = "https://example-my.sharepoint.com/:x:/g/personal/anna/Stundenzettel_KW42.xlsx?e=abc"
    r = c.post("/api/tasks/%d/links" % tk["tid"], json={"url": url, "title": "Stundenzettel KW42", "comment": "OneDrive"})
    assert r.status_code == 201
    l = r.json()[0]
    assert l["kind"] == "link" and l["url"] == url and l["filename"] == "Stundenzettel KW42" and l["size"] == 0
    assert c.get("/api/projects/%d" % tk["pid"]).json()["tasks"][0]["file_count"] == 1
    # Titel-Vorgabe aus der URL; gefährliche/ungültige Links werden abgelehnt
    t2 = c.post("/api/tasks/%d/links" % tk["tid"], json={"url": "https://example.com/ordner/Lieferschein.pdf"}).json()
    assert any(x["filename"] == "Lieferschein.pdf" for x in t2)
    for bad in ("javascript:alert(1)", "ftp://x.de/a", "https://", "https://a.de/x y", "//evil.de/x", "file:///c:/x"):
        assert c.post("/api/tasks/%d/links" % tk["tid"], json={"url": bad if len(bad) >= 8 else bad + "........"}).status_code == 422
    assert c.get("/api/files/%d/download" % l["id"]).status_code == 400
    assert c.delete("/api/files/%d" % l["id"]).status_code == 200
