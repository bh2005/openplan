from test_api import c  # noqa: F401,E402  (setzt DATA_DIR/ADMIN_PASSWORD vor allen App-Importen)

import pytest  # noqa: E402

import acme_client  # noqa: E402
import main  # noqa: E402


@pytest.fixture()
def tls(tmp_path, monkeypatch):
    monkeypatch.setattr(acme_client, "TLS_DIR", tmp_path)
    monkeypatch.setattr(main, "FORCE_HTTPS", True)
    return tmp_path


def test_no_redirect_without_certificate_listener(c, tls):
    assert c.get("/health").status_code == 200
    r = c.get("/api/auth/me", follow_redirects=False)
    assert r.status_code != 308                                  # Marker fehlt -> nie umleiten (kein Aussperren)


def test_redirect_when_https_listener_is_serving(c, tls, monkeypatch):
    (tls / "serving").write_text("8443")
    r = c.get("/api/projects?x=1", headers={"host": "openplan.corp.test"}, follow_redirects=False)
    assert r.status_code == 308 and r.headers["location"] == "https://openplan.corp.test/api/projects?x=1"
    # Ausnahmen: Health-Check und ACME-Challenge bleiben über HTTP erreichbar
    assert c.get("/health", headers={"host": "openplan.corp.test"}, follow_redirects=False).status_code == 200
    acme_client.CHALLENGES["tok"] = "tok.key"
    try:
        assert c.get("/.well-known/acme-challenge/tok", headers={"host": "x.corp.test"}, follow_redirects=False).text == "tok.key"
    finally:
        acme_client.CHALLENGES.pop("tok", None)
    # abweichender öffentlicher Port, Host mit Port
    monkeypatch.setattr(main, "PUBLIC_HTTPS_PORT", "8443")
    r = c.get("/", headers={"host": "openplan.corp.test:8080"}, follow_redirects=False)
    assert r.headers["location"] == "https://openplan.corp.test:8443/"


def test_redirect_disabled_by_default(c, tmp_path, monkeypatch):
    monkeypatch.setattr(acme_client, "TLS_DIR", tmp_path)
    (tmp_path / "serving").write_text("8443")
    monkeypatch.setattr(main, "FORCE_HTTPS", False)
    assert c.get("/health", follow_redirects=False).status_code == 200
    assert c.get("/api/auth/me", follow_redirects=False).status_code == 200           # normal beantwortet, keine Umleitung
