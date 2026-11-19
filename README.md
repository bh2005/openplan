# OpenPlan

Projektplanung im Browser (PWA) – eine Open-Source-Alternative zu MS Project. FastAPI + SQLite im Backend, Vue 3 / TypeScript im Frontend, ein Docker-Image.

Oberfläche und Handbuch sind **zweisprachig (Deutsch / Englisch)**, jeder Benutzer wählt Sprache und **Hell/Dunkel** selbst (Kopfzeile, wird im Profil gespeichert).

## Funktionen
- **Planung:** Gantt (Tage/Wochen/Monate), Drag & Drop, Vorgangsstruktur (PSP) mit Sammelvorgängen, Abhängigkeiten FS/SS/FF/SF mit Verzug, kritischer Pfad, Constraints, Meilensteine, Status und Fortschritt, **Basisplan** mit Abweichungen, Rückgängig/Wiederholen, Live-Updates für mehrere Benutzer
- **Team:** Ressourcen, Auslastung (Überlastung rot), Teamplaner mit Umplanen per Ziehen, Kalenderansicht, **Arbeitspakete** zur Selbstübernahme (Pool), Kommentare mit @-Erwähnung, **Meine Aufgaben** (projektübergreifende To-do-Liste)
- **Geräte-Rollouts:** Vorlagen je Gerätetyp, **Geräteliste-Import** (Excel/CSV) mit Spaltenzuordnung, Vorschau, Location-Code und Datenbereinigung, Matrix „Geräte × Schritte“
- **Budget & Controlling** (EUR): Kostenstellen/-arten, Plan-/Ist-Kosten, CSV/SAP-Import, Earned-Value-Kennzahlen, Kostenverlauf
- **Zusammenarbeit:** Dokumente und OneDrive/SharePoint-Links an Vorgängen, Benachrichtigungen (Glocke und E-Mail), automatische Erinnerungen/Eskalation, Projekt- und Portfolio-/Kostenstellen-Reports
- **Zugriff:** Verantwortlicher je Projekt, Mitglieder (Editor/Leser), **Mitarbeiter** (ergibt sich aus der Zuordnung: eigene Vorgänge bearbeiten), „Betrachter (alle Projekte)“, Admin; Anmeldung lokal oder per **Active Directory (LDAP)**
- **Betrieb:** Server-Zertifikat per **ACME**, Backup/Restore, Audit-Log, Release Notes in der App, Hilfe-Panel (F1) und Handbuch
- **Import/Export:** MS-Project-XML (MSPDI), CSV, JSON
- **Beispielprojekte** (Projektliste → „Beispielprojekt anlegen“): Netzwerk-Rollout, Server-Migration auf ein neues Cluster, Transition eines Release-Wechsels

## Schnellstart
```bash
cp .env.example .env            # ADMIN_PASSWORD setzen (sonst Zufallspasswort im Log)
docker compose up -d --build
docker compose logs openplan | grep Admin
```
→ http://localhost:8083. Vor dem produktiven Einsatz einen TLS-Reverse-Proxy davorsetzen oder das Zertifikat per ACME in der Verwaltung ausstellen lassen; ein Betrieb mit HTTPS auf einer eigenen VM beschreibt `docker-compose.prod.yml`.

Wichtige Umgebungsvariablen (siehe `.env.example`): `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `JWT_SECRET`, `TOKEN_TTL_HOURS`, `PORT`, `LDAP_*`. Hinter einem Proxy mit TLS-Inspektion die interne CA unter `certs/` ablegen (siehe `certs/README.md`).

## Entwicklung
```bash
docker compose -f docker-compose.dev.yml up -d --build     # Frontend http://localhost:5173, Backend http://localhost:8765/docs
docker compose -f docker-compose.dev.yml exec backend python -m pytest      # Backend-Tests
cd frontend && npm install && npx vue-tsc --noEmit          # Typprüfung
cd e2e && npm install && npx playwright test                # Browser-Tests gegen den Dev-Stack
```
Architektur, Konventionen und Entscheidungen stehen in [`CLAUDE.md`](CLAUDE.md). Neue Oberflächentexte immer mit `$t(...)` bzw. `tr(...)` schreiben und in `frontend/src/locales/en.ts` ergänzen; Handbuchtexte in `content/help.ts` und `help.en.*.ts`.

Die CI (`.github/workflows/ci.yml`) führt Backend-Tests und Frontend-Typprüfung/-Build aus.

## Grenzen
Tagesgenaue Planung (keine Stundenplanung), keine automatische Ressourcenglättung, Last-Write-Wins bei gleichzeitiger Bearbeitung. Beim MS-Project-Import werden Constraints außer ASAP/SNET/MSO/FNLT zu ASAP, inaktive Vorgänge übersprungen.

Lizenz: MIT.
