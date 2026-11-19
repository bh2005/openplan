"""Server-Zertifikat per ACME (RFC 8555) – z. B. gegen die interne step-ca.

Minimaler Client: Account-Key (ECDSA P-256 / ES256), HTTP-01-Challenge, Zertifikat in ``DATA_DIR/tls``.
Die Challenge-Antwort liefert die App selbst unter ``/.well-known/acme-challenge/<token>`` aus; dafür muss Port 80
der angefragten Domain auf die App (Port 8080 im Container) weitergeleitet werden.
Einstellungen und Status stehen in ``app_settings`` (Schlüssel ``acme`` / ``acme_state``).
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import ipaddress
import json
import logging
import re
import socket
import ssl
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.x509.oid import NameOID

import config
from fastapi import HTTPException

log = logging.getLogger("openplan.acme")

TLS_DIR = config.DATA_DIR / "tls"
CERT_FILE, KEY_FILE, ACCOUNT_KEY = TLS_DIR / "fullchain.pem", TLS_DIR / "privkey.pem", TLS_DIR / "account.key"
DEFAULTS: Dict[str, Any] = {
    "directory_url": "https://ca.corp.example/acme/acme/directory",
    "domains": [], "email": "it-ops@corp.example", "ca_pem": "", "auto_renew": True, "renew_days": 30, "account_url": "",
}
CHALLENGES: Dict[str, str] = {}            # token -> key authorization (HTTP-01)
_run = {"running": False, "message": ""}
_run_lock = threading.Lock()
_HOST_RE = re.compile(r"^(?=.{1,253}$)([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


class AcmeError(Exception):
    pass


# ── Einstellungen / Status ──────────────────────────────────────────────────
def _load(db, key: str) -> Optional[Dict[str, Any]]:
    r = db.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    return json.loads(r["value"]) if r else None


def _store(db, key: str, value: Dict[str, Any]) -> None:
    db.execute("INSERT INTO app_settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))


def _is_ip(v: str) -> bool:
    try:
        ipaddress.ip_address(v)
        return True
    except ValueError:
        return False


def _san_entry(d: str):
    """IP-Adressen als IPAddress-SAN (RFC 8738 'ip'-Identifier), alles andere als DNSName."""
    return x509.IPAddress(ipaddress.ip_address(d)) if _is_ip(d) else x509.DNSName(d)


def settings(db) -> Dict[str, Any]:
    return {**DEFAULTS, **(_load(db, "acme") or {})}


def validate(v: Dict[str, Any]) -> None:
    if not v["directory_url"].lower().startswith("https://"):
        raise HTTPException(422, "Die ACME-Directory-URL muss mit https:// beginnen")
    doms = v["domains"]
    if not isinstance(doms, list) or len(doms) > 20:
        raise HTTPException(422, "Domains: Liste mit höchstens 20 Einträgen")
    for d in doms:
        if not isinstance(d, str) or not _HOST_RE.match(d) or "*" in d:
            raise HTTPException(422, "Ungültiger Hostname: %r (Wildcards gehen mit HTTP-01 nicht)" % d)
    if v["email"] and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v["email"]):
        raise HTTPException(422, "E-Mail-Adresse ungültig")
    if not (1 <= int(v["renew_days"]) <= 60):
        raise HTTPException(422, "Erneuern ab: 1–60 Tage vor Ablauf")
    parse_ca_chain(v["ca_pem"] or "")


def parse_ca_chain(pem: str) -> List[Dict[str, str]]:
    """PEM-Kette (Root + Intermediate) prüfen; liefert Subject/Fingerabdruck je Zertifikat. Leer = keine eigene CA."""
    pem = pem.strip()
    if not pem:
        return []
    try:
        certs = x509.load_pem_x509_certificates(pem.encode())
    except ValueError:
        raise HTTPException(422, "CA-Zertifikat/-Kette muss im PEM-Format vorliegen (-----BEGIN CERTIFICATE----- …)")
    if not certs:
        raise HTTPException(422, "Im PEM wurde kein Zertifikat gefunden")
    out = []
    for c in certs:
        cn = c.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        out.append({"subject": cn[0].value if cn else c.subject.rfc4514_string(), "fingerprint": c.fingerprint(hashes.SHA256()).hex(":").upper()})
    return out


def fetch_ca_chain(url: str) -> Dict[str, Any]:
    """CA-Kette von einer URL laden (z. B. ks-chain-ca.pem) – nur Abruf und Prüfung, gespeichert wird erst per Formular.
    Hinweis: über http:// ist das Trust-on-first-use; die Fingerabdrücke sollten gegen die bekannten Werte geprüft werden."""
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(422, "Die URL muss mit http:// oder https:// beginnen")
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "openplan"}), timeout=15) as r:
            body = r.read(200_001)
    except (urllib.error.URLError, socket.timeout, ssl.SSLError, ValueError) as e:
        raise HTTPException(502, "Abruf fehlgeschlagen: %s" % getattr(e, "reason", e))
    if len(body) > 200_000:
        raise HTTPException(422, "Die Datei ist zu groß für eine CA-Kette")
    try:
        pem = body.decode("ascii").strip()
    except UnicodeDecodeError:
        raise HTTPException(422, "Die Datei ist kein PEM-Text")
    return {"pem": pem, "certs": parse_ca_chain(pem)}


def save_settings(db, patch: Dict[str, Any]) -> Dict[str, Any]:
    cur = settings(db)
    for k, val in patch.items():
        if k in DEFAULTS and k != "account_url" and val is not None:
            cur[k] = [d.strip().lower() for d in val if d.strip()] if k == "domains" else (val.strip() if isinstance(val, str) and k != "ca_pem" else val)
    validate(cur)
    if cur["directory_url"] != settings(db)["directory_url"]:
        cur["account_url"] = ""                       # anderer CA-Server -> neuer Account
    _store(db, "acme", cur)
    return public(db)


def cert_info() -> Optional[Dict[str, Any]]:
    if not CERT_FILE.exists():
        return None
    try:
        cert = x509.load_pem_x509_certificate(CERT_FILE.read_bytes())
    except ValueError:
        return None
    try:
        ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        san = ext.get_values_for_type(x509.DNSName) + [str(i) for i in ext.get_values_for_type(x509.IPAddress)]
    except x509.ExtensionNotFound:
        san = []
    cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    icn = cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
    na = cert.not_valid_after_utc if hasattr(cert, "not_valid_after_utc") else cert.not_valid_after.replace(tzinfo=dt.timezone.utc)
    nb = cert.not_valid_before_utc if hasattr(cert, "not_valid_before_utc") else cert.not_valid_before.replace(tzinfo=dt.timezone.utc)
    return {"subject": cn[0].value if cn else "", "issuer": icn[0].value if icn else "", "san": san,
            "not_before": nb.isoformat(), "not_after": na.isoformat(),
            "days_left": (na - dt.datetime.now(dt.timezone.utc)).days,
            "fingerprint": cert.fingerprint(hashes.SHA256()).hex(":").upper()}


def public(db) -> Dict[str, Any]:
    s = settings(db)
    s["registered"] = bool(s.pop("account_url"))
    return {"settings": s, "cert": cert_info(), "state": _load(db, "acme_state") or {}, "running": _run["running"],
            "message": _run["message"], "serving": TLS_DIR.joinpath("serving").exists()}


# ── ACME-Protokoll ──────────────────────────────────────────────────────────
def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _ctx(ca_pem: str) -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if ca_pem.strip():
        ctx.load_verify_locations(cadata=ca_pem.strip())
    return ctx


def _fetch(method: str, url: str, headers: Dict[str, str], data: Optional[bytes], ca_pem: str) -> Tuple[int, Dict[str, str], bytes]:
    """Einziger Netzwerkzugriff (per monkeypatch ersetzbar)."""
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20, context=_ctx(ca_pem)) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()
    except (urllib.error.URLError, socket.timeout, ssl.SSLError) as e:
        msg = str(getattr(e, "reason", e))
        hint = (" – CA-Kette (z. B. KS ROOT CA → KS Linux CA) unter „CA-Zertifikat“ hinterlegen"
                if "CERTIFICATE_VERIFY_FAILED" in msg or "issuer certificate" in msg else "")
        raise AcmeError("Verbindung zur CA fehlgeschlagen: %s%s" % (msg, hint))


class Client:
    def __init__(self, directory_url: str, ca_pem: str, key: ec.EllipticCurvePrivateKey, account_url: str = ""):
        self.dir_url, self.ca, self.key, self.kid = directory_url, ca_pem, key, account_url
        self.dir: Dict[str, Any] = {}
        self.nonce = ""
        pn = key.public_key().public_numbers()
        self.jwk = {"crv": "P-256", "kty": "EC", "x": b64u(pn.x.to_bytes(32, "big")), "y": b64u(pn.y.to_bytes(32, "big"))}
        self.thumb = b64u(hashlib.sha256(json.dumps(self.jwk, sort_keys=True, separators=(",", ":")).encode()).digest())

    def _sign(self, protected: Dict[str, Any], payload: Optional[Any]) -> bytes:
        p = b64u(json.dumps(protected).encode())
        pl = "" if payload is None else b64u(json.dumps(payload).encode())
        der = self.key.sign(("%s.%s" % (p, pl)).encode(), ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der)
        return json.dumps({"protected": p, "payload": pl, "signature": b64u(r.to_bytes(32, "big") + s.to_bytes(32, "big"))}).encode()

    def _get_json(self, url: str) -> Dict[str, Any]:
        st, _h, body = _fetch("GET", url, {}, None, self.ca)
        if st != 200:
            raise AcmeError("Directory nicht abrufbar (HTTP %s)" % st)
        return json.loads(body)

    def post(self, url: str, payload: Optional[Any], jwk: bool = False, accept: str = "application/json") -> Tuple[int, Dict[str, str], bytes]:
        for attempt in (0, 1):
            if not self.nonce:
                st, h, _b = _fetch("HEAD", self.dir["newNonce"], {}, None, self.ca)
                self.nonce = h.get("replay-nonce", "")
            prot = {"alg": "ES256", "nonce": self.nonce, "url": url}
            prot.update({"jwk": self.jwk} if jwk else {"kid": self.kid})
            st, h, body = _fetch("POST", url, {"Content-Type": "application/jose+json", "Accept": accept},
                                 self._sign(prot, payload), self.ca)
            self.nonce = h.get("replay-nonce", "")
            if st == 400 and b"badNonce" in body and attempt == 0:
                continue
            if st >= 400:
                try:
                    pb = json.loads(body)
                    msg = "%s (%s)" % (pb.get("detail", ""), pb.get("type", "").split(":")[-1])
                except ValueError:
                    msg = body[:200].decode(errors="replace")
                raise AcmeError("ACME-Fehler HTTP %s: %s" % (st, msg))
            return st, h, body
        raise AcmeError("Nonce-Fehler")

    def start(self, email: str) -> None:
        self.dir = self._get_json(self.dir_url)
        if not self.kid:
            payload: Dict[str, Any] = {"termsOfServiceAgreed": True}
            if email:
                payload["contact"] = ["mailto:" + email]
            _st, h, _b = self.post(self.dir["newAccount"], payload, jwk=True)
            self.kid = h.get("location", "")
            if not self.kid:
                raise AcmeError("CA hat keine Account-URL geliefert")

    def poll(self, url: str, ok: Tuple[str, ...], timeout: float = 90.0) -> Dict[str, Any]:
        end = time.time() + timeout
        while True:
            _st, _h, body = self.post(url, None)
            obj = json.loads(body)
            if obj.get("status") in ok:
                return obj
            if obj.get("status") in ("invalid", "revoked", "deactivated", "expired"):
                err = (obj.get("error") or {}).get("detail", "")
                for ch in obj.get("challenges", []):
                    err = err or (ch.get("error") or {}).get("detail", "")
                raise AcmeError("Validierung fehlgeschlagen (%s): %s" % (obj["status"], err or "kein Detail"))
            if time.time() > end:
                raise AcmeError("Zeitüberschreitung beim Warten auf die CA")
            time.sleep(1.0)

    def issue(self, domains: List[str]) -> Tuple[str, str]:
        _st, h, body = self.post(self.dir["newOrder"], {"identifiers": [{"type": "ip" if _is_ip(d) else "dns", "value": d} for d in domains]})
        order, order_url = json.loads(body), h.get("location", "")
        tokens: List[str] = []
        try:
            for authz_url in order["authorizations"]:
                _s, _h, ab = self.post(authz_url, None)
                authz = json.loads(ab)
                if authz.get("status") == "valid":
                    continue
                ch = next((c for c in authz["challenges"] if c["type"] == "http-01"), None)
                if not ch:
                    raise AcmeError("Die CA bietet für %s keine HTTP-01-Challenge an" % authz["identifier"]["value"])
                CHALLENGES[ch["token"]] = "%s.%s" % (ch["token"], self.thumb)
                tokens.append(ch["token"])
                self.post(ch["url"], {})
                self.poll(authz_url, ("valid",))
            pkey = ec.generate_private_key(ec.SECP256R1())          # step-ca erwartet EC (kein RSA)
            csr = (x509.CertificateSigningRequestBuilder()
                   .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, domains[0])]))
                   .add_extension(x509.SubjectAlternativeName([_san_entry(d) for d in domains]), critical=False)
                   .sign(pkey, hashes.SHA256()))
            self.post(order["finalize"], {"csr": b64u(csr.public_bytes(serialization.Encoding.DER))})
            done = self.poll(order_url, ("valid",))
            _s, _h, chain = self.post(done["certificate"], None, accept="application/pem-certificate-chain")
        finally:
            for t in tokens:
                CHALLENGES.pop(t, None)
        key_pem = pkey.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
        return chain.decode(), key_pem


def _account_key() -> ec.EllipticCurvePrivateKey:
    TLS_DIR.mkdir(parents=True, exist_ok=True)
    if ACCOUNT_KEY.exists():
        return serialization.load_pem_private_key(ACCOUNT_KEY.read_bytes(), None)
    key = ec.generate_private_key(ec.SECP256R1())
    ACCOUNT_KEY.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    _chmod(ACCOUNT_KEY)
    return key


def _chmod(p) -> None:
    try:
        p.chmod(0o600)
    except OSError:
        pass


def _write_atomic(path, text: str, secret: bool = False) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    if secret:
        _chmod(tmp)
    tmp.replace(path)


def request_certificate(db) -> Dict[str, Any]:
    """Zertifikat anfordern bzw. erneuern (blockierend). Wirft ``AcmeError`` bei Fehlern."""
    s = settings(db)
    if not s["domains"]:
        raise AcmeError("Keine Domains konfiguriert")
    cl = Client(s["directory_url"], s["ca_pem"], _account_key(), s["account_url"])
    cl.start(s["email"])
    if cl.kid != s["account_url"]:
        s["account_url"] = cl.kid
        _store(db, "acme", s)
    chain, key_pem = cl.issue(s["domains"])
    TLS_DIR.mkdir(parents=True, exist_ok=True)
    _write_atomic(KEY_FILE, key_pem, secret=True)          # erst Schlüssel, dann Kette (Watcher lädt bei neuer Kette)
    _write_atomic(CERT_FILE, chain)
    return cert_info() or {}


def run_issue(note: str = "manuell") -> bool:
    """Hintergrund-Lauf mit eigener DB-Verbindung; Ergebnis in ``acme_state``. Liefert False, wenn schon einer läuft."""
    from database import connect
    if not _run_lock.acquire(blocking=False):
        return False
    _run.update(running=True, message="Verbindung zur CA …")
    db = connect()
    try:
        try:
            info = request_certificate(db)
            state = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(), "ok": True, "message": "Zertifikat ausgestellt (gültig bis %s)" % info.get("not_after", "?")[:10], "trigger": note}
        except (AcmeError, ValueError, OSError) as e:
            log.error("ACME: %s", e)
            state = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(), "ok": False, "message": str(e), "trigger": note}
        _store(db, "acme_state", state)
        db.commit()
        return state["ok"]
    finally:
        db.close()
        _run.update(running=False, message="")
        _run_lock.release()


def start_issue_thread(note: str = "manuell") -> bool:
    if _run["running"]:
        return False
    threading.Thread(target=run_issue, args=(note,), daemon=True, name="acme-issue").start()
    return True


def renew_due(db) -> bool:
    s = settings(db)
    if not s["auto_renew"] or not s["domains"]:
        return False
    info = cert_info()
    if info is None or sorted(info["san"]) != sorted(s["domains"]):
        return True
    return info["days_left"] <= int(s["renew_days"])


_bg_started = False


def start_background() -> None:
    """Erneuerungs-Thread einmal pro Prozess starten."""
    global _bg_started
    if not _bg_started:
        _bg_started = True
        threading.Thread(target=renew_loop, daemon=True, name="acme-renew").start()


def renew_loop(interval: float = 6 * 3600, first_delay: float = 90.0) -> None:
    """Prüft regelmäßig, ob erneuert werden muss. Nach einem Fehler vergehen mindestens ``interval`` bis zum nächsten Versuch."""
    from database import connect
    time.sleep(first_delay)
    while True:
        try:
            db = connect()
            try:
                due = renew_due(db)
            finally:
                db.close()
            if due:
                run_issue("automatisch")
        except Exception:                       # Thread darf nie sterben
            log.exception("ACME-Erneuerungsprüfung")
        time.sleep(interval)
