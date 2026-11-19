from test_api import _login, c  # noqa: F401,E402  (setzt DATA_DIR/ADMIN_PASSWORD vor allen App-Importen)

import pytest  # noqa: E402

import envadmin  # noqa: E402
import envfile  # noqa: E402

SAMPLE = "# Kopf\nADMIN_PASSWORD=geheim123\n\n# Mail\nMAX_UPLOAD_MB=25\nLDAP_URL=ldaps://dc:636\n"


@pytest.fixture()
def envf(tmp_path, monkeypatch):
    p = tmp_path / ".env"
    p.write_text(SAMPLE, encoding="utf-8")
    monkeypatch.setenv("ENV_FILE", str(p))
    return p


def test_quote_roundtrip():
    for v in ["", "abc", "mit Leerzeichen", "a$b#c", "pw'x", "pw'x $y \"z\" \\", "ldaps://dc:636/x?y=1", "ü ö ß"]:
        assert envfile.unquote(envfile.quote(v)) == v
    with pytest.raises(ValueError):
        envfile.quote("a\nb")
    assert envfile.parse("A=1\nA=2\n# B=3\nexport C= 'x y' # k\nD=ab # kommentar\n") == [("A", "2"), ("C", "x y"), ("D", "ab")]


def test_get_masks_secrets_and_needs_admin(c, envf):
    d = c.get("/api/admin/env").json()
    assert d["enabled"] and d["writable"]
    e = {x["key"]: x for x in d["entries"]}
    assert e["ADMIN_PASSWORD"]["value"] is None and e["ADMIN_PASSWORD"]["secret"] and e["ADMIN_PASSWORD"]["set"]
    assert e["MAX_UPLOAD_MB"]["value"] == "25"
    c.post("/api/users", json={"username": "env_ed", "password": "passwort-env_ed", "role": "editor"})
    assert _login("env_ed", "passwort-env_ed").get("/api/admin/env").status_code == 403


def test_save_keeps_comments_and_secret_and_backs_up(c, envf):
    r = c.put("/api/admin/env", json={"entries": [
        {"key": "ADMIN_PASSWORD", "value": None},                          # Geheimnis unverändert
        {"key": "MAX_UPLOAD_MB", "value": "50"},
        {"key": "HTTPS_PROXY", "value": "http://proxy:8080"},             # neu
        {"key": "NEU_MIT_LEER", "value": "a b $x"},                       # Quoting
    ]})
    assert r.status_code == 200
    text = envf.read_text(encoding="utf-8")
    assert "# Kopf" in text and "# Mail" in text and "ADMIN_PASSWORD=geheim123" in text      # Kommentare + Geheimnis bleiben
    assert "MAX_UPLOAD_MB=50" in text and "LDAP_URL" not in text                              # LDAP_URL entfernt
    assert "NEU_MIT_LEER='a b $x'" in text and "HTTPS_PROXY=http://proxy:8080" in text
    assert dict(envfile.parse(text))["NEU_MIT_LEER"] == "a b $x"
    assert r.json()["pending_restart"] is True
    baks = list(envadmin._backup_dir().glob("env-*.bak"))
    assert baks and "LDAP_URL=ldaps://dc:636" in baks[-1].read_text(encoding="utf-8")        # alte Fassung gesichert
    # Audit: nur Namen, keine Werte
    log = c.get("/api/admin/audit?action=env.save").json()
    blob = str(log)
    assert "env.save" in blob and "geheim123" not in blob and "a b $x" not in blob and "MAX_UPLOAD_MB" in blob
    # unverändert speichern = keine neue Sicherung
    n = len(list(envadmin._backup_dir().glob("env-*.bak")))
    c.put("/api/admin/env", json={"entries": [{"key": k["key"], "value": k["value"]} for k in c.get("/api/admin/env").json()["entries"]]})
    assert len(list(envadmin._backup_dir().glob("env-*.bak"))) == n


def test_validation(c, envf):
    def put(entries):
        return c.put("/api/admin/env", json={"entries": entries}).status_code
    assert put([{"key": "1BAD", "value": "x"}]) == 422
    assert put([{"key": "A B", "value": "x"}]) == 422
    assert put([{"key": "ENV_FILE", "value": "x"}]) == 422
    assert put([{"key": "A", "value": "1"}, {"key": "A", "value": "2"}]) == 422
    assert put([{"key": "NEU", "value": None}]) == 422                       # neu ohne Wert
    assert put([{"key": "MAX_UPLOAD_MB", "value": None}]) == 422             # Nicht-Geheimnis ohne Wert
    assert put([{"key": "A", "value": "zeile1\nzeile2"}]) == 422
    assert envf.read_text(encoding="utf-8") == SAMPLE                        # nichts verändert


def test_disabled_without_env_file(c, monkeypatch):
    monkeypatch.delenv("ENV_FILE", raising=False)
    d = c.get("/api/admin/env").json()
    assert d["enabled"] is False and "ENV_FILE" in d["reason"]
    assert c.put("/api/admin/env", json={"entries": []}).status_code == 409


def test_restart_gate_and_trigger(c, monkeypatch):
    calls = []
    monkeypatch.setattr(envfile, "schedule_restart", lambda *a, **k: calls.append(1))
    monkeypatch.delenv("ALLOW_SELF_RESTART", raising=False)
    assert c.post("/api/admin/restart").status_code == 409 and not calls
    monkeypatch.setenv("ALLOW_SELF_RESTART", "1")
    assert c.post("/api/admin/restart").json() == {"restarting": True} and calls == [1]
    assert "server.restart" in str(c.get("/api/admin/audit?action=server.restart").json())


def test_load_into_environ(tmp_path, monkeypatch):
    p = tmp_path / ".env"
    p.write_text("FOO_TEST_X=aus_datei\nENV_FILE=boese\n", encoding="utf-8")
    monkeypatch.setenv("FOO_TEST_X", "aus_compose")
    monkeypatch.setenv("ENV_FILE", str(p))
    envfile.load_into_environ(str(p))
    import os
    assert os.environ["FOO_TEST_X"] == "aus_datei" and os.environ["ENV_FILE"] == str(p)       # Datei hat Vorrang, ENV_FILE geschützt
    monkeypatch.delenv("FOO_TEST_X")
    envfile.load_into_environ(str(tmp_path / "gibt-es-nicht"))                               # Fehler -> kein Abbruch
