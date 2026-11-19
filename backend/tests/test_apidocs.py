from test_api import _login, c  # noqa: F401,E402  (setzt DATA_DIR/ADMIN_PASSWORD/WEBHOOK_WORKER vor allen App-Importen)

import re  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import apidocs  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture()
def anon():
    with TestClient(app) as cl:
        yield cl


def test_open_mode_default(anon, monkeypatch):
    monkeypatch.delenv("API_DOCS", raising=False)
    r = anon.get("/docs")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "cdn." not in r.text and "jsdelivr" not in r.text and "unpkg" not in r.text           # keine externen Quellen
    for url in re.findall(r'(?:src|href)="([^"]+)"', r.text):
        assert url.startswith("/docs-assets/"), url
        a = anon.get(url)
        assert a.status_code == 200 and len(a.content) > 100, url
    assert "javascript" in anon.get("/docs-assets/swagger-ui-bundle.js").headers["content-type"]
    assert "css" in anon.get("/docs-assets/swagger-ui.css").headers["content-type"]
    js = anon.get("/docs-assets/openplan-docs.js")
    assert js.status_code == 200 and "/openapi.json" in js.text and "queryConfigEnabled: false" in js.text
    spec = anon.get("/openapi.json").json()
    assert spec["info"]["title"] == "OpenPlan" and "HTTPBearer" in spec["components"]["securitySchemes"]
    assert "Authorization: Bearer" in spec["info"]["description"]
    assert anon.get("/docs-assets/gibtes-nicht.js").status_code == 404 and anon.get("/docs-assets/..%2f..%2fmain.py").status_code in (404, 422)


def test_every_operation_has_tag_and_summary(anon, monkeypatch):
    """Neuer Endpunkt ohne Tag/Beschreibung? Dann TAG_RULES / SUMMARIES in apidocs.py ergänzen."""
    monkeypatch.delenv("API_DOCS", raising=False)
    spec = anon.get("/openapi.json").json()
    known = {n for n, _ in apidocs.TAGS}
    missing = []
    for path, ops in spec["paths"].items():
        for m, op in ops.items():
            key = "%s %s" % (m.upper(), path)
            if not op.get("tags") or op["tags"][0] not in known:
                missing.append("Tag fehlt: " + key)
            if key not in apidocs.SUMMARIES:
                missing.append("Beschreibung fehlt: " + key)
    assert not missing, "\n".join(missing)
    stale = [k for k in apidocs.SUMMARIES if k.split(" ", 1)[1] not in spec["paths"] or k.split(" ", 1)[0].lower() not in spec["paths"][k.split(" ", 1)[1]]]
    assert not stale, "SUMMARIES für nicht mehr vorhandene Endpunkte: %s" % stale
    used = {op["tags"][0] for ops in spec["paths"].values() for op in ops.values()}
    assert used == known, "Tags ohne Endpunkte: %s" % (known - used)


def test_tags_sample(anon, monkeypatch):
    monkeypatch.delenv("API_DOCS", raising=False)
    p = anon.get("/openapi.json").json()["paths"]
    assert p["/api/auth/login"]["post"]["tags"] == ["Anmeldung"] and p["/api/auth/login"]["post"]["summary"] == "Anmelden und Token erhalten"
    assert p["/api/admin/tokens"]["get"]["tags"] == ["API-Zugänge"] and p["/api/admin/webhooks"]["post"]["tags"] == ["Webhooks"]
    assert p["/api/tasks/{tid}/events"]["post"]["tags"] == ["Integration"] and p["/api/projects/{pid}/lookup"]["get"]["tags"] == ["Integration"]
    assert p["/api/projects/{pid}/budget"]["get"]["tags"] == ["Budget & Kosten"] and p["/api/tasks/{tid}"]["patch"]["tags"] == ["Vorgänge"]
    assert p["/api/projects/{pid}"]["get"]["tags"] == ["Projekte"] and p["/api/admin/env"]["get"]["tags"] == ["Verwaltung"]
    assert p["/health"]["get"]["tags"] == ["System"] and p["/api/templates"]["get"]["tags"] == ["Geräte & Vorlagen"]


def test_admin_mode(c, anon, monkeypatch):
    monkeypatch.setenv("API_DOCS", "admin")
    assert anon.get("/openapi.json").status_code == 401                                          # nicht angemeldet
    c.post("/api/users", json={"username": "docs_ed", "password": "passwort-docs_ed", "role": "editor"})
    assert _login("docs_ed", "passwort-docs_ed").get("/openapi.json").status_code == 403         # Editor
    svc = c.post("/api/admin/tokens", json={"name": "docs", "username": "svc-docs", "scope": "read"}).json()
    tc = TestClient(app)
    tc.headers["Authorization"] = "Bearer " + svc["token"]
    assert tc.get("/openapi.json").status_code == 403                                            # Dienstkonto ist nie Admin
    r = c.get("/openapi.json")                                                                   # Admin
    assert r.status_code == 200 and len(r.json()["paths"]) > 100
    page = anon.get("/docs")
    assert page.status_code == 200 and "paths" not in page.text and "/api/projects" not in page.text   # Seite ist nur die Hülle, ohne API-Struktur
    assert anon.get("/docs-assets/swagger-ui.css").status_code == 200


def test_off_mode(c, anon, monkeypatch):
    monkeypatch.setenv("API_DOCS", "0")
    for url in ("/docs", "/openapi.json", "/docs-assets/swagger-ui-bundle.js", "/docs-assets/openplan-docs.js"):
        r = anon.get(url)
        assert r.status_code == 404 and "abgeschaltet" in r.text, url
    assert c.get("/openapi.json").status_code == 404                                             # auch für Admins
    assert c.get("/api/auth/me").status_code == 200                                              # die API selbst läuft weiter
    for v in ("false", "off", "no", "AUS"):
        monkeypatch.setenv("API_DOCS", v)
        assert anon.get("/docs").status_code == 404


def test_mode_values(monkeypatch):
    for v, m in (("", "open"), ("1", "open"), ("true", "open"), ("admin", "admin"), (" Admin ", "admin"), ("0", "off"), ("off", "off")):
        monkeypatch.setenv("API_DOCS", v)
        assert apidocs.mode() == m, v
    monkeypatch.delenv("API_DOCS")
    assert apidocs.mode() == "open"
