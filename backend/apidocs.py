"""API-Dokumentation (Swagger UI) – lokal ausgeliefert, ohne CDN, abschaltbar.

``API_DOCS`` (Umgebungsvariable, wird bei jeder Anfrage gelesen):
  * ``1`` / leer  – Standard: ``/docs`` und ``/openapi.json`` für jeden erreichbar (die Endpunkte selbst brauchen weiter ein Token)
  * ``admin``     – ``/openapi.json`` nur mit Administrator-Anmeldung; die Seite ``/docs`` ist dann nur eine leere Hülle, die das Token der
                    OpenPlan-Sitzung (localStorage ``openplan.token``, gleiche Adresse) mitschickt
  * ``0``         – ``/docs``, ``/openapi.json`` und die Dateien liefern 404

Swagger UI liegt unter ``backend/vendor/swagger-ui`` (swagger-ui-dist 5.34.0, Apache-2.0). Die Seite lädt die OpenAPI-Beschreibung selbst
(``spec``-Objekt, keine ``?url=``-Parameter) und trägt die Sitzung bei „Try it out“ nur für Aufrufe an die eigene Adresse ein.

Tags und Kurzbeschreibungen stehen hier (``TAG_RULES``, ``SUMMARIES``), nicht an den Routen; ``tests/test_apidocs.py`` schlägt fehl, wenn ein
neuer Endpunkt keinen Tag oder keine Beschreibung bekommt.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth import current_user
from database import get_db

router = APIRouter()
VENDOR = Path(__file__).resolve().parent / "vendor" / "swagger-ui"
_opt_bearer = HTTPBearer(auto_error=False)
ASSETS = {"swagger-ui-bundle.js": "text/javascript", "swagger-ui.css": "text/css", "favicon-32x32.png": "image/png"}


def mode() -> str:
    v = os.environ.get("API_DOCS", "1").strip().lower()
    if v in ("0", "false", "no", "off", "aus"):
        return "off"
    return "admin" if v in ("admin", "admins") else "open"


def _off() -> HTTPException:
    return HTTPException(404, "Die API-Dokumentation ist auf diesem Server abgeschaltet (API_DOCS=0)")


# ── Tags und Beschreibungen ─────────────────────────────────────────────────────────────────
TAGS = [
    ("Anmeldung", "Login, eigenes Konto, Passwort und Profil."),
    ("Benutzer", "Benutzerverwaltung (Administratoren): Konten, Rollen, Sitzungen."),
    ("Projekte", "Projekte anlegen, ändern, exportieren/importieren, Mitglieder, Journal, Rückgängig/Wiederholen, Live-Updates."),
    ("Vorgänge", "Vorgänge und Phasen: anlegen, ändern, Status, Zuordnung, Arbeitspakete (Pool)."),
    ("Terminplanung", "Abhängigkeiten, Verschieben, Basisplan und Leveling (Überlast auflösen)."),
    ("Ressourcen & Abwesenheiten", "Ressourcen, Organigramm, Abwesenheiten je Projekt und persönliche Abwesenheiten."),
    ("Budget & Kosten", "Kostenstellen, Kostenarten, Plankosten, Ist-Kosten, Budgetzeilen und Auswertung."),
    ("Geräte & Vorlagen", "Rollout-Planung: Vorlagen je Gerätetyp, Geräteliste importieren, Rollen-Zuordnung."),
    ("Dokumente & Kommentare", "Dateien und Links an Vorgängen, Kommentare."),
    ("Berichte & Übersicht", "Dashboard, Übersicht „Wer arbeitet woran“, Projekt- und Portfolio-Reports."),
    ("Benachrichtigungen", "Glocke: Benachrichtigungen des Benutzers."),
    ("Feiertage", "Feiertage je Bundesland (Quelle api-feiertage.de)."),
    ("Integration", "Schnittstellen für Skripte und Fremdsysteme: externe Referenzen, Suche, Rückmeldungen, AutoPatch."),
    ("API-Zugänge", "Dienstkonten und API-Tokens (Administratoren)."),
    ("Webhooks", "Ausgehende Webhooks mit Signatur und Zustellprotokoll (Administratoren)."),
    ("Verwaltung", "Einstellungen und Betrieb (Administratoren): AD, Mail, Zertifikat, Reports, Backup, Erinnerungen, Server-Umgebung, Audit-Log."),
    ("System", "Health-Check."),
]

# Reihenfolge zählt: die erste passende Regel gewinnt (Pfad-Regex, optional nur für bestimmte Methoden)
TAG_RULES = [
    (r"^/health$", "System"),
    (r"^/api/auth", "Anmeldung"),
    (r"^/api/admin/tokens", "API-Zugänge"),
    (r"^/api/admin/webhooks", "Webhooks"),
    (r"^/api/integrations|^/api/tasks/\{tid\}/(refs|events)|/lookup$", "Integration"),
    (r"^/api/admin", "Verwaltung"),
    (r"^/api/users", "Benutzer"),
    (r"^/api/notifications", "Benachrichtigungen"),
    (r"^/api/holidays", "Feiertage"),
    (r"/finance|/budget|/cost-|/actuals", "Budget & Kosten"),
    (r"/devices|/templates|/role-map", "Geräte & Vorlagen"),
    (r"/files|/links|/comments", "Dokumente & Kommentare"),
    (r"/resources|/absences|/reports-to|^/api/me/absences", "Ressourcen & Abwesenheiten"),
    (r"/leveling|/baseline|/predecessors|/shift$|/move$", "Terminplanung"),
    (r"/report|^/api/reports|^/api/dashboard|^/api/overview", "Berichte & Übersicht"),
    (r"^/api/my-tasks|^/api/tasks|/tasks", "Vorgänge"),
    (r"^/api/projects", "Projekte"),
]


def tag_of(path: str) -> Optional[str]:
    for rx, tag in TAG_RULES:
        if re.search(rx, path):
            return tag
    return None


SUMMARIES: Dict[str, str] = {
    "GET /health": "Health-Check (für Docker und Monitoring)",
    "POST /api/auth/login": "Anmelden und Token erhalten",
    "GET /api/auth/me": "Angemeldeten Benutzer abrufen",
    "POST /api/auth/password": "Eigenes Passwort ändern",
    "PUT /api/auth/profile": "Eigenes Profil ändern (E-Mail, Benachrichtigung, Sprache, Design)",
    "GET /api/users": "Alle Benutzer auflisten (Admin)",
    "POST /api/users": "Benutzer anlegen (Admin)",
    "GET /api/users/directory": "Benutzer suchen (schlanke Liste für Auswahlfelder)",
    "PUT /api/users/{uid}/email": "E-Mail-Adresse eines Benutzers setzen (Admin)",
    "PUT /api/users/{uid}/display-name": "Anzeigenamen eines lokalen Benutzers setzen (Admin)",
    "PUT /api/users/{uid}/password": "Passwort eines lokalen Benutzers zurücksetzen (Admin)",
    "POST /api/users/{uid}/logout": "Alle Sitzungen eines Benutzers beenden (Admin)",
    "PUT /api/users/{uid}/role": "Rolle eines Benutzers ändern (Admin)",
    "PUT /api/users/{uid}/see-all": "„Betrachter alle Projekte“ ein-/ausschalten (Admin)",
    "DELETE /api/users/{uid}": "Benutzer löschen (Admin)",
    "GET /api/my-tasks": "Meine Aufgaben: offene Vorgänge des Benutzers",
    "GET /api/notifications": "Benachrichtigungen abrufen",
    "POST /api/notifications/read-all": "Alle Benachrichtigungen als gelesen markieren",
    "POST /api/notifications/{nid}/read": "Eine Benachrichtigung als gelesen markieren",
    "GET /api/projects": "Projekte auflisten (nur die, auf die der Benutzer Zugriff hat)",
    "POST /api/projects": "Projekt anlegen",
    "POST /api/projects/wizard": "Projekt mit dem Assistenten anlegen (Art, Team, Report)",
    "POST /api/projects/demo": "Beispielprojekt anlegen",
    "POST /api/projects/import": "Projekt importieren (JSON oder MS-Project-XML)",
    "GET /api/projects/{pid}": "Projekt mit allen Vorgängen, Abhängigkeiten, Ressourcen und Terminen laden",
    "PATCH /api/projects/{pid}": "Projekteinstellungen ändern (Name, Start, Arbeitstage, Verantwortlicher, Report)",
    "DELETE /api/projects/{pid}": "Projekt löschen",
    "GET /api/projects/{pid}/revision": "Aktuelle Revisionsnummer des Projekts",
    "GET /api/projects/{pid}/events": "Live-Updates des Projekts (Server-Sent Events)",
    "PUT /api/projects/{pid}/members": "Projektmitglieder setzen (Editor/Leser)",
    "GET /api/projects/{pid}/journal": "Änderungsjournal des Projekts",
    "GET /api/projects/{pid}/export": "Projekt exportieren (JSON, XML, CSV)",
    "POST /api/projects/{pid}/undo": "Letzte Änderung rückgängig machen",
    "POST /api/projects/{pid}/redo": "Rückgängig gemachte Änderung wiederholen",
    "POST /api/projects/{pid}/baseline": "Basisplan setzen",
    "DELETE /api/projects/{pid}/baseline": "Basisplan löschen",
    "POST /api/projects/{pid}/tasks": "Vorgang anlegen",
    "POST /api/projects/{pid}/tasks/status": "Status mehrerer Vorgänge setzen",
    "PATCH /api/tasks/{tid}": "Vorgang ändern (Name, Dauer, Status, Fortschritt, Frist, Einschränkung …)",
    "DELETE /api/tasks/{tid}": "Vorgang löschen (samt Teilvorgängen)",
    "POST /api/tasks/{tid}/move": "Vorgang in der Struktur verschieben (neuer Elternvorgang, Position)",
    "POST /api/tasks/{tid}/shift": "Vorgang oder Phase um Kalendertage verschieben",
    "PUT /api/tasks/{tid}/predecessors": "Vorgänger und Verknüpfungsarten setzen (FS/SS/FF/SF mit Wartezeit)",
    "PUT /api/tasks/{tid}/assignments": "Zuordnung zu Ressourcen oder Benutzern setzen",
    "POST /api/tasks/{tid}/claim": "Arbeitspaket aus dem Pool selbst übernehmen",
    "POST /api/tasks/{tid}/release": "Übernommenes Arbeitspaket zurück in den Pool geben",
    "GET /api/projects/{pid}/leveling": "Leveling-Vorschlag: Überlast innerhalb des freien Puffers auflösen",
    "POST /api/projects/{pid}/leveling/apply": "Leveling-Vorschlag übernehmen",
    "POST /api/projects/{pid}/resources": "Ressource anlegen",
    "PUT /api/resources/{rid}": "Ressource ändern",
    "DELETE /api/resources/{rid}": "Ressource löschen",
    "PUT /api/resources/{rid}/reports-to": "Organigramm: Ressource einer anderen unterstellen",
    "POST /api/projects/{pid}/absences": "Abwesenheit einer Ressource anlegen",
    "PUT /api/absences/{aid}": "Abwesenheit ändern",
    "DELETE /api/absences/{aid}": "Abwesenheit löschen",
    "GET /api/me/absences": "Meine persönlichen Abwesenheiten (gelten in allen Projekten)",
    "POST /api/me/absences": "Persönliche Abwesenheit anlegen",
    "PUT /api/me/absences/{aid}": "Persönliche Abwesenheit ändern",
    "DELETE /api/me/absences/{aid}": "Persönliche Abwesenheit löschen",
    "GET /api/projects/{pid}/finance": "Kosten-Stammdaten und Plankosten des Projekts",
    "PUT /api/projects/{pid}/finance/settings": "Kosten-Sichtbarkeit für Mitglieder einstellen",
    "GET /api/projects/{pid}/budget": "Budgetauswertung (Plan, Ist, Prognose) zum Stichtag",
    "GET /api/projects/{pid}/budget/export": "Budgetauswertung exportieren",
    "POST /api/projects/{pid}/cost-centers": "Kostenstelle anlegen",
    "PUT /api/cost-centers/{rid}": "Kostenstelle ändern",
    "DELETE /api/cost-centers/{rid}": "Kostenstelle löschen",
    "POST /api/projects/{pid}/cost-centers/import": "Kostenstellen aus Text importieren (Code;Name)",
    "POST /api/projects/{pid}/cost-types": "Kostenart anlegen",
    "PUT /api/cost-types/{rid}": "Kostenart ändern",
    "DELETE /api/cost-types/{rid}": "Kostenart löschen",
    "POST /api/projects/{pid}/cost-types/import": "Kostenarten aus Text importieren (Code;Name)",
    "POST /api/tasks/{tid}/cost-items": "Plankosten an einem Vorgang anlegen",
    "PUT /api/cost-items/{iid}": "Plankosten ändern",
    "DELETE /api/cost-items/{iid}": "Plankosten löschen",
    "PUT /api/projects/{pid}/budget-lines": "Budgetzeilen setzen (Gesamtbudget und je Kostenstelle/-art)",
    "GET /api/projects/{pid}/actuals": "Ist-Kosten auflisten",
    "POST /api/projects/{pid}/actuals": "Ist-Kosten buchen",
    "PUT /api/actuals/{aid}": "Ist-Kosten ändern",
    "DELETE /api/actuals/{aid}": "Ist-Kosten löschen",
    "POST /api/projects/{pid}/actuals/import": "Ist-Kosten per CSV/SAP-Export importieren (mit Vorschau)",
    "GET /api/templates": "Vorlagen je Gerätetyp auflisten",
    "POST /api/templates": "Vorlage anlegen",
    "GET /api/templates/sample.xlsx": "Muster-Geräteliste als Excel herunterladen",
    "PUT /api/templates/{tid}": "Vorlage ändern",
    "DELETE /api/templates/{tid}": "Vorlage löschen",
    "GET /api/projects/{pid}/role-map": "Zuordnung Vorlagen-Rolle → Ressource lesen",
    "PUT /api/projects/{pid}/role-map": "Zuordnung Vorlagen-Rolle → Ressource setzen",
    "POST /api/projects/{pid}/devices/parse": "Geräteliste (Excel/CSV) einlesen und Spalten vorschlagen",
    "POST /api/projects/{pid}/devices/import": "Geräteliste importieren (Trockenlauf oder echt)",
    "POST /api/projects/{pid}/devices": "Einzelnes Gerät aus einer Vorlage anlegen",
    "GET /api/tasks/{tid}/files": "Dokumente und Links eines Vorgangs auflisten",
    "POST /api/tasks/{tid}/files": "Dokumente an einen Vorgang hochladen",
    "POST /api/tasks/{tid}/links": "Link (z. B. OneDrive) an einen Vorgang hängen",
    "GET /api/files/{fid}/download": "Dokument herunterladen",
    "DELETE /api/files/{fid}": "Dokument oder Link löschen",
    "GET /api/tasks/{tid}/comments": "Kommentare eines Vorgangs auflisten",
    "POST /api/tasks/{tid}/comments": "Kommentar schreiben (mit @-Erwähnung)",
    "DELETE /api/comments/{cid}": "Kommentar löschen",
    "GET /api/dashboard": "Management-Dashboard: Ampel, Termine, Risiken, Auslastung, Kosten",
    "GET /api/overview/people": "Übersicht „Wer arbeitet woran“ (Personen × Projekte)",
    "GET /api/projects/{pid}/report/preview": "Projektreport als Vorschau",
    "POST /api/projects/{pid}/report/send": "Projektreport jetzt per E-Mail versenden",
    "GET /api/reports/mine": "Meine abonnierten übergreifenden Reports",
    "GET /api/reports/{sid}": "Übergreifenden Report anzeigen",
    "GET /api/holidays/states": "Bundesländer für den Feiertagsimport",
    "GET /api/holidays": "Feiertage eines Bundeslandes für ein oder mehrere Jahre",
    "GET /api/tasks/{tid}/refs": "Externe Referenzen eines Vorgangs auflisten",
    "PUT /api/tasks/{tid}/refs/{system}": "Externe Referenz setzen (z. B. ServiceNow-Change); idempotent",
    "DELETE /api/tasks/{tid}/refs/{system}": "Externe Referenz entfernen",
    "GET /api/projects/{pid}/lookup": "Vorgänge per Hostname oder externer Referenz finden",
    "POST /api/tasks/{tid}/events": "Rückmeldung eines Fremdsystems: Status, Fortschritt, Notiz, Referenz; idempotent",
    "POST /api/integrations/autopatch/results": "Job-Ergebnis von AutoPatch je Server übernehmen (Zuordnung per Hostname/DNS)",
    "GET /api/admin/tokens": "API-Tokens auflisten (Admin)",
    "POST /api/admin/tokens": "API-Token mit Dienstkonto anlegen; Klartext nur einmal (Admin)",
    "DELETE /api/admin/tokens/{tid}": "API-Token widerrufen (Admin)",
    "GET /api/admin/webhooks": "Webhooks auflisten (Admin)",
    "POST /api/admin/webhooks": "Webhook anlegen; Geheimnis nur einmal (Admin)",
    "PUT /api/admin/webhooks/{wid}": "Webhook ändern, optional neues Geheimnis (Admin)",
    "DELETE /api/admin/webhooks/{wid}": "Webhook samt Zustellungen löschen (Admin)",
    "GET /api/admin/webhooks/{wid}/deliveries": "Zustellprotokoll eines Webhooks (Admin)",
    "POST /api/admin/webhooks/{wid}/test": "Ping an einen Webhook senden und Ergebnis melden (Admin)",
    "GET /api/admin/settings/ldap": "AD-/LDAP-Einstellungen lesen (Admin)",
    "PUT /api/admin/settings/ldap": "AD-/LDAP-Einstellungen speichern (Admin)",
    "POST /api/admin/settings/ldap/test": "AD-Verbindung testen, optional mit Benutzeranmeldung (Admin)",
    "GET /api/admin/tls": "Server-Zertifikat (ACME): Einstellungen und Status (Admin)",
    "PUT /api/admin/tls": "Server-Zertifikat (ACME): Einstellungen speichern (Admin)",
    "POST /api/admin/tls/fetch-ca": "CA-Kette von einer URL abrufen und prüfen (Admin)",
    "POST /api/admin/tls/issue": "Zertifikat jetzt anfordern oder erneuern (Admin)",
    "GET /api/admin/tls/cert": "Öffentliche Zertifikatskette herunterladen (Admin)",
    "GET /api/admin/settings/mail": "E-Mail-Einstellungen lesen (Admin)",
    "PUT /api/admin/settings/mail": "E-Mail-Einstellungen speichern (Admin)",
    "POST /api/admin/settings/mail/test": "Testmail senden (Admin)",
    "GET /api/admin/reports": "Übergreifende Reports und Kostenstellen-Verantwortliche (Admin)",
    "POST /api/admin/reports": "Übergreifenden Report anlegen (Admin)",
    "PUT /api/admin/reports/{sid}": "Übergreifenden Report ändern (Admin)",
    "DELETE /api/admin/reports/{sid}": "Übergreifenden Report löschen (Admin)",
    "POST /api/admin/reports/{sid}/send": "Übergreifenden Report jetzt senden (Admin)",
    "PUT /api/admin/cost-owners": "Kostenstellen-Verantwortliche setzen (Admin)",
    "GET /api/admin/audit": "Audit-Log durchsuchen (Admin)",
    "GET /api/admin/audit/export": "Audit-Log als CSV exportieren (Admin)",
    "GET /api/admin/backup": "Datensicherung: Einstellungen und vorhandene Sicherungen (Admin)",
    "PUT /api/admin/backup": "Datensicherung: Einstellungen speichern (Admin)",
    "POST /api/admin/backup": "Datensicherung jetzt erstellen (Admin)",
    "POST /api/admin/backup/{name}/verify": "Sicherung auf Lesbarkeit prüfen (Admin)",
    "GET /api/admin/backup/{name}/download": "Sicherung herunterladen (Admin)",
    "DELETE /api/admin/backup/{name}": "Sicherung löschen (Admin)",
    "GET /api/admin/settings/reminders": "Erinnerungen: Einstellungen lesen (Admin)",
    "PUT /api/admin/settings/reminders": "Erinnerungen: Einstellungen speichern (Admin)",
    "POST /api/admin/reminders/run": "Erinnerungsprüfung jetzt ausführen (Admin)",
    "GET /api/admin/settings/holidays": "Feiertags-API: Einstellung lesen (Admin)",
    "PUT /api/admin/settings/holidays": "Feiertags-API: URL speichern (Admin)",
    "DELETE /api/admin/settings/holidays/cache": "Feiertags-Zwischenspeicher leeren (Admin)",
    "POST /api/admin/settings/holidays/test": "Feiertags-API testen (Admin)",
    "GET /api/admin/env": "Server-Umgebung (.env) lesen; Geheimnisse maskiert (Admin)",
    "PUT /api/admin/env": "Server-Umgebung (.env) speichern (Admin)",
    "POST /api/admin/restart": "Container neu starten (Admin)",
}

INTRO = """REST-API von OpenPlan. Alle Pfade unter `/api` verlangen ein Token im Header `Authorization: Bearer <Token>`:

* **Benutzer:** `POST /api/auth/login` liefert ein Token (12 Stunden gültig).
* **Skripte und Fremdsysteme:** API-Token (`op_…`) eines Dienstkontos, anlegbar unter Verwaltung → API-Zugänge. Ein Token mit Umfang *read* darf nur lesen; ein auf Projekte beschränktes Token sieht nur diese.

Über **Authorize** kann ein Token eingetragen werden. Wurde diese Seite aus einer angemeldeten OpenPlan-Sitzung geöffnet, nutzt „Try it out“ diese Anmeldung automatisch – Änderungen sind echt.

Fehler kommen als `{"detail": "…"}` (401 nicht angemeldet, 403 keine Berechtigung, 404 nicht gefunden oder nicht sichtbar, 422 ungültige Eingabe, 429 zu viele Anfragen). Ausführliche Anleitung für Integrationen: `docs/integration-api.md` im Repository."""


def openapi_for(app) -> Dict[str, Any]:
    """OpenAPI-Beschreibung mit deutschen Tags und Kurzbeschreibungen (einmal erzeugt, dann zwischengespeichert)."""
    if getattr(app, "_openplan_openapi", None):
        return app._openplan_openapi
    from fastapi.openapi.utils import get_openapi
    spec = get_openapi(title=app.title, version=app.version, description=INTRO, routes=app.routes, tags=[{"name": n, "description": d} for n, d in TAGS])
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            tag = tag_of(path)
            if tag:
                op["tags"] = [tag]
            summary = SUMMARIES.get("%s %s" % (method.upper(), path))
            if summary:
                op["summary"] = summary
    app._openplan_openapi = spec
    return spec


# ── Routen ───────────────────────────────────────────────────────────────────────────────────────
def _docs_access(request: Request, cred: Optional[HTTPAuthorizationCredentials] = Depends(_opt_bearer), db=Depends(get_db, scope="function")):
    m = mode()
    if m == "off":
        raise _off()
    if m == "admin":
        user = current_user(request, cred, db)
        if user["role"] != "admin":
            raise HTTPException(403, "Die API-Dokumentation ist nur für Administratoren sichtbar")
    return None


@router.get("/openapi.json", include_in_schema=False)
def openapi_json(request: Request, _=Depends(_docs_access)):
    return JSONResponse(openapi_for(request.app))


PAGE = """<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenPlan – API</title>
<link rel="icon" href="/docs-assets/favicon-32x32.png"><link rel="stylesheet" href="/docs-assets/swagger-ui.css">
<style>body{margin:0;font-family:system-ui,sans-serif}#msg{display:none;margin:0;padding:10px 20px;background:#fff7e6;border-bottom:1px solid #f0c36d;color:#5c4400;font-size:14px}</style>
</head><body><p id="msg"></p><div id="ui"></div>
<script src="/docs-assets/swagger-ui-bundle.js"></script><script src="/docs-assets/openplan-docs.js"></script></body></html>"""

PAGE_JS = """(function () {
  var tok = null
  try { tok = localStorage.getItem('openplan.token') } catch (e) { /* kein Zugriff */ }
  var msg = document.getElementById('msg')
  function show(t) { msg.textContent = t; msg.style.display = 'block' }
  fetch('/openapi.json', { headers: tok ? { Authorization: 'Bearer ' + tok } : {}, cache: 'no-store' })
    .then(function (r) {
      if (r.status === 401 || r.status === 403) throw new Error('Die API-Dokumentation ist nur für angemeldete Administratoren sichtbar. Bitte in OpenPlan als Administrator anmelden und diese Seite neu laden.')
      if (r.status === 404) throw new Error('Die API-Dokumentation ist auf diesem Server abgeschaltet (API_DOCS=0).')
      if (!r.ok) throw new Error('Die OpenAPI-Beschreibung konnte nicht geladen werden (HTTP ' + r.status + ').')
      return r.json()
    })
    .then(function (spec) {
      if (tok) show('Angemeldet über die OpenPlan-Sitzung: „Try it out“ führt Aufrufe mit Ihrem Benutzer aus – Änderungen sind echt.')
      window.ui = SwaggerUIBundle({
        spec: spec, dom_id: '#ui', deepLinking: true, docExpansion: 'none', filter: true, persistAuthorization: false, queryConfigEnabled: false,
        requestInterceptor: function (req) {
          if (tok && req.url.indexOf(location.origin) === 0 && !req.headers.Authorization) req.headers.Authorization = 'Bearer ' + tok
          return req
        }
      })
    })
    .catch(function (e) { show(e.message) })
})()
"""


@router.get("/docs", include_in_schema=False)
def docs_page():
    if mode() == "off":
        raise _off()
    return HTMLResponse(PAGE, headers={"Cache-Control": "no-cache"})


@router.get("/docs-assets/{name}", include_in_schema=False)
def docs_asset(name: str):
    if mode() == "off":
        raise _off()
    if name == "openplan-docs.js":
        return Response(PAGE_JS, media_type="text/javascript", headers={"Cache-Control": "no-cache"})
    if name in ASSETS and (VENDOR / name).is_file():
        return FileResponse(VENDOR / name, media_type=ASSETS[name], headers={"Cache-Control": "public, max-age=86400"})
    raise HTTPException(404, "Nicht gefunden")
