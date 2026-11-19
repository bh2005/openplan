# Entwurf: API-Tokens und Webhooks (Stand 2026-10-22, v0.12.0)

Ziel: Externe Systeme (Ansible/AWX, Checkmk, ServiceNow, Skripte) können OpenPlan lesen und schreiben und werden bei Ereignissen benachrichtigt. **Stand 2026-10-22:** Abschnitte 1–4 sind umgesetzt (API-Tokens, externe Referenzen, Webhooks, Rückkanal; 174 Tests grün). Offen: `project.deadline_missed`-Ereignis, Beispielintegration (Checkmk/AWX), ServiceNow-Mapping. Nutzeranleitung: `integration-api.md`. Der Text darunter ist der ursprüngliche Entwurf.

## Ausgangslage im Code

- **Auth** (`backend/auth.py`): nur JWT (HS256) für Benutzer, `current_user` lädt die Zeile aus `users` und prüft `token_version`. Rollen `admin/editor/viewer`, Projektrechte über `access.proj("view"|"edit"|"owner")`. Es gibt **keine** Dienstkonten und keine langlebigen Tokens (TTL 12 h).
- **Ereignisse**: `service.log()` schreibt jede Änderung ins `journal` (Aktion, Detail, `task_id`). Der SSE-Stream `/projects/{pid}/events` pollt nur `projects.revision`, er liefert keine Inhalte.
- **Hintergrund-Threads**: Muster `start_background()` in `reminders.py`/`reports.py`/`backup.py` (daemon-Thread, eigene DB-Verbindung).
- **Audit** (`backend/audit.py`): `audit.log(db, user, action, detail, ip)` für Verwaltungsaktionen.
- **Geräte** sind Sammelvorgänge (Gerät) mit Kind-Vorgängen (Schritte); Hostname steht im Namen, übrige Attribute im Notizfeld (`devices.py`, `NOTE_MARK`). Es gibt kein eigenes Feld für externe Kennungen.

## 1. API-Tokens (Dienstkonten)

**Prinzip:** Ein Token gehört zu einem Dienstkonto (Eintrag in `users`, `auth_source='service'`, kein Passwort-Login). Dadurch greifen Rollen, `access.proj(...)` und Audit unverändert.

Tabelle:

```sql
CREATE TABLE IF NOT EXISTS api_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,                 -- z. B. "awx-rollout"
    token_hash TEXT NOT NULL UNIQUE,    -- SHA-256 des Klartext-Tokens
    prefix TEXT NOT NULL,               -- erste 8 Zeichen, nur zur Anzeige
    scope TEXT NOT NULL DEFAULT 'read', -- 'read' | 'write'
    project_ids TEXT NOT NULL DEFAULT '',-- leer = alle Projekte, die das Konto sehen darf
    expires_at TEXT,                    -- NULL = unbegrenzt (nicht empfohlen)
    last_used_at TEXT,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

- Format `op_<random 40 Zeichen>`; Klartext wird **einmalig** beim Anlegen angezeigt, gespeichert nur der Hash.
- `current_user` erkennt das Präfix `op_`, schlägt den Hash nach, prüft Ablauf und liefert den Benutzer des Dienstkontos. Scope `read` sperrt alle schreibenden Methoden (zusätzliche Prüfung in `require_editor`/`access.proj("edit")`).
- Verwaltung unter Admin → „API-Zugänge“: anlegen, widerrufen, Ablauf, letzte Nutzung. Jede Aktion in `audit.log` (`token.create`, `token.revoke`; Nutzung nur als `last_used_at`, nicht pro Aufruf).
- Rate-Limit je Token (einfacher Zähler im Speicher, z. B. 120 Anfragen/Minute).
- Tests: Token gültig/abgelaufen/widerrufen, read darf nicht schreiben, Projektbeschränkung, Hash nie in Antworten/Logs.

## 2. Externe Referenzen

Damit Zuordnungen stabil sind (z. B. ServiceNow-Change, AWX-Job):

```sql
CREATE TABLE IF NOT EXISTS external_refs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    system TEXT NOT NULL,       -- 'servicenow' | 'awx' | 'checkmk' | frei
    ref TEXT NOT NULL,          -- z. B. CHG0012345
    url TEXT NOT NULL DEFAULT '',
    UNIQUE (task_id, system)
);
```

- `GET/PUT/DELETE /api/tasks/{tid}/refs/{system}`; in der Aufgaben-Detailansicht als Link-Liste.
- Suche nach Referenz: `GET /api/projects/{pid}/tasks?ref=servicenow:CHG0012345` und nach Hostname, damit Skripte ohne interne IDs arbeiten können.
- Idempotenz: `PUT` ersetzt, doppelte Aufrufe schaden nicht.

## 3. Ausgehende Webhooks

Tabellen:

```sql
CREATE TABLE IF NOT EXISTS webhooks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    secret TEXT NOT NULL,                 -- für HMAC, in der UI maskiert
    events TEXT NOT NULL DEFAULT '*',     -- Komma-Liste, z. B. task.status,task.blocked
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,  -- NULL = alle
    enabled INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    webhook_id INTEGER NOT NULL REFERENCES webhooks(id) ON DELETE CASCADE,
    event TEXT NOT NULL,
    payload TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    next_try TEXT NOT NULL DEFAULT (datetime('now')),
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | ok | failed
    last_code INTEGER, last_error TEXT NOT NULL DEFAULT '',
    ts TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Auslösung:** Zentral in `service.log()` bzw. an den Stellen mit Statuswechsel (`api.py` um Zeile 821/876). Dort wird nach dem Schreiben des Journals ein Eintrag in `webhook_deliveries` angelegt (selbe Transaktion, damit bei Rollback nichts gesendet wird). Ein Hintergrund-Thread (`webhooks.start_background()`, Muster `reminders.py`) liefert aus und wiederholt bei Fehlern.

**Ereignisse (Start):**

| Event | Wann |
|---|---|
| `task.status` | Status eines Vorgangs geändert (open/in_progress/blocked/done) |
| `task.blocked` | Spezialfall mit `status_note` |
| `task.assigned` | Zuteilung geändert |
| `device.created` | Gerät aus Vorlage/Import angelegt |
| `project.deadline_missed` | aus `reminders.py` |

**Payload (JSON):**

```json
{"id": "evt_…", "event": "task.status", "ts": "2026-10-22T08:15:00Z",
 "project": {"id": 7, "name": "Netzwerk-Rollout"},
 "task": {"id": 412, "name": "Konfiguration ausrollen", "status": "done", "percent": 100,
          "device": {"hostname": "sw-neu-01", "standort": "Standort A", "typ": "Switch"},
          "refs": {"servicenow": "CHG0012345"}},
 "actor": "jdoe", "previous": {"status": "in_progress"}}
```

**Sicherheit:**
- Signatur `X-OpenPlan-Signature: sha256=<HMAC(secret, body)>` plus `X-OpenPlan-Event`, `X-OpenPlan-Delivery`.
- Ziel-URL nur `https://`; Zielliste (Allowlist) in der Verwaltung, um SSRF zu begrenzen (keine Zugriffe auf Link-Local/Metadaten-Adressen, Weiterleitungen nicht folgen).
- Timeout 10 s, bis zu 5 Wiederholungen mit steigendem Abstand, danach `failed`; Aufbewahrung der Zustellungen 14 Tage.
- Secrets nur über die gleiche Maskierung wie im `.env`-Editor anzeigen, im Audit nur Namen.
- Zustellung nur für Projekte, auf die der Ersteller des Webhooks Zugriff hat.

## 4. Rückkanal (eingehend)

Externe Systeme nutzen die vorhandene REST-API mit Token, statt eine eigene Schnittstelle zu bekommen:

- `PATCH` auf Vorgang (Status, Prozent, Notiz, `status_note`) – gibt es bereits.
- Neu: `POST /api/tasks/{tid}/events` mit `{"status": "done", "note": "AWX-Job 4711 erfolgreich", "url": "…"}` als schmale, idempotente Schnittstelle für Callbacks (verhindert, dass Automatisierung beliebige Felder überschreibt; setzt Status und hängt Notiz/Link an, Journal-Eintrag mit Dienstkonto).

## 5. Reihenfolge und Aufwand (grobe Schätzung)

1. API-Tokens + Verwaltung + Tests: ca. 1 Tag.
2. Externe Referenzen + Suche: ca. 0,5 Tag.
3. Webhooks (Tabellen, Auslöser, Zusteller, UI, Tests): ca. 1,5 Tage.
4. Rückkanal `/events`: ca. 0,5 Tag.
5. Beispielintegration mit Checkmk (Downtime bei Schrittbeginn) oder AWX als Referenz: ca. 1 Tag.

## Offene Entscheidungen

- Sollen Tokens an Projekte gebunden werden können (empfohlen: ja) oder nur an das Konto?
- Welche Zielsysteme sind erlaubt (Allowlist per Umgebung oder per UI)?
- Soll Ansible/AWX von OpenPlan aus **ausgelöst** werden (OpenPlan ruft AWX) oder nur **Webhooks** an eine Middleware senden? Auslösen ist mächtiger, aber sicherheitskritisch (nur freigegebene Job-Templates, eigene Rolle).
- ServiceNow: Eigenes Mapping-Modul oder zunächst nur Webhook + Skript auf ServiceNow-Seite?
- Hinweis zur Bereitstellung: Die VM-Compose auf dem Zielserver ist handgepflegt; neue Umgebungsvariablen (z. B. Webhook-Allowlist) dort manuell ergänzen.
