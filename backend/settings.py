"""In der Verwaltung gepflegte Einstellungen (Tabelle ``app_settings``), derzeit: LDAP/Active Directory.

Umgebungsvariablen (``config.LDAP_*``) sind die Voreinstellung; sobald ein Admin die Einstellungen speichert,
gelten die Werte aus der Datenbank. Das Bind-Passwort wird nie an den Browser zurückgegeben.
"""
from __future__ import annotations

import contextlib
import json
import re
import threading
from typing import Any, Dict, Iterator, Optional

from fastapi import HTTPException

import config

_lock = threading.RLock()
_CA_FILE = config.DATA_DIR / "ldap_ca.pem"

# Feld -> (config-Attribut, Typ)
LDAP_FIELDS = {
    "url": ("LDAP_URL", str), "base_dn": ("LDAP_BASE_DN", str), "domain": ("LDAP_DOMAIN", str),
    "bind_dn": ("LDAP_BIND_DN", str), "bind_password": ("LDAP_BIND_PASSWORD", str),
    "user_filter": ("LDAP_USER_FILTER", str), "required_group": ("LDAP_REQUIRED_GROUP", str),
    "admin_group": ("LDAP_ADMIN_GROUP", str), "auditor_group": ("LDAP_AUDITOR_GROUP", str), "default_role": ("LDAP_DEFAULT_ROLE", str),
    "auto_create": ("LDAP_AUTO_CREATE", bool), "nested_groups": ("LDAP_NESTED_GROUPS", bool),
}
_ENV = {k: getattr(config, a) for k, (a, _t) in LDAP_FIELDS.items()}
_ENV["ca_pem"] = ""
_ENV["enabled"] = bool(config.LDAP_URL)
_ENV_CA_FILE = config.LDAP_CA_FILE


def _row(db) -> Optional[Dict[str, Any]]:
    r = db.execute("SELECT value FROM app_settings WHERE key='ldap'").fetchone()
    return json.loads(r["value"]) if r else None


def effective(db) -> Dict[str, Any]:
    stored = _row(db)
    return {**_ENV, **stored} if stored is not None else dict(_ENV)


def public(db) -> Dict[str, Any]:
    """Für den Browser: ohne Bind-Passwort (nur ``bind_password_set``)."""
    e = effective(db)
    out = {k: v for k, v in e.items() if k != "bind_password"}
    out["bind_password_set"] = bool(e.get("bind_password"))
    out["from_db"] = _row(db) is not None
    return out


def _set_config(values: Dict[str, Any]) -> None:
    for k, (attr, _t) in LDAP_FIELDS.items():
        if k in values:
            setattr(config, attr, values[k])
    if not values.get("enabled", True):
        config.LDAP_URL = ""
    pem = (values.get("ca_pem") or "").strip()
    if pem:
        _CA_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CA_FILE.write_text(pem + "\n")
        try:
            _CA_FILE.chmod(0o600)
        except OSError:
            pass
        config.LDAP_CA_FILE = str(_CA_FILE)
    else:
        config.LDAP_CA_FILE = _ENV_CA_FILE


def apply(db) -> None:
    """Gespeicherte Einstellungen in ``config`` übernehmen (ohne gespeicherten Datensatz bleibt die Umgebung maßgeblich)."""
    stored = _row(db)
    if stored is not None:
        with _lock:
            _set_config({**_ENV, **stored})


def validate(v: Dict[str, Any]) -> None:
    url = (v.get("url") or "").strip()
    if v.get("enabled") and not url:
        raise HTTPException(422, "LDAP-URL fehlt")
    for u in [x for x in re.split(r"[\s,;]+", url) if x]:             # mehrere Server = Ausfallsicherung
        if not u.lower().startswith(("ldap://", "ldaps://")):
            raise HTTPException(422, "Die LDAP-URL muss mit ldap:// oder ldaps:// beginnen (mehrere Server mit Leerzeichen oder Komma trennen)")
    if v.get("enabled") and not (v.get("domain") or v.get("bind_dn")):
        raise HTTPException(422, "Domain (UPN-Bind) oder Bind-DN (Service-Account) angeben")
    if v.get("enabled") and not v.get("base_dn"):
        raise HTTPException(422, "Base-DN fehlt")
    if "{username}" not in (v.get("user_filter") or ""):
        raise HTTPException(422, "Der Benutzerfilter muss {username} enthalten")
    if v.get("default_role") not in ("editor", "viewer"):
        raise HTTPException(422, "Standardrolle: editor oder viewer")
    pem = (v.get("ca_pem") or "").strip()
    if pem and not (pem.startswith("-----BEGIN CERTIFICATE-----") and pem.endswith("-----END CERTIFICATE-----")):
        raise HTTPException(422, "CA-Zertifikat muss im PEM-Format vorliegen (-----BEGIN CERTIFICATE----- …)")


def merge(db, patch: Dict[str, Any]) -> Dict[str, Any]:
    """Bestehende Werte mit Änderungen verbinden; ``bind_password`` nur bei nicht-leerer Eingabe ersetzen."""
    cur = effective(db)
    for k, v in patch.items():
        if v is None or k not in cur and k not in ("enabled", "ca_pem"):
            continue
        if k == "bind_password" and v == "":
            continue
        cur[k] = v.strip() if isinstance(v, str) and k != "ca_pem" else v
    if patch.get("clear_bind_password"):
        cur["bind_password"] = ""
    return cur


def save(db, patch: Dict[str, Any]) -> Dict[str, Any]:
    new = merge(db, patch)
    validate(new)
    db.execute("INSERT INTO app_settings(key, value) VALUES ('ldap', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               (json.dumps(new),))
    apply(db)
    return public(db)


@contextlib.contextmanager
def override(db, patch: Dict[str, Any]) -> Iterator[None]:
    """Einstellungen vorübergehend (ungespeichert) anwenden, z. B. für den Verbindungstest."""
    new = merge(db, patch)
    attrs = [a for a, _t in LDAP_FIELDS.values()] + ["LDAP_CA_FILE"]
    with _lock:
        old = {a: getattr(config, a) for a in attrs}
        try:
            _set_config(new)
            yield
        finally:
            for a, v in old.items():
                setattr(config, a, v)
