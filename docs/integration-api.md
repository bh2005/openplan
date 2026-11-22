# OpenPlan – Schnittstelle für Skripte und Fremdsysteme

Für Ansible/AWX, Checkmk, ServiceNow-Middleware und eigene Skripte. Alle Aufrufe gehen gegen die REST-API (`/api`, Swagger unter `/docs` auf dem Dev-Backend).

**Swagger:** `/docs` (alle Endpunkte nach Themen, „Try it out“), maschinenlesbar `/openapi.json`. Die Dateien liegen lokal unter `backend/vendor/swagger-ui` (kein CDN). `API_DOCS=1` (Standard, offen) | `admin` (nur angemeldete Administratoren) | `0` (aus, 404); Änderung in der `.env` wirkt nach Neustart. Tags und Kurzbeschreibungen pflegt `backend/apidocs.py`; `tests/test_apidocs.py` schlägt fehl, wenn ein neuer Endpunkt keinen Tag oder keine Beschreibung hat.

## 1. Zugang einrichten (Admin)

Verwaltung → **API-Zugänge** → Zugang anlegen: Name, Dienstkonto (wird angelegt), Umfang (`read` / `write`), optional Projekte, Laufzeit. Das Token `op_…` wird **nur einmal** angezeigt.

Danach das Dienstkonto im Projekt als **Mitglied** eintragen (Projekt → Mitglieder, Rolle Bearbeiter oder Leser) – ohne Mitgliedschaft sieht es das Projekt nicht.

```bash
curl -H "Authorization: Bearer op_…" https://openplan.example/api/projects
```

Grenzen: 120 Anfragen/Minute je Token (`API_TOKEN_RATE`), `read` erlaubt nur GET, ein Token kann nichts in der Verwaltung ändern und keine Projekte anlegen, wenn es auf Projekte beschränkt ist. Widerruf wirkt sofort.

## 2. Vorgänge finden

```bash
# Gerät samt Schritten per Hostname (Groß-/Kleinschreibung egal)
curl -H "Authorization: Bearer $T" "https://…/api/projects/7/lookup?hostname=sw-neu-01"
# Vorgang per externer Referenz (optional auf ein System begrenzt)
curl -H "Authorization: Bearer $T" "https://…/api/projects/7/lookup?ref=CHG0012345&system=servicenow"
```

Antwort: `{"items": [{"id", "name", "status", "percent", "device", "refs", "steps": [...]}]}` – `steps` nur bei Hostname-Suche.

## 3. Externe Referenzen

Je Vorgang und System (a–z, 0–9, `-`, `_`) genau eine Referenz mit optionalem Link. Wiederholtes `PUT` mit denselben Werten ändert nichts.

```bash
curl -X PUT  -H "Authorization: Bearer $T" -H "Content-Type: application/json" \
     -d '{"ref":"CHG0012345","url":"https://sn.example/chg/CHG0012345"}' https://…/api/tasks/412/refs/servicenow
curl -X DELETE -H "Authorization: Bearer $T" https://…/api/tasks/412/refs/servicenow
curl            -H "Authorization: Bearer $T" https://…/api/tasks/412/refs
```

Referenzen erscheinen im Vorgangsdialog („Externe Referenzen“), in `GET /projects/{pid}` (`tasks[].refs`) und in jedem Webhook-Payload.

## 4. Rückmeldung eines Fremdsystems

`POST /api/tasks/{tid}/events` setzt Status, Fortschritt, Notiz und optional eine Referenz in einem Schritt – nur für Teilvorgänge (keine Sammelvorgänge). Gleiche Daten ein zweites Mal senden ändert nichts (`"changed": false`, kein Webhook).

```bash
curl -X POST -H "Authorization: Bearer $T" -H "Content-Type: application/json" \
     -d '{"status":"done","note":"AWX-Job 4711 erfolgreich","system":"awx","ref":"4711","url":"https://awx.example/#/jobs/4711"}' \
     https://…/api/tasks/412/events
```

Erlaubte Systeme: `servicenow`, `awx`, `checkmk`, `jira`, `autopatch`, `portwerk`. Referenzen setzen darf nur ein Bearbeiter. Im Änderungsjournal steht „Rückmeldung (API)“ mit dem Dienstkonto.

## 5. Webhooks (ausgehend)

Verwaltung → **Webhooks**: Ziel-URL (https), Projekt (leer = alle), Ereignisse (leer = alle). Das Geheimnis `whsec_…` wird **nur einmal** angezeigt (erneuerbar). „Testen“ sendet ein `ping`.

| Ereignis | Wann |
|---|---|
| `task.status` | Status eines Teilvorgangs geändert (auch per Sammelvorgang/Mehrfachauswahl) |
| `task.blocked` | zusätzlich, wenn der neue Status „blockiert“ ist (Payload enthält die Status-Notiz) |
| `task.assigned` | Zuordnung geändert (`assigned`, `previous_assigned` = Ressourcennamen) |
| `device.created` | Gerät beim Import oder aus Vorlage neu angelegt (`steps` = Anzahl Schritte); Trockenläufe senden nichts |
| `ping` | nur Testknopf |

Payload (Beispiel):

```json
{"id": "evt_3f9a…", "event": "task.status", "ts": "2026-10-22T08:15:00Z", "actor": "svc-awx",
 "project": {"id": 7, "name": "Netzwerk-Rollout"},
 "task": {"id": 412, "name": "Konfiguration ausrollen", "status": "done", "percent": 100, "status_note": "",
          "device": {"id": 400, "hostname": "sw-neu-01", "standort": "Standort A", "typ": "Switch"},
          "refs": {"servicenow": "CHG0012345"}},
 "previous": {"status": "in_progress"}}
```

**`actor`** nennt den auslösenden Benutzer. Löst ein Dienstkonto per Rückmeldung (Abschnitt 4) selbst ein Ereignis aus, sollte der Empfänger Ereignisse mit seinem eigenen `actor` ignorieren, um Schleifen zu vermeiden.

Header: `X-OpenPlan-Event`, `X-OpenPlan-Delivery` (Zustell-ID), `X-OpenPlan-Timestamp` (Unix-Sekunden), `X-OpenPlan-Signature: sha256=<HMAC-SHA256(Geheimnis, roher Body)>`.

Signatur prüfen (Python):

```python
import hmac, hashlib, time
def valid(secret: str, body: bytes, headers) -> bool:
    mac = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    fresh = abs(time.time() - int(headers["X-OpenPlan-Timestamp"])) < 300      # Wiederholungen abwehren
    return fresh and hmac.compare_digest(mac, headers["X-OpenPlan-Signature"])
```

Zustellung: Antwort 2xx = erledigt, alles andere (auch Zeitüberschreitung nach 10 s) wird nach 1, 5, 30 und 120 Minuten wiederholt, danach „fehlgeschlagen“. Der Empfänger muss doppelte Zustellungen vertragen (`id` des Ereignisses ist gleich). Protokoll je Webhook unter „Protokoll“, Aufbewahrung 14 Tage. Weiterleitungen (3xx) werden nicht verfolgt.

### Zielregeln und Betrieb

- Nur `https://` (für Tests `WEBHOOK_ALLOW_HTTP=1`); keine Ziele auf Loopback, Link-Local (u. a. Cloud-Metadaten) oder nicht auflösbare Namen. Das Netz 10/8, 172.16/12, 192.168/16 ist erlaubt. Die Prüfung läuft beim Anlegen **und** bei jeder Zustellung.
- Optionale Positivliste: `WEBHOOK_ALLOWED_HOSTS=corp.example.com,awx.example` (Domains inkl. Subdomains).
- Der Container nutzt `HTTPS_PROXY`/`NO_PROXY` aus der Umgebung – interne Ziele gehören in `NO_PROXY` (auf dem Zielserver ist `.corp.example.com` bereits drin). TLS-Zertifikate des Ziels werden gegen `SSL_CERT_FILE` geprüft (Host-CA-Bundle mit Company-Ketten).
- Hintergrund-Thread abschalten: `WEBHOOK_WORKER=0` (z. B. in Tests).
- Hinweis zur Ausrollung: die handgepflegte Compose-Datei auf dem Zielserver braucht für diese Funktionen keine Änderung, die neuen Tabellen legt der Start automatisch an.

## 6. AutoPatch → OpenPlan (Patch-/CVE-Ergebnisse je Server)

AutoPatch meldet nach jedem Patch- und CVE-Job (auch dem automatischen CVE-Check nach dem Patchen) das Ergebnis je Server an
`POST /api/integrations/autopatch/results`. OpenPlan ordnet jeden Server einem **Gerät** des Projekts zu und setzt den passenden **Schritt**
(Teilvorgang unter dem Gerät).

**Einrichten**
1. OpenPlan: Verwaltung → API-Zugänge → Zugang (Umfang `write`, Rolle `editor`), Dienstkonto im Projekt als **Bearbeiter** eintragen.
2. AutoPatch: `OPENPLAN_TOKEN=op_…` in die `.env`, dann Einstellungen → **OpenPlan**: Adresse, optional Projekt-ID, „Verbindung testen“, einschalten.
3. Das Gerät braucht einen Schritt, dessen Name zur Job-Art passt (Standard: Patch-Job → `patch|update|aktualisier`, CVE-Job → `cve|schwachstell|vulnerab`;
   überschreibbar mit `step`). Passt kein oder mehr als ein Schritt, wird nichts gesetzt und die Antwort sagt warum.

**Zuordnung Server ↔ Gerät** (`match`): 1. gleicher Hostname (Groß-/Kleinschreibung egal), 2. gleicher Kurzname (`web01` ↔ `web01.corp.example`),
3. nur per DNS: ein Gerät, dessen Hostname zur gemeldeten IP auflöst (nur wenn AutoPatch die IP mitschickt). Mehrere Treffer → `ambiguous_device`, nichts passiert.

**DNS-Prüfung** (`dns`, Standard `verify`): Bei Treffer 1 und 2 wird zusätzlich geprüft, ob der Gerätename zur IP des gemeldeten Servers auflöst.
`mismatch` (gleicher Name, andere IP) → **nichts** wird gesetzt (`dns_conflict`), `unresolved` (Name nicht auflösbar) → wird mit Warnung übernommen.
`"dns": "off"` schaltet die Prüfung ab.

**Wirkung je Host:** `success` → Schritt erledigt (Notiz „Neustart nötig“, falls der Server einen Reboot meldet) · `failed` → blockiert mit Notiz
„AutoPatch-Job #N fehlgeschlagen: <letzte Fehlerzeile>“ · `running`/`pending` → in Arbeit (nur wenn der Schritt offen war) · `skipped` → unverändert.
Bereits **erledigte** Schritte werden nicht wieder geöffnet (`already_done`), damit monatliche Folgeläufe nichts durcheinanderbringen. Am Schritt wird die
Referenz `autopatch: job-<ID>` mit Link zu AutoPatch gesetzt; Webhooks (`task.status`) und das Änderungsjournal laufen wie bei jeder Änderung.

Antwort: `{"applied": n, "items": [{hostname, outcome, match, dns, device, project_id, task_id, step, message}]}`. Mögliche `outcome`-Werte: `applied`,
`unchanged`, `already_done`, `skipped`, `no_device`, `ambiguous_device`, `dns_conflict`, `no_step`, `ambiguous_step`. Ein leeres `results` ändert nichts und
prüft nur Token, Adresse und Projektzugriff (das nutzt der Testknopf).

Ein Fehler beim Melden beeinflusst den AutoPatch-Job nie; das Ergebnis der letzten Meldung steht in den AutoPatch-Einstellungen unter „OpenPlan“.
