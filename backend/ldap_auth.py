"""Anmeldung gegen LDAP/Active Directory (ldap3).

Zwei Betriebsarten:
* Service-Account (``LDAP_BIND_DN``): Benutzer suchen, dann als gefundener DN mit dem Passwort binden.
* UPN-Bind (nur ``LDAP_DOMAIN``): direkt als ``benutzer@domain`` binden, danach die eigenen Attribute lesen.

Leere Passwörter werden nie weitergereicht (LDAP wertet einen Bind ohne Passwort als anonym = „erfolgreich").
Die Konfiguration liegt in ``config.LDAP_*``; ``settings.apply`` überschreibt sie mit den in der Verwaltung gepflegten Werten.
"""
from __future__ import annotations

import logging
import re
import ssl
from typing import Any, Dict, List, Optional

import config

log = logging.getLogger("openplan.ldap")
_USER_RE = re.compile(r"^[A-Za-z0-9._\-@ ]{1,64}$")
NESTED_RULE = "1.2.840.113556.1.4.1941"
_last_error = ""
_last_url = ""


def enabled() -> bool:
    return bool(config.LDAP_URL and (config.LDAP_DOMAIN or config.LDAP_BIND_DN))


def urls() -> List[str]:
    """Konfigurierte Server (``LDAP_URL``: mehrere durch Leerzeichen, Komma oder Semikolon getrennt = Ausfallsicherung)."""
    return [u for u in re.split(r"[\s,;]+", config.LDAP_URL.strip()) if u]


def _open_one(url: str, user: str, password: str):
    """Ein Server: ``(Verbindung, art, detail)``; art ``None`` = gebunden, ``"invalid"`` = Zugangsdaten abgelehnt,
    ``"unavailable"`` = Verbindungs-/TLS-Problem. (Testbar per monkeypatch.)"""
    from ldap3 import Connection, Server, Tls
    from ldap3.core.exceptions import LDAPException
    ssl_on = url.lower().startswith("ldaps")
    try:
        tls = Tls(ca_certs_file=config.LDAP_CA_FILE or None, validate=ssl.CERT_REQUIRED) if ssl_on else None
        server = Server(url, use_ssl=ssl_on, tls=tls, connect_timeout=5)
        conn = Connection(server, user=user, password=password, receive_timeout=10)
        if conn.bind():
            return conn, None, ""
        return None, "invalid", str((conn.result or {}).get("description") or "Bind abgelehnt")
    except LDAPException as e:
        return None, "unavailable", "%s: %s" % (type(e).__name__, e)


def _open(user: str, password: str):
    """Verbindung aufbauen und binden; ``None`` bei falschen Zugangsdaten/Verbindungsfehler. Mehrere Server werden der
    Reihe nach versucht, aber nur bei Verbindungsproblemen – abgelehnte Zugangsdaten werden nie auf weiteren Servern wiederholt."""
    global _last_error, _last_url
    _last_error, _last_url = "", ""
    errors: List[str] = []
    for url in urls():
        conn, kind, detail = _open_one(url, user, password)
        if conn:
            _last_url = url
            return conn
        if kind == "invalid":
            _last_error = "%s (%s)" % (detail, url) if len(urls()) > 1 else detail
            return None
        errors.append("%s: %s" % (url, detail) if len(urls()) > 1 else detail)
        log.error("LDAP-Fehler (%s): %s", url, detail)
    _last_error = " | ".join(errors) or "keine LDAP-URL konfiguriert"
    return None


def _is_member(conn, user_dn: str, member_of: list, group_dn: str) -> bool:
    from ldap3.utils.conv import escape_filter_chars as esc
    if not group_dn:
        return True
    if group_dn.lower() in [m.lower() for m in member_of]:
        return True
    if config.LDAP_NESTED_GROUPS:
        flt = "(&(distinguishedName=%s)(memberOf:%s:=%s))" % (esc(user_dn), NESTED_RULE, esc(group_dn))
        conn.search(config.LDAP_BASE_DN, flt, attributes=["distinguishedName"], size_limit=1)
        return bool(conn.entries)
    return False


def _step(trace: Optional[List[Dict[str, Any]]], name: str, ok: bool, detail: str = "") -> None:
    if trace is not None:
        trace.append({"step": name, "ok": ok, "detail": detail})


def _auth(username: str, password: str, trace: Optional[List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    from ldap3.utils.conv import escape_filter_chars as esc
    username = (username or "").strip()
    if not enabled():
        _step(trace, "Konfiguration", False, "LDAP-URL und (Domain oder Bind-DN) müssen gesetzt sein")
        return None
    if not password or not _USER_RE.match(username):
        _step(trace, "Eingabe", False, "Benutzername/Passwort fehlen oder enthalten unzulässige Zeichen")
        return None
    attrs = ["sAMAccountName", "displayName", "memberOf", "distinguishedName", "userPrincipalName", "mail"]
    sam = username.split("@")[0]
    flt = config.LDAP_USER_FILTER.replace("{username}", esc(sam))
    if config.LDAP_BIND_DN:                                              # Modus A: suchen, dann als Benutzer binden
        conn = _open(config.LDAP_BIND_DN, config.LDAP_BIND_PASSWORD)
        if not conn:
            log.error("LDAP: Bind des Service-Accounts fehlgeschlagen")
            _step(trace, "Service-Account-Bind", False, _last_error)
            return None
        _step(trace, "Service-Account-Bind", True, config.LDAP_BIND_DN + (" @ " + _last_url if len(urls()) > 1 and _last_url else ""))
        conn.search(config.LDAP_BASE_DN, flt, attributes=attrs, size_limit=2)
        if len(conn.entries) != 1:
            conn.unbind()
            _step(trace, "Benutzer suchen", False, "%d Treffer für %s (erwartet: 1)" % (len(conn.entries), flt))
            return None
        _step(trace, "Benutzer suchen", True, conn.entries[0].entry_dn)
        user_conn = _open(conn.entries[0].entry_dn, password)
        if not user_conn:
            conn.unbind()
            _step(trace, "Passwort prüfen", False, _last_error)
            return None
        user_conn.unbind()
        _step(trace, "Passwort prüfen", True)
    else:                                                                # Modus B: UPN-Bind
        upn = username if "@" in username else "%s@%s" % (username, config.LDAP_DOMAIN)
        conn = _open(upn, password)
        if not conn:
            _step(trace, "Bind als %s" % upn, False, _last_error)
            return None
        _step(trace, "Bind als %s" % upn, True, "Server: " + _last_url if len(urls()) > 1 and _last_url else "")
        conn.search(config.LDAP_BASE_DN, flt, attributes=attrs, size_limit=2)
        if len(conn.entries) != 1:
            conn.unbind()
            _step(trace, "Benutzer suchen", False, "%d Treffer für %s (erwartet: 1)" % (len(conn.entries), flt))
            return None
        _step(trace, "Benutzer suchen", True, conn.entries[0].entry_dn)
    try:
        entry = conn.entries[0]
        g = lambda a: (entry[a].value if a in entry.entry_attributes else None)  # noqa: E731
        member_of = g("memberOf") or []
        member_of = [member_of] if isinstance(member_of, str) else list(member_of)
        if trace is not None:                                            # Hilfe beim Eintragen der Gruppen-DNs (nur im Verbindungstest)
            _step(trace, "Gruppen des Benutzers", True, "%d direkte Gruppen%s" % (len(member_of), (": " + " | ".join(sorted(member_of)[:25])) if member_of else ""))
        dn = entry.entry_dn
        if config.LDAP_REQUIRED_GROUP:
            ok = _is_member(conn, dn, member_of, config.LDAP_REQUIRED_GROUP)
            _step(trace, "Pflichtgruppe", ok, config.LDAP_REQUIRED_GROUP)
            if not ok:
                log.warning("LDAP: %s ist nicht Mitglied der erforderlichen Gruppe", username)
                return None
        admin = bool(config.LDAP_ADMIN_GROUP) and _is_member(conn, dn, member_of, config.LDAP_ADMIN_GROUP)
        if config.LDAP_ADMIN_GROUP:
            _step(trace, "Admin-Gruppe", True, "Mitglied: %s" % ("ja" if admin else "nein"))
        auditor = bool(config.LDAP_AUDITOR_GROUP) and _is_member(conn, dn, member_of, config.LDAP_AUDITOR_GROUP)
        if config.LDAP_AUDITOR_GROUP:
            _step(trace, "Betrachter-Gruppe", True, "Mitglied: %s" % ("ja" if auditor else "nein"))
        return {"username": str(g("sAMAccountName") or sam), "display": str(g("displayName") or ""), "email": str(g("mail") or ""), "admin": admin, "auditor": auditor}
    finally:
        conn.unbind()


def authenticate(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Ergebnis ``{"username", "display", "admin"}`` bei Erfolg, sonst ``None`` (falsch/nicht berechtigt/Fehler)."""
    return _auth(username, password, None)


def diagnose(username: str = "", password: str = "") -> Dict[str, Any]:
    """Verbindungstest für die Verwaltung: Schritt-für-Schritt-Protokoll. Ohne Benutzer nur Service-Account-Bind."""
    trace: List[Dict[str, Any]] = []
    if username and password:
        info = _auth(username, password, trace)
        return {"ok": info is not None, "steps": trace, "user": info}
    if not enabled():
        _step(trace, "Konfiguration", False, "LDAP-URL und (Domain oder Bind-DN) müssen gesetzt sein")
    elif config.LDAP_BIND_DN:
        conn = _open(config.LDAP_BIND_DN, config.LDAP_BIND_PASSWORD)
        _step(trace, "Service-Account-Bind", conn is not None, config.LDAP_BIND_DN if conn else _last_error)
        if conn:
            conn.unbind()
    else:
        _step(trace, "Konfiguration", True, "UPN-Bind: zum Testen Benutzername und Passwort eingeben")
    return {"ok": bool(trace) and all(s["ok"] for s in trace), "steps": trace, "user": None}
