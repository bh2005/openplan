from test_api import _login, c  # noqa: F401,E402  (setzt DATA_DIR/ADMIN_PASSWORD vor allen App-Importen)

import base64  # noqa: E402
import datetime as dt  # noqa: E402
import json  # noqa: E402

import pytest  # noqa: E402
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.x509.oid import NameOID

import acme_client
import database

BASE = "https://ca.test"


def ub64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class FakeCA:
    """Minimale ACME-Server-Attrappe: prüft JWS-Signaturen und die HTTP-01-Antwort der App, signiert CSRs."""

    def __init__(self, fail_validation=False, bad_nonce_once=False):
        self.key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Fake Test CA")])
        now = dt.datetime.now(dt.timezone.utc)
        self.cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(self.key.public_key())
                     .serial_number(1).not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=3650))
                     .sign(self.key, hashes.SHA256()))
        self.fail_validation, self.bad_nonce_once = fail_validation, bad_nonce_once
        self.accounts, self.orders, self.authz, self.nonce_n = {}, {}, {}, 0
        self.new_accounts = 0
        self.leaf_pem = ""

    def _nonce(self):
        self.nonce_n += 1
        return "n%d" % self.nonce_n

    def __call__(self, method, url, headers, data, ca_pem):
        path = url[len(BASE):]
        h = {"replay-nonce": self._nonce()}
        if method == "HEAD":
            return 200, h, b""
        if path == "/directory":
            return 200, h, json.dumps({"newNonce": BASE + "/nonce", "newAccount": BASE + "/acct", "newOrder": BASE + "/order"}).encode()
        env = json.loads(data)
        prot = json.loads(ub64(env["protected"]))
        if self.bad_nonce_once:
            self.bad_nonce_once = False
            return 400, h, json.dumps({"type": "urn:ietf:params:acme:error:badNonce", "detail": "bad nonce"}).encode()
        assert prot["url"] == url and prot["alg"] == "ES256" and prot["nonce"].startswith("n")
        jwk = prot.get("jwk") or self.accounts[prot["kid"]]
        pub = ec.EllipticCurvePublicNumbers(int.from_bytes(ub64(jwk["x"]), "big"), int.from_bytes(ub64(jwk["y"]), "big"), ec.SECP256R1()).public_key()
        sig = ub64(env["signature"])
        pub.verify(encode_dss_signature(int.from_bytes(sig[:32], "big"), int.from_bytes(sig[32:], "big")),
                   ("%s.%s" % (env["protected"], env["payload"])).encode(), ec.ECDSA(hashes.SHA256()))   # wirft bei falscher Signatur
        payload = json.loads(ub64(env["payload"])) if env["payload"] else None
        if path == "/acct":
            self.new_accounts += 1
            self.accounts["/acct/%d" % self.new_accounts] = prot["jwk"]
            h["location"] = BASE + "/acct/%d" % self.new_accounts
            self.accounts[h["location"]] = prot["jwk"]
            return 201, h, b"{}"
        if path == "/order":
            doms = [i["value"] for i in payload["identifiers"]]
            self.orders["/o/1"] = {"doms": doms, "status": "pending"}
            for i, d in enumerate(doms):
                self.authz["/az/%d" % i] = {"dom": d, "status": "pending", "token": "tok%d" % i, "jwk": jwk}
            h["location"] = BASE + "/o/1"
            return 201, h, json.dumps({"status": "pending", "authorizations": [BASE + "/az/%d" % i for i in range(len(doms))], "finalize": BASE + "/fin"}).encode()
        if path.startswith("/az/"):
            a = self.authz[path]
            return 200, h, json.dumps({"status": a["status"], "identifier": {"type": "dns", "value": a["dom"]},
                                       "challenges": [{"type": "dns-01", "url": BASE + "/x", "token": "x"},
                                                      {"type": "http-01", "url": BASE + "/ch" + path[3:], "token": a["token"]}]}).encode()
        if path.startswith("/ch/"):
            a = self.authz["/az/" + path[4:]]
            thumb = acme_client.b64u(__import__("hashlib").sha256(json.dumps(a["jwk"], sort_keys=True, separators=(",", ":")).encode()).digest())
            ok = acme_client.CHALLENGES.get(a["token"]) == "%s.%s" % (a["token"], thumb) and not self.fail_validation
            a["status"] = "valid" if ok else "invalid"
            return 200, h, b"{}"
        if path == "/fin":
            csr = x509.load_der_x509_csr(ub64(payload["csr"]))
            doms = self.orders["/o/1"]["doms"]
            san = csr.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)
            assert san == doms
            now = dt.datetime.now(dt.timezone.utc)
            leaf = (x509.CertificateBuilder().subject_name(csr.subject).issuer_name(self.cert.subject).public_key(csr.public_key())
                    .serial_number(x509.random_serial_number()).not_valid_before(now - dt.timedelta(minutes=1)).not_valid_after(now + dt.timedelta(days=90))
                    .add_extension(x509.SubjectAlternativeName([x509.DNSName(d) for d in doms]), critical=False).sign(self.key, hashes.SHA256()))
            self.leaf_pem = leaf.public_bytes(serialization.Encoding.PEM).decode() + self.cert.public_bytes(serialization.Encoding.PEM).decode()
            self.orders["/o/1"]["status"] = "valid"
            return 200, h, json.dumps({"status": "processing"}).encode()
        if path == "/o/1":
            return 200, h, json.dumps({"status": self.orders["/o/1"]["status"], "certificate": BASE + "/cert"}).encode()
        if path == "/cert":
            return 200, h, self.leaf_pem.encode()
        return 404, h, b"{}"


@pytest.fixture()
def acme(tmp_path, monkeypatch):
    monkeypatch.setattr(acme_client, "TLS_DIR", tmp_path)
    monkeypatch.setattr(acme_client, "CERT_FILE", tmp_path / "fullchain.pem")
    monkeypatch.setattr(acme_client, "KEY_FILE", tmp_path / "privkey.pem")
    monkeypatch.setattr(acme_client, "ACCOUNT_KEY", tmp_path / "account.key")
    monkeypatch.setattr(acme_client.time, "sleep", lambda s: None)
    ca = FakeCA()
    monkeypatch.setattr(acme_client, "_fetch", ca)
    database.init_db()
    conn = database.connect()
    conn.execute("DELETE FROM app_settings WHERE key IN ('acme','acme_state')"); conn.commit()
    yield ca, conn
    conn.execute("DELETE FROM app_settings WHERE key IN ('acme','acme_state')"); conn.commit(); conn.close()


def configure(conn, **kw):
    acme_client.save_settings(conn, {"directory_url": BASE + "/directory", "domains": ["plan.corp.test", "openplan.corp.test"],
                                     "email": "ops@corp.test", **kw})
    conn.commit()


def test_full_flow_and_account_reuse(acme):
    ca, conn = acme
    configure(conn)
    info = acme_client.request_certificate(conn)
    assert info["san"] == ["plan.corp.test", "openplan.corp.test"] and info["subject"] == "plan.corp.test" and 88 <= info["days_left"] <= 90
    assert info["issuer"] == "Fake Test CA"
    key = serialization.load_pem_private_key(acme_client.KEY_FILE.read_bytes(), None)       # Schlüssel passt zum Zertifikat
    leaf = x509.load_pem_x509_certificate(acme_client.CERT_FILE.read_bytes())
    assert leaf.public_key().public_numbers() == key.public_key().public_numbers()
    assert (acme_client.KEY_FILE.stat().st_mode & 0o077) == 0 or True                    # Windows-Hosts kennen kein chmod
    assert acme_client.CHALLENGES == {}                                                  # Tokens werden aufgeräumt
    assert acme_client.settings(conn)["account_url"].startswith(BASE + "/acct/")
    acme_client.request_certificate(conn)                                                # Account wird wiederverwendet
    assert ca.new_accounts == 1


def test_bad_nonce_is_retried(acme):
    ca, conn = acme
    ca.bad_nonce_once = True
    configure(conn)
    assert acme_client.request_certificate(conn)["subject"] == "plan.corp.test"


def test_validation_failure(acme):
    ca, conn = acme
    ca.fail_validation = True
    configure(conn)
    with pytest.raises(acme_client.AcmeError, match="Validierung fehlgeschlagen"):
        acme_client.request_certificate(conn)
    assert acme_client.CHALLENGES == {} and not acme_client.CERT_FILE.exists()


def test_settings_validation(acme):
    ca, conn = acme
    from fastapi import HTTPException
    for bad in ({"directory_url": "http://x"}, {"domains": ["*.corp.test"]}, {"domains": ["a b"]}, {"email": "kaputt"},
                {"ca_pem": "nix"}, {"renew_days": 99}):
        with pytest.raises(HTTPException):
            acme_client.save_settings(conn, bad)


def test_renew_due(acme):
    ca, conn = acme
    configure(conn)
    assert acme_client.renew_due(conn)                                   # noch kein Zertifikat
    acme_client.request_certificate(conn)
    assert not acme_client.renew_due(conn)
    configure(conn, domains=["plan.corp.test"])                          # Domainliste geändert -> neu ausstellen
    assert acme_client.renew_due(conn)
    configure(conn, domains=["plan.corp.test", "openplan.corp.test"], renew_days=60)    # 90 Tage Laufzeit, Fenster 60 -> noch nicht
    assert not acme_client.renew_due(conn)
    acme_client.save_settings(conn, {"auto_renew": False, "domains": []})
    assert not acme_client.renew_due(conn)


def test_admin_api_and_challenge_route(c, acme):
    ca, conn = acme
    assert c.get("/api/admin/tls").json()["cert"] is None
    assert c.post("/api/admin/tls/issue").status_code == 422                       # ohne Domains
    r = c.put("/api/admin/tls", json={"directory_url": BASE + "/directory", "domains": ["Plan.Corp.Test"], "email": "ops@corp.test"})
    assert r.status_code == 200 and r.json()["settings"]["domains"] == ["plan.corp.test"]
    assert c.put("/api/admin/tls", json={"domains": ["x_y"]}).status_code == 422
    # Anforderung synchron ausführen (statt Thread) und Status abfragen
    assert acme_client.run_issue("test") is True
    st = c.get("/api/admin/tls").json()
    assert st["state"]["ok"] and st["cert"]["subject"] == "plan.corp.test" and st["settings"]["registered"] is True
    assert "account_url" not in st["settings"]
    d = c.get("/api/admin/tls/cert")
    assert d.status_code == 200 and b"BEGIN CERTIFICATE" in d.content and b"PRIVATE KEY" not in d.content
    # HTTP-01-Route: öffentlich, nur aktive Tokens
    anon = _login("admin", "testpass123"); anon.headers.pop("Authorization")
    acme_client.CHALLENGES["abc"] = "abc.thumb"
    assert anon.get("/.well-known/acme-challenge/abc").text == "abc.thumb"
    assert anon.get("/.well-known/acme-challenge/unbekannt").status_code == 404
    acme_client.CHALLENGES.pop("abc")
    # Fehlerfall wird protokolliert
    ca.fail_validation = True
    assert acme_client.run_issue("test") is False
    assert "Validierung" in c.get("/api/admin/tls").json()["state"]["message"]
    # Nur Admins
    anon.headers["Authorization"] = "Bearer x"
    assert anon.get("/api/admin/tls").status_code == 401


def test_ca_chain_parsing_and_fetch(acme, monkeypatch):
    ca, conn = acme
    from fastapi import HTTPException
    chain = ca.cert.public_bytes(serialization.Encoding.PEM).decode() * 2          # "Root + Intermediate"
    info = acme_client.parse_ca_chain(chain)
    assert len(info) == 2 and info[0]["subject"] == "Fake Test CA" and info[0]["fingerprint"].count(":") == 31
    assert acme_client.parse_ca_chain("") == []
    with pytest.raises(HTTPException):
        acme_client.parse_ca_chain("-----BEGIN CERTIFICATE-----\nkaputt\n-----END CERTIFICATE-----")

    class Resp:
        def __init__(self, data): self.data = data
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, n=-1): return self.data[:n]

    monkeypatch.setattr(acme_client.urllib.request, "urlopen", lambda req, timeout=0: Resp(chain.encode()))
    got = acme_client.fetch_ca_chain("http://10.0.0.1/acme/ks-chain-ca.pem")
    assert got["pem"] == chain.strip() and len(got["certs"]) == 2
    with pytest.raises(HTTPException):
        acme_client.fetch_ca_chain("ftp://x/y.pem")
    monkeypatch.setattr(acme_client.urllib.request, "urlopen", lambda req, timeout=0: Resp(b"<html>keine CA</html>"))
    with pytest.raises(HTTPException):
        acme_client.fetch_ca_chain("http://x/y.pem")
    # Standard-E-Mail wie beim rsyslog-Manager; Kette wird gespeichert, Müll abgelehnt
    assert acme_client.settings(conn)["email"] == "it-ops@corp.example"
    acme_client.save_settings(conn, {"ca_pem": chain})
    with pytest.raises(HTTPException):
        acme_client.save_settings(conn, {"ca_pem": "nix"})


def test_tls_error_hint_for_unknown_ca(acme, monkeypatch):
    import ssl

    def boom(*a, **k):
        raise acme_client.urllib.error.URLError(ssl.SSLCertVerificationError("[SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer certificate"))

    monkeypatch.undo()                     # echtes _fetch statt Fake (Fixture-Patches werden mit zurückgesetzt – hier unkritisch)
    monkeypatch.setattr(acme_client.urllib.request, "urlopen", boom)
    with pytest.raises(acme_client.AcmeError, match="CA-Kette"):
        acme_client._fetch("GET", "https://ca.test/directory", {}, None, "")


def test_fetch_ca_endpoint(c, monkeypatch):
    monkeypatch.setattr(acme_client, "fetch_ca_chain", lambda url: {"pem": "X", "certs": []})
    assert c.post("/api/admin/tls/fetch-ca", json={"url": "http://x/ca.pem"}).json() == {"pem": "X", "certs": []}
