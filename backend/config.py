import os
import re
import pathlib

import envfile

if os.environ.get("ENV_FILE"):            # .env aus der Verwaltung (siehe envfile.py): hat Vorrang vor der Compose-Umgebung
    envfile.load_into_environ(os.environ["ENV_FILE"])

DATA_DIR = pathlib.Path(os.environ.get("DATA_DIR", pathlib.Path(__file__).parent.parent / "data"))
DB_PATH = DATA_DIR / "openplan.db"
FILES_DIR = DATA_DIR / "files"
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "25"))
FRONTEND_DIST = pathlib.Path(os.environ.get(
    "FRONTEND_DIST", pathlib.Path(__file__).parent.parent / "frontend" / "dist"))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")  # leer -> Zufallspasswort, wird einmalig geloggt
TOKEN_TTL_HOURS = int(os.environ.get("TOKEN_TTL_HOURS", "12"))

# ── LDAP / Active Directory (optional; leer = nur lokale Benutzer) ──────────
LDAP_URL = os.environ.get("LDAP_URL", "")                         # z. B. ldaps://dc01.corp.example:636
LDAP_BASE_DN = os.environ.get("LDAP_BASE_DN", "")                 # Suchbasis, z. B. DC=corp,DC=example
LDAP_DOMAIN = os.environ.get("LDAP_DOMAIN", "")                   # UPN-Suffix, z. B. corp.example (Bind als user@domain)
LDAP_BIND_DN = os.environ.get("LDAP_BIND_DN", "")                 # optionaler Service-Account (statt UPN-Bind)
LDAP_BIND_PASSWORD = os.environ.get("LDAP_BIND_PASSWORD", "")
LDAP_USER_FILTER = os.environ.get("LDAP_USER_FILTER", "(&(objectClass=user)(sAMAccountName={username}))")
LDAP_CA_FILE = os.environ.get("LDAP_CA_FILE", "")                 # CA-Bundle für LDAPS (interne CA)
# Optionale Präfixe, die beim Geräteliste-Import vor dem Spaltennamen ignoriert werden (kommagetrennt, z. B. "inv_,asset_"); leer = aus
IMPORT_HEADER_PREFIXES = [re.sub(r"[\s*:_]", "", x).lower() for x in os.environ.get("IMPORT_HEADER_PREFIXES", "").split(",") if x.strip()]
LDAP_REQUIRED_GROUP = os.environ.get("LDAP_REQUIRED_GROUP", "")   # DN; nur Mitglieder dürfen sich anmelden
LDAP_ADMIN_GROUP = os.environ.get("LDAP_ADMIN_GROUP", "")         # DN; Mitglieder werden OpenPlan-Admin
LDAP_AUDITOR_GROUP = os.environ.get("LDAP_AUDITOR_GROUP", "")     # DN; Mitglieder sind „Betrachter alle Projekte“ (viewer + see_all)
LDAP_DEFAULT_ROLE = os.environ.get("LDAP_DEFAULT_ROLE", "editor")  # Rolle neu angelegter AD-Benutzer (editor|viewer)
LDAP_AUTO_CREATE = os.environ.get("LDAP_AUTO_CREATE", "1") not in ("0", "false", "no")
LDAP_NESTED_GROUPS = os.environ.get("LDAP_NESTED_GROUPS", "1") not in ("0", "false", "no")   # AD-Regel 1.2.840.113556.1.4.1941
