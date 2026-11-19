import pytest
from ldap3 import MOCK_SYNC, Connection, Server

import config
import ldap_auth
from test_api import c  # noqa: F401  (Admin-Client + Test-DB)

BASE = "DC=corp,DC=test"
GRP_USERS = "CN=OpenPlan-Users,OU=G," + BASE
GRP_ADMINS = "CN=OpenPlan-Admins,OU=G," + BASE
SVC = "CN=svc,OU=S," + BASE


@pytest.fixture()
def ad(monkeypatch):
    """Gemockter Verzeichnisdienst (ldap3 MOCK_SYNC) mit Service-Account und drei Benutzern."""
    server = Server("mock-ad")
    boot = Connection(server, user=SVC, password="svcpw", client_strategy=MOCK_SYNC)
    boot.strategy.add_entry(SVC, {"userPassword": "svcpw", "objectClass": ["user"], "sAMAccountName": "svc"})
    def person(sam, pw, groups=()):
        boot.strategy.add_entry("CN=%s,OU=U,%s" % (sam, BASE), {
            "userPassword": pw, "objectClass": ["user"], "sAMAccountName": sam,
            "displayName": sam.title(), "memberOf": list(groups)})
    person("ldap_anna", "anna-pw-123", [GRP_USERS])
    person("ldap_boss", "boss-pw-123", [GRP_USERS, GRP_ADMINS])
    person("ldap_fremd", "fremd-pw-123")
    boot.bind()

    def fake_open(user, password):
        conn = Connection(server, user=user, password=password, client_strategy=MOCK_SYNC)
        return conn if conn.bind() else None
    monkeypatch.setattr(ldap_auth, "_open", fake_open)
    for k, v in dict(LDAP_URL="ldaps://mock", LDAP_BASE_DN=BASE, LDAP_BIND_DN=SVC, LDAP_BIND_PASSWORD="svcpw",
                     LDAP_DOMAIN="", LDAP_REQUIRED_GROUP="", LDAP_ADMIN_GROUP="", LDAP_NESTED_GROUPS=False,
                     LDAP_AUTO_CREATE=True, LDAP_DEFAULT_ROLE="editor").items():
        monkeypatch.setattr(config, k, v)
    return monkeypatch


def login(c, u, p):
    return c.post("/api/auth/login", json={"username": u, "password": p})


def test_ldap_disabled_by_default(c):
    assert not ldap_auth.enabled()
    assert login(c, "ldap_anna", "anna-pw-123").status_code == 401


def test_ldap_login_creates_account(c, ad):
    r = login(c, "ldap_anna", "anna-pw-123")
    assert r.status_code == 200 and r.json()["user"]["role"] == "editor"
    assert login(c, "ldap_anna", "anna-pw-123").status_code == 200            # zweiter Login: Konto vorhanden
    assert login(c, "ldap_anna", "falsch").status_code == 401
    assert login(c, "ldap_anna", "").status_code == 401                       # leeres Passwort = anonymer Bind -> nie zulassen
    assert login(c, "ldap_gibtsnicht", "x").status_code == 401
    users = {u["username"]: u for u in c.get("/api/users").json()}
    assert users["ldap_anna"]["auth_source"] == "ldap"
    # Der Hash des AD-Kontos ist kein gültiges lokales Passwort
    ad.setattr(config, "LDAP_URL", "")
    assert login(c, "ldap_anna", "anna-pw-123").status_code == 401


def test_ldap_filter_injection_rejected(c, ad):
    assert login(c, "*)(sAMAccountName=*", "x").status_code == 401
    assert login(c, "ldap_anna)(objectClass=*", "anna-pw-123").status_code == 401


def test_ldap_required_group(c, ad):
    ad.setattr(config, "LDAP_REQUIRED_GROUP", GRP_USERS)
    assert login(c, "ldap_fremd", "fremd-pw-123").status_code == 401         # richtiges Passwort, aber nicht in der Gruppe
    assert login(c, "ldap_anna", "anna-pw-123").status_code == 200


def test_ldap_admin_group_and_viewer_default(c, ad):
    ad.setattr(config, "LDAP_ADMIN_GROUP", GRP_ADMINS)
    ad.setattr(config, "LDAP_DEFAULT_ROLE", "viewer")
    assert login(c, "ldap_boss", "boss-pw-123").json()["user"]["role"] == "admin"
    assert login(c, "ldap_anna", "anna-pw-123").json()["user"]["role"] in ("viewer", "editor")  # Konto evtl. aus Vortest
    # Entfernen aus der Admin-Gruppe stuft beim nächsten Login herab
    ad.setattr(config, "LDAP_ADMIN_GROUP", "CN=Andere,OU=G," + BASE)
    assert login(c, "ldap_boss", "boss-pw-123").json()["user"]["role"] == "viewer"


def test_ldap_no_auto_create(c, ad):
    ad.setattr(config, "LDAP_AUTO_CREATE", False)
    assert login(c, "ldap_fremd", "fremd-pw-123").status_code == 403
    # Vorab angelegtes AD-Konto (ohne Passwort) funktioniert
    r = c.post("/api/users", json={"username": "ldap_fremd", "role": "viewer", "source": "ldap"})
    assert r.status_code == 201
    assert login(c, "ldap_fremd", "fremd-pw-123").status_code == 200


def test_local_account_not_hijacked_and_password_rules(c, ad):
    c.post("/api/users", json={"username": "ldap_anna2", "password": "lokal-pw-123", "role": "editor"})
    assert login(c, "ldap_anna2", "lokal-pw-123").status_code == 200
    assert login(c, "admin", "testpass123").status_code == 200               # lokaler Admin bleibt als Notzugang
    # lokale Benutzer brauchen ein Passwort
    assert c.post("/api/users", json={"username": "ohne_pw", "role": "editor"}).status_code == 422
    # AD-Benutzer können ihr Passwort nicht in OpenPlan ändern
    tok = login(c, "ldap_anna", "anna-pw-123").json()["token"]
    r = c.post("/api/auth/password", json={"old_password": "x", "new_password": "neues-pw-12345"}, headers={"Authorization": "Bearer " + tok})
    assert r.status_code == 400 and "Active Directory" in r.json()["detail"]


def test_ldap_settings_api(c, ad):
    # Standard: aus der Umgebung (leer), nie mit Bind-Passwort in der Antwort
    s = c.get("/api/admin/settings/ldap").json()
    assert "bind_password" not in s and s["from_db"] is False and s["default_role"] == "editor"
    # Speichern mit Validierung
    assert c.put("/api/admin/settings/ldap", json={"url": "http://x"}).status_code == 422
    assert c.put("/api/admin/settings/ldap", json={"user_filter": "(sAMAccountName=x)"}).status_code == 422
    assert c.put("/api/admin/settings/ldap", json={"ca_pem": "kein pem"}).status_code == 422
    s = c.put("/api/admin/settings/ldap", json={"enabled": True, "url": "ldaps://mock", "base_dn": BASE, "bind_dn": SVC,
                                                 "bind_password": "svcpw", "nested_groups": False}).json()
    assert s["from_db"] and s["bind_password_set"] and s["url"] == "ldaps://mock"
    # Leeres Passwortfeld lässt das gespeicherte unverändert -> Login funktioniert weiter
    c.put("/api/admin/settings/ldap", json={"bind_password": ""})
    assert login(c, "ldap_anna", "anna-pw-123").status_code == 200
    # Test-Endpunkt: nur Service-Account, dann voller Test mit Benutzer; falsches Passwort zeigt den fehlgeschlagenen Schritt
    t = c.post("/api/admin/settings/ldap/test", json={}).json()
    assert t["ok"] and t["steps"][0]["step"] == "Service-Account-Bind"
    t = c.post("/api/admin/settings/ldap/test", json={"username": "ldap_anna", "password": "anna-pw-123"}).json()
    assert t["ok"] and [x["step"] for x in t["steps"]][:3] == ["Service-Account-Bind", "Benutzer suchen", "Passwort prüfen"]
    grp = [x for x in t["steps"] if x["step"] == "Gruppen des Benutzers"]
    assert grp and grp[0]["ok"] and GRP_USERS in grp[0]["detail"] and grp[0]["detail"].startswith("1 direkte Gruppen")   # Hilfe fürs Eintragen der Gruppen-DNs
    t = c.post("/api/admin/settings/ldap/test", json={"username": "ldap_anna", "password": "falsch"}).json()
    assert not t["ok"] and t["steps"][-1]["step"] == "Passwort prüfen" and not t["steps"][-1]["ok"]
    # Ungespeicherte Formularwerte (falsche Base-DN) werden nur für den Test genutzt
    t = c.post("/api/admin/settings/ldap/test", json={"settings": {"base_dn": "DC=nix"}, "username": "ldap_anna", "password": "anna-pw-123"}).json()
    assert not t["ok"]
    assert config.LDAP_BASE_DN == BASE
    # Deaktivieren sperrt AD-Logins, lokaler Admin bleibt
    c.put("/api/admin/settings/ldap", json={"enabled": False})
    assert login(c, "ldap_anna", "anna-pw-123").status_code == 401 and login(c, "admin", "testpass123").status_code == 200
    import database
    conn = database.connect(); conn.execute("DELETE FROM app_settings"); conn.commit(); conn.close()   # Testzustand zurücksetzen
    # Nur Admins
    tok = login(c, "ldap_anna2", "lokal-pw-123")
    if tok.status_code == 200:
        assert c.get("/api/admin/settings/ldap", headers={"Authorization": "Bearer " + tok.json()["token"]}).status_code == 403


def test_failover_only_on_connectivity_problems(monkeypatch):
    monkeypatch.setattr(config, "LDAP_URL", "ldaps://a.corp.test:636, ldaps://b.corp.test:636")
    calls = []

    def one(url, user, password):
        calls.append(url)
        if url.startswith("ldaps://a"):
            return None, "unavailable", "timeout"
        return "CONN", None, ""
    monkeypatch.setattr(ldap_auth, "_open_one", one)
    assert ldap_auth.urls() == ["ldaps://a.corp.test:636", "ldaps://b.corp.test:636"]
    assert ldap_auth._open("u", "p") == "CONN" and calls == ["ldaps://a.corp.test:636", "ldaps://b.corp.test:636"]
    assert ldap_auth._last_url == "ldaps://b.corp.test:636"
    calls.clear()                                                         # falsche Zugangsdaten: kein Versuch auf dem zweiten Server
    monkeypatch.setattr(ldap_auth, "_open_one", lambda url, u, p: (calls.append(url), (None, "invalid", "invalidCredentials"))[1])
    assert ldap_auth._open("u", "p") is None and calls == ["ldaps://a.corp.test:636"] and "invalidCredentials" in ldap_auth._last_error
    calls.clear()                                                         # alle Server tot: beide Fehler im Protokoll
    monkeypatch.setattr(ldap_auth, "_open_one", lambda url, u, p: (calls.append(url), (None, "unavailable", "timeout"))[1])
    assert ldap_auth._open("u", "p") is None and len(calls) == 2
    assert "a.corp.test" in ldap_auth._last_error and "b.corp.test" in ldap_auth._last_error


def test_multiple_urls_in_settings_api(c):
    ok = c.put("/api/admin/settings/ldap", json={"url": "ldaps://dc1.corp.test:636 ldaps://dc2.corp.test:636", "domain": "corp.test", "base_dn": BASE})
    assert ok.status_code == 200 and ok.json()["url"].count("ldaps://") == 2
    assert c.put("/api/admin/settings/ldap", json={"url": "ldaps://dc1.corp.test http://x"}).status_code == 422
    import database
    conn = database.connect(); conn.execute("DELETE FROM app_settings"); conn.commit(); conn.close()


def test_ldap_display_name_synced(c, ad):
    assert login(c, "ldap_anna", "anna-pw-123").status_code == 200
    row = next(u for u in c.get("/api/users").json() if u["username"] == "ldap_anna")
    assert row["display_name"] == "Ldap_Anna"                                   # aus displayName angelegt
    import database
    with database.connect() as db:
        db.execute("UPDATE users SET display_name='alt' WHERE username='ldap_anna'")
    assert login(c, "ldap_anna", "anna-pw-123").status_code == 200
    assert next(u for u in c.get("/api/users").json() if u["username"] == "ldap_anna")["display_name"] == "Ldap_Anna"   # beim Login abgeglichen
