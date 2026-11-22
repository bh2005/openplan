/** Einzige Quelle für die Release Notes (Verwaltung → Release Notes). Neueste Version zuerst; bei jeder Änderung hier ergänzen. */
export type ChangeKind = 'neu' | 'verbessert' | 'behoben'
export interface Release { version: string; date: string; title: string; changes: { kind: ChangeKind; text: string }[] }

export const releases: Release[] = [
  {
    version: '0.14.0', date: '2026-11-23', title: 'Anbindung Portwerk',
    changes: [
      { kind: 'neu', text: 'Projektart „Einbau Patchfelder / Verkabelung“ im Assistenten „Neues Projekt“: Planung, Montage, Verlegen und Auflegen, Messung, Abschnitt „Patchaufträge (aus Portwerk)“ und Abnahme. Portwerk legt Projekte dieser Art über die API an und hängt seine Patchaufträge unter den Abschnitt.' },
      { kind: 'neu', text: 'Externe Referenz „portwerk“: Rückmeldungen (POST /api/tasks/{id}/events) dürfen die Referenz portwerk: PA-… mit Link setzen; im Vorgang ist „portwerk“ als System auswählbar.' },
    ],
  },
  {
    version: '0.13.0', date: '2026-11-02', title: 'Board (Kanban)',
    changes: [
      { kind: 'neu', text: 'Neuer Tab „Board“ im Projekt: Vorgänge als Karten in den Spalten Offen, In Arbeit, Blockiert und Erledigt. Karte ziehen (oder das Statusfeld auf der Karte benutzen) ändert den Status – mit denselben Regeln und Rechten wie im Gantt (Mitarbeiter nur eigene Vorgänge). Das Board ist nur eine Sicht auf den Plan und hat keine eigenen Daten.' },
      { kind: 'neu', text: 'Board: Karten zeigen PSP, Zeitraum (rot bei überfällig), Fortschritt, Personen sowie Kennzeichen für kritischen Pfad, Meilenstein, Pool-Paket und Kommentare. Beim Verschieben nach „Blockiert“ wird der Grund erfragt; Vorgänge mit nicht erledigten Vorgängern tragen „⛓ wartet auf n“ und fragen vor „In Arbeit“/„Erledigt“ zurück.' },
      { kind: 'neu', text: 'Board: Suche, Filter „Nur meine“, „Nur Pool“, „Nur kritische“, „Erledigte ausblenden“ und Bahnen nach Phase oder Person; auf schmalen Bildschirmen werden die Spalten gewischt. Handbuchthema „Board (Kanban)“ (DE/EN).' },
    ],
  },
  {
    version: '0.12.0', date: '2026-10-21', title: 'Sitzungen absichern, Kopfleiste, Organigramm bearbeiten',
    changes: [
      { kind: 'neu', text: 'Sitzungen: Nach einem Passwortwechsel (eigen oder durch den Administrator) enden alle bisherigen Sitzungen des Benutzers; bei der eigenen Änderung bleibt die aktuelle Sitzung bestehen. Neu: Verwaltung → Benutzer → „Sitzungen beenden“ meldet einen Benutzer überall ab.' },
      { kind: 'verbessert', text: 'Kopfleiste: Dashboard, Wer arbeitet woran und Organigramm stehen jetzt unter dem Menüpunkt „Übersicht“.' },
      { kind: 'neu', text: 'Organigramm: Kästchen lassen sich mit der Maus auf ein anderes Kästchen ziehen (= unterstellen) bzw. auf die Projektleitung (= direkt unterstellt). Voraussetzung: Bearbeitungsrecht im Projekt; auf Touchgeräten weiter über die Spalte „Berichtet an“.' },
      { kind: 'neu', text: 'Organigramm-PDF: Seitenformat wählbar (Bildgröße, A4 quer, A3 quer, Folie 16:9).' },
    ],
  },
  {
    version: '0.11.0', date: '2026-10-21', title: 'Funktion je Ressource und Organigramm',
    changes: [
      { kind: 'neu', text: 'Organigramm je Projekt: neuer Tab „Organigramm“ und eigene Seite „Organigramm“ (Projektauswahl, für Vorgesetzte). Aufbau über die neue Spalte „Berichtet an“ im Tab Ressourcen; ohne Angabe hängt eine Ressource an der Projektleitung. Externe Ressourcen ohne Benutzerkonto erscheinen gestrichelt, Mitglieder ohne Ressource als eigene Kästchen. Export als PNG, SVG oder PDF.' },
      { kind: 'neu', text: 'Tab Ressourcen: neues Freitextfeld „Funktion“ je Ressource, z. B. Projektleiter, Netzwerktechniker oder Netzwerk-Lead – gilt je Projekt, dieselbe Person kann in jedem Projekt eine andere Funktion haben. „Wer arbeitet woran“ zeigt sie am Projekt.' },
    ],
  },
  {
    version: '0.10.1', date: '2026-10-21', title: 'Benutzersuche bei Ressourcen',
    changes: [
      { kind: 'verbessert', text: 'Tab Ressourcen: Die Verknüpfung einer Ressource mit einem Benutzer ist jetzt eine Suche (ID, Name oder E-Mail) über alle Benutzer statt einer Liste nur mit Verantwortlichem und Mitgliedern; die gewählte Person erscheint als „Name (ID)“.' },
    ],
  },
  {
    version: '0.10.0', date: '2026-10-21', title: 'Benutzer-ID und Anzeigename getrennt',
    changes: [
      { kind: 'neu', text: 'Benutzer haben jetzt eine ID (Anmeldename) und einen Anzeigenamen. Bei Active-Directory-Konten kommt der Name aus dem AD (displayName) und wird bei jeder Anmeldung abgeglichen; bei lokalen Konten pflegt ihn der Administrator in Verwaltung → Benutzer.' },
      { kind: 'verbessert', text: 'Die Benutzersuche (Verantwortliche, Mitglieder, Zuordnung, Reports) findet nach ID, Anzeigename und E-Mail und zeigt „Name (ID)“. Beim Verknüpfen einer Ressource mit einem Benutzer wird der Anzeigename als Ressourcenname vorgeschlagen.' },
      { kind: 'verbessert', text: 'Überall, wo Personen angezeigt werden (Kopfzeile, Verantwortlicher, Kommentare, Übersicht, Dashboard, Reports, Glocke und E-Mails), steht der Anzeigename. Journal und Audit-Log behalten die ID.' },
    ],
  },
  {
    version: '0.9.4', date: '2026-10-21', title: 'Passwort für lokale Benutzer setzen',
    changes: [
      { kind: 'neu', text: 'Verwaltung → Benutzer: Administratoren können für lokale Benutzer ein neues Passwort setzen (Button „Passwort setzen“). AD-Konten und das eigene Konto sind ausgenommen; der Vorgang steht im Audit-Log.' },
    ],
  },
  {
    version: '0.9.3', date: '2026-10-21', title: 'Rollen nachträglich ändern',
    changes: [
      { kind: 'neu', text: 'Verwaltung → Benutzer: Die Rolle (admin / editor / viewer) lässt sich nach dem Anlegen direkt in der Tabelle ändern und gilt sofort. Die eigene Rolle ist gesperrt; ein Wechsel zu viewer ist erst möglich, wenn der Benutzer keine Projekte mehr verantwortet. Die Änderung steht im Audit-Log.' },
    ],
  },
  {
    version: '0.9.2', date: '2026-10-21', title: 'AD: Ausfallsicherung & Gruppen im Test',
    changes: [
      { kind: 'neu', text: 'AD-Anmeldung: mehrere LDAP-Server (z. B. zwei Domain-Controller) in der LDAP-URL mit Leerzeichen oder Komma; Failover nur bei Verbindungsproblemen, nie bei falschem Passwort.' },
      { kind: 'neu', text: 'Verbindungstest: zeigt den antwortenden Server und die direkten Gruppen des Benutzers (zum Übernehmen der Gruppen-DNs).' },
    ],
  },
  {
    version: '0.9.1', date: '2026-10-21', title: 'Eine Ampel für Dashboard und Report',
    changes: [
      { kind: 'verbessert', text: 'Der Portfolio-Report (Reports und E-Mail) nutzt jetzt dieselbe Ampel wie das Dashboard: rot bei Ende nach Frist, mehr als 10 % überfälligen Vorgängen oder Blockaden, gelb bei überfälligen Vorgängen. Neu: Grund je Projekt und Kategorie „abgeschlossen“; das Budget steht daneben und färbt nicht mehr um.' },
    ],
  },
  {
    version: '0.9.0', date: '2026-10-21', title: 'Management-Dashboard',
    changes: [
      { kind: 'neu', text: 'Neue Seite „Dashboard“ für Vorstand, Bereichs- und Projektleiter: Projekt-Ampel (rot: Ende nach Frist, mehr als 10 % überfällig oder etwas blockiert; gelb: etwas überfällig), Kacheln, Meilenstein-Zeitstrahl, Risiken & Handlungsbedarf, Auslastung/Abwesenheit und Budget (nur mit Kostenrecht). Jeder sieht nur seine sichtbaren Projekte; als PNG oder PDF exportierbar.' },
    ],
  },
  {
    version: '0.8.0', date: '2026-10-21', title: 'Export für Folien',
    changes: [
      { kind: 'neu', text: 'Gantt: Export → „Bild / PDF für Folien“ als PNG (doppelte Auflösung), SVG oder PDF – immer im hellen Design, wählbar als Folie 16:9, A4/A3 quer oder Originalgröße, mit Seitenumbruch, Vorschau, Titel/Untertitel, Spalten, Zeitraum und Legende.' },
      { kind: 'neu', text: 'Management-Sicht: nur Phasen und Meilensteine (Ebenen wählbar) mit Beschriftung am Balken; außerdem „nur kritischer Pfad“.' },
      { kind: 'neu', text: 'Wer arbeitet woran: aktuelle Ansicht als PNG oder PDF speichern.' },
    ],
  },
  {
    version: '0.7.1', date: '2026-10-21', title: 'Feiertags-API einstellbar',
    changes: [
      { kind: 'neu', text: 'Verwaltung → Feiertags-API: URL der Feiertagsquelle einstellbar (Standard api-feiertage.de, Platzhalter {year} möglich), Verbindung testen, Zwischenspeicher einsehen und leeren.' },
    ],
  },
  {
    version: '0.7.0', date: '2026-10-21', title: 'Server-Umgebung bearbeiten',
    changes: [
      { kind: 'neu', text: 'Verwaltung → Server-Umgebung (.env): Variablen der .env bearbeiten (Kommentare bleiben, Passwörter/Schlüssel werden nie angezeigt), mit Sicherung der alten Datei und Audit-Eintrag (nur Namen), und den Container per Knopfdruck neu starten – die Seite lädt danach selbst neu.' },
      { kind: 'verbessert', text: 'Die .env wird beim Start direkt aus der eingebundenen Datei gelesen (ENV_FILE) und hat Vorrang vor der Compose-Umgebung; deshalb genügt ein Neustart statt „docker compose up“.' },
    ],
  },
  {
    version: '0.6.0', date: '2026-10-21', title: 'Wer arbeitet woran',
    changes: [
      { kind: 'neu', text: 'Neue Seite „Wer arbeitet woran“ für Vorgesetzte: Personen (Auslastung heute, Spitze der nächsten 30 Tage, Abwesenheit, Projekte mit offenen/überfälligen Vorgängen) und Projekte (Leitung, Fortschritt, Beteiligte mit Rolle). Zeigt genau die Projekte, die der Benutzer sehen darf; Ressourcen werden über das verknüpfte Benutzerkonto projektübergreifend zusammengeführt.' },
    ],
  },
  {
    version: '0.5.0', date: '2026-10-21', title: 'Leveling & persönliche Abwesenheiten',
    changes: [
      { kind: 'neu', text: 'Teamplaner: „Überlastung auflösen …“ schlägt Verschiebungen innerhalb des freien Puffers vor (Nachfolger und Projektende bleiben unverändert). Auswählen, übernehmen, mit Strg+Z rücknehmbar; nicht lösbare Fälle werden gesondert gemeldet.' },
      { kind: 'neu', text: 'Meine Abwesenheiten: Urlaub einmal persönlich eintragen – gilt in allen Projekten, in denen du als Ressource geführt wirst. „Krank“ sehen andere nur als „Sonstiges“, Notizen bleiben privat.' },
    ],
  },
  {
    version: '0.4.1', date: '2026-10-21', title: 'Puffer & kritischer Pfad',
    changes: [
      { kind: 'neu', text: 'Gantt: Schalter „Puffer“ blendet Gesamtpuffer und freien Puffer als Spalten ein, zeichnet Pufferlinien hinter die Balken und färbt knapp kritische Vorgänge orange (Schwelle einstellbar, Standard 2 Tage).' },
      { kind: 'neu', text: 'Gantt: „Nur kritische“ zeigt nur Vorgänge des kritischen Pfads samt Phasen.' },
      { kind: 'neu', text: 'Freier Puffer wird berechnet (alle Verknüpfungsarten); Sammelvorgänge zeigen den kleinsten Puffer ihrer Teilvorgänge; Tooltip und Vorgangsdialog nennen beide Werte.' },
    ],
  },
  {
    version: '0.4.0', date: '2026-10-20', title: 'Abwesenheiten & Jahresübersicht',
    changes: [
      { kind: 'neu', text: 'Abwesenheiten je Ressource (Urlaub, Schulung, Krank, Sonstiges) im Tab „Ressourcen“. Bearbeiter pflegen alle, Mitarbeiter die der eigenen Ressource.' },
      { kind: 'neu', text: 'Teamplaner: Abwesenheiten als schraffierte Bänder; an diesen Tagen hat die Ressource keine Kapazität – eingeplante Arbeit zählt als Überlastung (⚠ bei Einsatz während einer Abwesenheit).' },
      { kind: 'neu', text: 'Kalender: neue Jahresübersicht (12 Monate) mit freien Tagen, Abwesenheiten, Meilensteinen und Fristen; Klick auf einen Tag springt in die Monatsansicht. Abwesenheiten erscheinen auch in Monat und Woche.' },
    ],
  },
  {
    version: '0.3.1', date: '2026-10-20', title: 'Feiertage je Bundesland',
    changes: [
      { kind: 'neu', text: 'Projekt-Einstellungen und Assistent: Bundesland wählen und gesetzliche Feiertage per Knopfdruck laden (api-feiertage.de, Projektjahr + zwei Folgejahre). Eigene freie Tage bleiben erhalten; das Bundesland wird am Projekt gespeichert.' },
    ],
  },
  {
    version: '0.3.0', date: '2026-10-19', title: 'Release Notes & Verwaltung',
    changes: [
      { kind: 'neu', text: 'Release Notes / Changelog in der Verwaltung (diese Seite).' },
      { kind: 'neu', text: 'Zweisprachig: Deutsch (Standard) und Englisch, von jedem Benutzer selbst umschaltbar.' },
      { kind: 'neu', text: 'Hell-, Dunkel- oder Systemmodus, von jedem Benutzer selbst wählbar (Kopfzeile).' },
      { kind: 'neu', text: 'Meine Aufgaben: projektübergreifende To-do-Liste mit allen dir zugeordneten offenen Vorgängen (überfällig, diese Woche, später), Erledigt-Haken und Zähler in der Kopfzeile.' },
      { kind: 'neu', text: 'Zugriffsmodell: „Mitarbeiter“ ergibt sich automatisch aus der Zuordnung (eigene Vorgänge bearbeiten), neue Rolle „Betrachter (alle Projekte)“ (lesend, auch per AD-Gruppe), Benutzer lassen sich per Suche direkt einem Vorgang zuordnen – die Ressource entsteht bei Bedarf.' },
      { kind: 'neu', text: 'Geräteliste-Import: Location-Code (z. B. LOC024) als eigenes Feld – ein Code = eine Standort-Phase („LOC024 – Musterwerk“); Spaltenerkennung auch für Inventar-Exporte (konfigurierbarer Präfix); Bereinigung unsichtbarer Zeichen, einheitliche Priorität, Warnungen bei doppelten IPs und Seriennummern.' },
      { kind: 'verbessert', text: 'Smartphone-Ansicht: kompakte Kopfzeile mit Menü, Aufgabenliste als Karten im Gantt-Tab (Zeitachse umschaltbar), einklappbare Werkzeuge, Dialoge als Bottom-Sheet, Projektliste und Verwaltung ohne seitliches Überlaufen.' },
      { kind: 'neu', text: 'Assistent „Neues Projekt“: Projektart (leer, Netzwerk-Rollout, Server-Migration, Release-Transition), Grunddaten, Team per Suche, Projektreport und Zusammenfassung; der Schnellweg bleibt erhalten.' },
      { kind: 'neu', text: 'Handbuch und Hilfe in Deutsch und Englisch.' },
      { kind: 'neu', text: 'Zwei neue Beispielprojekte (in der Sprache des Benutzers): Server-Migration auf ein neues Cluster und Transition eines Release-Wechsels.' },
      { kind: 'neu', text: 'Englische Kopien der Standard-Vorlagen (Switch, Access Point, Firewall) in der Vorlagen-Bibliothek.' },
      { kind: 'neu', text: 'Benachrichtigungen, E-Mails, Reports und Erinnerungen erscheinen in der Sprache des Empfängers.' },
      { kind: 'verbessert', text: 'Server-Fehlermeldungen werden in der gewählten Sprache angezeigt; die Geräteliste erkennt auch englische Spaltenüberschriften.' },
      { kind: 'verbessert', text: 'Die Tabs der Verwaltung sind farblich voneinander abgesetzt.' },
    ],
  },
  {
    version: '0.2.0', date: '2026-10-16', title: 'Betrieb, Zusammenarbeit & Import',
    changes: [
      { kind: 'neu', text: 'Produktivbetrieb auf einer eigenen VM mit HTTPS (Zertifikat per ACME aus der internen CA).' },
      { kind: 'neu', text: 'Arbeitspakete: direkt zuordnen oder im Pool zur Selbstübernahme (übernehmen/zurückgeben).' },
      { kind: 'neu', text: 'Vorlagen je Gerätetyp, Geräteliste-Import (Excel/CSV mit Spaltenzuordnung und Vorschau) und Geräte-Matrix.' },
      { kind: 'neu', text: 'Anmeldung über Active Directory (LDAP), Pflege samt Verbindungstest in der Verwaltung.' },
      { kind: 'neu', text: 'Benachrichtigungen (Glocke und E-Mail), Projektreports, Portfolio- und Kostenstellen-Reports.' },
      { kind: 'neu', text: 'Automatische Erinnerungen: fällig, überfällig, Eskalation, blockiert.' },
      { kind: 'neu', text: 'Kommentare mit @-Erwähnung an Vorgängen.' },
      { kind: 'neu', text: 'Rückgängig/Wiederholen (Strg+Z / Strg+Y) für Planänderungen.' },
      { kind: 'neu', text: 'Live-Updates für mehrere Benutzer per Server-Sent Events.' },
      { kind: 'neu', text: 'Server-Zertifikat per ACME, Backup (täglich, mit Prüfung) und Audit-Log in der Verwaltung.' },
      { kind: 'verbessert', text: 'Teamplaner mit Split-Layout wie der Gantt; Kalender auf Smartphones nutzbar.' },
      { kind: 'behoben', text: 'Schnelle Folgeanfragen lieferten gelegentlich 404 (Commit erst nach der Antwort).' },
    ],
  },
  {
    version: '0.1.0', date: '2026-10-15', title: 'Erste Version',
    changes: [
      { kind: 'neu', text: 'Terminplanung mit kritischem Pfad (FS/SS/FF/SF mit Verzug, Constraints, Sammelvorgänge) und Gantt-Diagramm.' },
      { kind: 'neu', text: 'Basisplan mit Δ-Spalten, Status je Vorgang, Ressourcen und Teamansicht.' },
      { kind: 'neu', text: 'Budget und Controlling in EUR: Kostenstellen, Plan-/Ist-Kosten, SAP/CSV-Import, Kennzahlen (EVM).' },
      { kind: 'neu', text: 'Dokumente an Vorgängen, Hilfe-Panel mit Handbuch und Beispielprojekt.' },
    ],
  },
]

export const currentVersion = releases[0].version
