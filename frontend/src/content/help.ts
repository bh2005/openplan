// Hilfetexte für das Hilfe-Panel (F1) und das Handbuch (/help). Eine Quelle, zwei Darstellungen.
// Inhalte sind statisches HTML aus diesem Repo (kein Nutzer-Input) und werden per v-html gerendert.

import { computed } from 'vue'
import { lang } from '../lib/i18n'
import { helpEn } from './help.en'

export interface Topic { id: string; group: string; title: string; summary: string; html: string }

export const GROUPS = ['Erste Schritte', 'Planen', 'Team & Ressourcen', 'Kosten & Budget', 'Zusammenarbeit', 'Referenz'] as const

export const topicsDe: Topic[] = [
  // ───────────────────────────── Erste Schritte ─────────────────────────────
  {
    id: 'start', group: 'Erste Schritte', title: 'Willkommen bei OpenPlan',
    summary: 'Was OpenPlan kann und wie du in fünf Minuten startest.',
    html: `
<h2>Willkommen bei OpenPlan</h2>
<p>OpenPlan ist eine Projektplanung im Browser – eine Open-Source-Alternative zu MS Project. Du planst Vorgänge mit Terminen und Abhängigkeiten, siehst den kritischen Pfad, verteilst Arbeit auf dein Team und behältst das Budget im Blick.</p>
<h3>In fünf Minuten zum ersten Plan</h3>
<ol>
  <li>In der <b>Projektliste</b> auf <b>+ Neues Projekt</b> klicken (Name und Startdatum genügen). Du wirst <b>Verantwortlicher</b> des Projekts.</li>
  <li><b>+ Vorgang</b> anlegen. Name und Dauer per <b>Doppelklick</b> in die Tabellenzelle eintragen.</li>
  <li>Vorgänge verknüpfen: am rechten Ende eines Balkens den blauen Punkt auf den Folgevorgang ziehen – oder in der Spalte <b>Vorgänger</b> die PSP-Nummer eintragen (z. B. <code>1.1</code>).</li>
  <li>Phasen bilden: Vorgang markieren und <b>⇥</b> (Einrücken) – er wird Teilvorgang der darüberliegenden Zeile.</li>
  <li>Plan steht? Im Gantt <b>Basisplan setzen</b>. Ab jetzt zeigt OpenPlan Abweichungen (Tracking).</li>
</ol>
<h3>Am schnellsten lernst du am Beispiel</h3>
<p>In der Projektliste legt <b>Beispielprojekt anlegen</b> einen kompletten Netzwerk-Rollout (Cisco → Extreme, 3 Mitarbeiter, 4 Standorte, 60 Geräte) mit Plan, Team, Budget und Ist-Kosten an – zum Ausprobieren und Kaputtmachen.</p>
<h3>Wo finde ich was?</h3>
<table>
  <tr><th>Tab im Projekt</th><th>Zweck</th></tr>
  <tr><td><b>Gantt</b></td><td>Planen: Vorgänge, Termine, Abhängigkeiten, Status, Basisplan</td></tr>
  <tr><td><b>Team</b></td><td>Auslastung je Person, Umplanen per Ziehen</td></tr>
  <tr><td><b>Pakete</b></td><td>Arbeitspakete direkt zuordnen oder zur Selbstübernahme bereitstellen</td></tr>
  <tr><td><b>Kalender</b></td><td>Monats-/Wochen-/Listenansicht der Vorgänge</td></tr>
  <tr><td><b>Ressourcen</b></td><td>Personen/Geräte, Verfügbarkeit, Tagessätze</td></tr>
  <tr><td><b>Budget</b></td><td>Plan-/Ist-Kosten, Kennzahlen, SAP-Abgleich (nur für Verantwortliche)</td></tr>
  <tr><td><b>Verlauf</b></td><td>Wer hat was wann geändert</td></tr>
</table>
<p class="help-tip">💡 <b>F1</b> oder <b>?</b> öffnet jederzeit die Hilfe zur aktuellen Seite. Das vollständige Handbuch erreichst du über <b>Handbuch</b> in der oberen Leiste.</p>`,
  },
  {
    id: 'projekte', group: 'Erste Schritte', title: 'Projektliste',
    summary: 'Projekte anlegen, importieren, das Beispielprojekt, Verantwortliche.',
    html: `
<h2>Projektliste</h2>
<p>Hier siehst du alle Projekte, auf die du Zugriff hast: als <b>Verantwortlicher</b>, als <b>Mitglied</b> oder als <b>Admin</b>. Projekte anderer sind für dich unsichtbar.</p>
<h3>Aktionen</h3>
<ul>
  <li><b>+ Neues Projekt</b> – der <b>Assistent</b> führt in fünf Schritten durch: <i>Art</i> (Leeres Projekt, Netzwerk-/Geräte-Rollout, Server-Migration, Release-Transition, Einbau Patchfelder / Verkabelung – die Art legt Phasen, Vorgänge und Meilensteine an; unter „Patchaufträge (aus Portwerk)“ hängt Portwerk seine Patchaufträge ein), <i>Grunddaten</i> (Name, Beschreibung, Start, Arbeitstage, Feiertage; du wirst Verantwortlicher, <i>Admins</i> können einen anderen wählen), <i>Team</i> (Mitglieder per Suche, Editor oder Leser), <i>Berichte</i> (automatischer Projektreport) und <i>Fertig</i> (Zusammenfassung). Ressourcen, Budget und Basisplan richtest du danach im Projekt ein. <b>Schnell anlegen</b> im Assistenten öffnet den kurzen Dialog nur mit Name und Start.</li>
  <li><b>Beispielprojekt anlegen</b> – wähle ein Beispiel: <i>Netzwerk-Rollout Cisco → Extreme</i> (Geräte, Standorte), <i>Server-Migration Hypervisor → neues Cluster</i> (120 VMs in vier Wellen) oder <i>Transition Release-Wechsel</i> (Test, Schulung, Cutover, Hypercare, Übergabe) – jeweils mit Plan, Team, Budget und Ist-Kosten. Die Texte der Server-Migration und der Transition entstehen in deiner Sprache. Jeder Klick legt ein neues Beispiel an.</li>
  <li><b>Importieren …</b> – MS-Project-XML (MSPDI) oder OpenPlan-JSON, siehe <i>Import &amp; Export</i>.</li>
  <li><b>Löschen</b> (auf der Karte) – nur für den Verantwortlichen/Admin; entfernt Vorgänge, Kosten und Dokumente endgültig.</li>
</ul>
<p>Auf jeder Karte siehst du den Verantwortlichen (👤), die Zahl der Vorgänge und den Projektstart.</p>
<h3>Suchen &amp; filtern</h3>
<p>Das Suchfeld über den Karten durchsucht <b>Name, Beschreibung und Verantwortlichen</b> (mehrere Wörter = alle müssen passen, Groß-/Kleinschreibung und Umlaute spielen keine Rolle). Dazu filterst du nach <b>meinen Projekten</b> oder <b>Verantwortlichen</b> und sortierst nach Änderung, Name, Start oder Ende. Die Auswahl (ohne Suchtext) merkt sich der Browser. Administratoren finden dasselbe für <b>Benutzer</b> in der Verwaltung (Name, E-Mail, Rolle, Anmeldeart).
<p class="help-tip">💡 Siehst du ein erwartetes Projekt nicht? Bitte den Verantwortlichen, dich unter <b>Einstellungen → Mitglieder</b> hinzuzufügen.</p>`,
  },

  // ───────────────────────────── Planen ─────────────────────────────
  {
    id: 'dashboard', group: 'Erste Schritte', title: 'Management-Dashboard',
    summary: 'Portfolio-Ampel, Fristen, Meilensteine, Risiken, Auslastung und Budget auf einer Seite – als Bild oder PDF exportierbar.',
    html: `
<h2>Management-Dashboard</h2>
<p>Das <b>Dashboard</b> (obere Leiste) gibt Vorstand, Bereichsleitern und Projektleitern einen Überblick über <b>alle Projekte, die sie sehen dürfen</b> (Admins und „Betrachter (alle Projekte)“ alle, andere ihre eigenen). Es ist reine Ansicht und aktualisiert sich alle 5 Minuten. Mit <b>PNG</b> und <b>PDF</b> oben rechts exportierst du die Seite für Folien.</p>
<h3>Ampel-Regeln</h3>
<ul>
  <li><b>Rot</b> – ein Vorgang plant sein Ende <i>nach seiner Frist</i>, ODER mehr als <b>10 %</b> der Vorgänge sind überfällig, ODER irgendetwas ist <i>blockiert</i>.</li>
  <li><b>Gelb</b> – nicht rot, aber mindestens ein Vorgang ist überfällig.</li>
  <li><b>Grün</b> – sonst. <b>Abgeschlossen</b> = alle Vorgänge erledigt, <b>Leer</b> = noch keine Vorgänge.</li>
  <li>Das <b>Budget</b> geht nicht in die Ampel ein, steht aber daneben (Ist / Budget, CPI/SPI, ⚠ bei Überschreitung) – nur für Projekte, für die du Kosten sehen darfst. „Überfällig“ heißt: geplantes Ende liegt vor heute und der Vorgang ist nicht erledigt.</li>
</ul>
<h3>Bereiche</h3>
<ul>
  <li><b>Kacheln</b> – Zahl der Projekte nach Ampel, überschrittene Fristen, überfällige und blockierte Vorgänge, überlastete Personen, heute Abwesende, durchschnittlicher Fortschritt laufender Projekte, Gesamt-Budget.</li>
  <li><b>Projekt-Ampel</b> – eine Zeile je Projekt (Rot zuerst) mit Grund, Fortschritt, Ende, Budget und nächstem Meilenstein; die Chips filtern nach Farbe, ein Klick auf den Namen öffnet das Projekt.</li>
  <li><b>Meilensteine</b> – Zeitstrahl der nächsten 60 Tage (überfällige rot, kritische violett).</li>
  <li><b>Risiken &amp; Handlungsbedarf</b> – überschrittene Fristen, blockierte und überfällige Vorgänge mit Projekt und Bearbeiter; ein Klick öffnet den Vorgang.</li>
  <li><b>Auslastung &amp; Abwesenheit</b> – Überlast der nächsten 30 Tage und wer heute fehlt (gleiche Quelle wie „Wer arbeitet woran“).</li>
</ul>
<p class="help-tip">💡 Die Aussagekraft hängt an gepflegten Daten: Fristen an Vorgängen, Status und zugeordnete Ressourcen. Der <b>Portfolio-Report</b> (Reports, E-Mail) verwendet dieselbe Ampel (Texte dort: kritisch / Achtung / im Plan / abgeschlossen) und nennt bei jedem Projekt den Grund; auch dort steht das Budget daneben und beeinflusst die Farbe nicht.</p>`,
  },
  {
    id: 'uebersicht', group: 'Erste Schritte', title: 'Wer arbeitet woran (Übersicht)',
    summary: 'Personen und Projekte auf einen Blick – Auslastung, Abwesenheit, Projektzugehörigkeit.',
    html: `
<h2>Wer arbeitet woran</h2>
<p>Die Seite <b>Wer arbeitet woran</b> (obere Leiste) ist für Vorgesetzte und Projektverantwortliche gedacht: Sie zeigt über <b>alle Projekte, die du sehen darfst</b>, wer wo mitarbeitet. Admins und „Betrachter (alle Projekte)“ sehen alle Projekte, alle anderen ihre eigenen. Die Seite ist reine Ansicht – Änderungen machst du wie gewohnt im Projekt.</p>
<h3>Tab Personen</h3>
<ul>
  <li><b>Auslastung heute</b> – Summe der Zuordnungen über alle Projekte (Balken; rot = mehr als verfügbar). <b>Spitze 30 T</b> ist die höchste Tageslast der nächsten 30 Tage; ⚠ heißt Überlast oder Einsatz während einer Abwesenheit.</li>
  <li><b>Abwesenheit</b> – wer heute fehlt (grau, mit Rückkehrdatum) oder wann die nächste Abwesenheit ansteht. „Krank“ wird für andere als „Sonstiges“ gezeigt, Notizen sehen nur die Betroffenen selbst.</li>
  <li><b>Projekte</b> – Chips je Projekt mit Zahl der offenen Vorgänge; <b>★</b> = Projektleitung, rot umrandet = überfällige Vorgänge (<b>!n</b>), oranger Rand = blockierte. Klick öffnet das Projekt, der Tooltip nennt die Rolle und das späteste Ende.</li>
  <li>Filter <b>Überlastet (30 Tage)</b> und <b>Heute abwesend</b> sowie die Suche über Personen und Projekte.</li>
</ul>
<h3>Tab Projekte</h3>
<p>Eine Karte je Projekt: Leitung, Ende, Fortschritt (erledigte Vorgänge), überfällige und blockierte Vorgänge und darunter alle Beteiligten mit Rolle (★ Projektleitung, 👥 Mitglied, 🔧 arbeitet an Vorgängen), offenen Vorgängen und aktueller Auslastung.</p>
<h3>Wer erscheint?</h3>
<p>Projektverantwortliche, Mitglieder und alle Ressourcen. Eine Ressource mit verknüpftem Benutzer (Tab Ressourcen → Spalte <i>Benutzer</i>) wird mit diesem Benutzer zusammengeführt, auch wenn sie in mehreren Projekten vorkommt. Ressourcen <b>ohne</b> Benutzer (◌) werden über ihren Namen zusammengefasst.</p>
<p class="help-tip">💡 Die Auslastung stimmt nur, wenn Vorgänge Ressourcen zugeordnet sind. Persönliche Abwesenheiten trägt jeder unter <b>Meine Abwesenheiten</b> selbst ein.</p>`,
  },
  {
    id: 'todo', group: 'Erste Schritte', title: 'Meine Aufgaben (To-do-Liste)',
    summary: 'Alle dir zugeordneten offenen Vorgänge – über alle Projekte, nach Termin sortiert.',
    html: `
<h2>Meine Aufgaben</h2>
<p>Unter <b>Meine Aufgaben</b> (obere Leiste) siehst du alle offenen Vorgänge, die <b>dir zugeordnet</b> sind – über <b>alle Projekte</b> hinweg, nach Ende bzw. Frist sortiert und gruppiert in <b>Überfällig</b>, <b>Diese Woche</b> und <b>Später</b>. Das Zahlen-Chip neben dem Menüpunkt zeigt die Anzahl (rot, wenn etwas überfällig ist).</p>
<ul>
  <li><b>✓</b> links markiert die Aufgabe als erledigt (Fortschritt 100 %) – sie verschwindet aus der Liste.</li>
  <li>Ein Klick auf den Namen öffnet die Details des Vorgangs im Projekt, ein Klick auf den Projektnamen das Projekt.</li>
  <li>Die Chips oben filtern nach <b>Überfällig</b>, <b>Diese Woche</b>, <b>Später</b> oder <b>Blockiert</b>; die Suche durchsucht Projekt, PSP-Nr., Name und Blockadegrund.</li>
  <li>Eine gesetzte <b>Frist</b> hat Vorrang vor dem geplanten Ende. <b>●</b> = kritischer Pfad; blockierte Aufgaben tragen einen orangen Rand samt Grund.</li>
  <li>Unter der Liste steht, wie viele offene <b>Arbeitspakete im Pool</b> deiner Projekte auf Übernahme warten (Tab <i>Pakete</i>).</li>
</ul>
<p class="help-tip">💡 Die Liste ist leer? Dann ist deine <b>Ressource nicht mit deinem Benutzer verknüpft</b> (Tab Ressourcen → Spalte <i>Benutzer</i>), oder dir ist nichts zugeordnet.</p>`,
  },
  {
    id: 'gantt', group: 'Planen', title: 'Gantt & Vorgangstabelle',
    summary: 'Tabelle bearbeiten, Balken ziehen, Zoom, Filter, Mehrfachauswahl.',
    html: `
<h2>Gantt &amp; Vorgangstabelle</h2>
<p>Links die Tabelle, rechts das Zeitdiagramm. Beide scrollen vertikal gemeinsam; das Diagramm hat eine eigene horizontale Scrollleiste. Die <b>Trennlinie</b> dazwischen lässt sich ziehen (Doppelklick = Standardbreite).</p>
<h3>Tabelle bearbeiten</h3>
<p><b>Doppelklick</b> auf eine Zelle, <b>Enter</b> übernimmt, <b>Esc</b> bricht ab.</p>
<table>
  <tr><th>Spalte</th><th>Bedeutung</th></tr>
  <tr><td>✓</td><td>Haken = erledigt (setzt 100 %). Nochmal klicken = wieder offen.</td></tr>
  <tr><td>PSP</td><td>Gliederungsnummer (1, 1.1, 1.2 …) – wird automatisch vergeben</td></tr>
  <tr><td>Dauer</td><td>in Arbeitstagen; <b>◆</b> = Meilenstein (Dauer 0)</td></tr>
  <tr><td>Beginn / Ende</td><td>berechnet. Beginn ändern setzt „Beginn frühestens“ (📌)</td></tr>
  <tr><td>%</td><td>Fortschritt, gekoppelt an den Status</td></tr>
  <tr><td>Status</td><td>Offen · In Arbeit · Blockiert · Erledigt</td></tr>
  <tr><td>Vorgänger</td><td>z. B. <code>2, 3AA+1T, 4EE-1T</code> – siehe <i>Abhängigkeiten</i></td></tr>
  <tr><td>Δ Beginn / Δ Ende</td><td>Abweichung zum Basisplan (nur mit Basisplan)</td></tr>
</table>
<h3>Im Diagramm</h3>
<ul>
  <li><b>Balken ziehen</b> – verschiebt den Vorgang (setzt „Beginn frühestens“).</li>
  <li><b>Rechten Rand ziehen</b> – ändert die Dauer.</li>
  <li><b>Blauen Punkt am Balkenende</b> auf einen anderen Vorgang ziehen – verknüpft (Ende→Anfang).</li>
  <li><b>Sammelbalken (schwarz) ziehen</b> – verschiebt die ganze Phase.</li>
  <li><b>Doppelklick</b> – öffnet die Details (Constraint, Ressourcen, Dokumente, Notizen).</li>
  <li><b>◌ / ▣</b> hinter dem Namen kennzeichnet ein <i>Arbeitspaket</i>: ◌ = offen im Pool, ▣ = übernommen/zugeordnet.</li>
  <li>Die rote gestrichelte Linie ist <b>heute</b>; Wochenenden und Feiertage sind grau.</li>
</ul>
<h3>Werkzeugleiste</h3>
<ul>
  <li><b>↶ / ↷</b> (<b>Strg+Z</b> / <b>Strg+Y</b>) – macht die letzte Planänderung rückgängig bzw. wiederholt sie. Der Tooltip nennt die Änderung. Gilt für Vorgänge, Abhängigkeiten, Ressourcen, Zuordnungen und Basisplan (bis zu 20 Schritte); nicht für Projekteinstellungen, Budget und Dokumente. Zurücknehmen darf, wer die Änderung gemacht hat, sowie der Verantwortliche.</li>
  <li><b>+ Vorgang / ◆ Meilenstein</b> – fügt hinter der markierten Zeile ein.</li>
  <li><b>⇤ ⇥ ↑ ↓</b> – Ausrücken, Einrücken, nach oben/unten.</li>
  <li><b>✓ Erledigt</b> und <b>Status setzen …</b> – wirken auf die gesamte Auswahl.</li>
  <li><b>Heute</b> springt zum aktuellen Tag; <b>Tage/Wochen/Monate</b> ändert die Zeitskala.</li>
  <li><b>Status-Filter</b> – z. B. „Nicht erledigt“ oder „Nur Blockierte“. Phasen mit passenden Teilvorgängen bleiben sichtbar.</li>
  <li><b>Kritischer Pfad</b> / <b>Basisplan</b> – Anzeige ein-/ausschalten.</li>
  <li><b>Puffer</b> – blendet die Spalten <b>Puffer</b> (Gesamtpuffer) und <b>fr. Puffer</b> (freier Puffer) ein, zeichnet hinter jedem Balken eine gestrichelte <b>Pufferlinie</b> und färbt <b>knapp kritische</b> Vorgänge orange. Was „knapp“ heißt, stellst du mit <b>knapp ≤ n T</b> ein (Standard 2 Tage).</li>
  <li><b>Export … → Bild / PDF für Folien</b> – erzeugt ein sauberes, immer helles Gantt für Vorstand und Management als <b>PNG</b> (doppelte Auflösung, passt scharf auf Folien), <b>SVG</b> (Vektor, in PowerPoint einfügbar) oder <b>PDF</b> (Druckdialog → „Als PDF speichern“, Ränder „Keine“). Wählbar sind <b>Umfang</b> (alle Vorgänge, nur <i>Phasen &amp; Meilensteine</i> als Management-Sicht mit Beschriftung am Balken, nur kritischer Pfad), <b>Format</b> (Folie 16:9, A4/A3 quer oder Originalgröße; zu viele Zeilen werden auf mehrere Seiten verteilt), Zeitraum, Spalten, Titel/Untertitel sowie Heute-Linie, kritischer Pfad, Basisplan, Abhängigkeiten und Legende. Die Vorschau zeigt das Ergebnis live; die Einstellungen merkt sich der Browser.</li>
  <li><b>Nur kritische</b> – zeigt nur Vorgänge auf dem kritischen Pfad, samt ihren Phasen (kombinierbar mit dem Statusfilter).</li>
</ul>
<h3>Mehrfachauswahl</h3>
<p><b>Strg-Klick</b> markiert einzelne Zeilen, <b>Umschalt-Klick</b> einen Bereich. Danach z. B. <b>✓ Erledigt</b>.</p>
<p class="help-tip">💡 Siehst du die Bearbeiten-Schaltflächen nicht? Dann hast du in diesem Projekt nur Leserechte.</p>`,
  },
  {
    id: 'struktur', group: 'Planen', title: 'Struktur: Phasen & Meilensteine',
    summary: 'Sammelvorgänge, Einrücken, Phasen verschieben, Meilensteine.',
    html: `
<h2>Struktur: Phasen &amp; Meilensteine</h2>
<h3>Sammelvorgänge (Phasen)</h3>
<p>Ein Vorgang mit Teilvorgängen ist ein <b>Sammelvorgang</b>. Seine Termine, Dauer, Fortschritt und Status werden <b>aus den Teilvorgängen berechnet</b> – deshalb sind Dauer, Ende und % dort nicht direkt änderbar (ein Hinweis erklärt das).</p>
<ul>
  <li><b>Einrücken ⇥</b> macht die markierte Zeile zum Teilvorgang der Zeile darüber, <b>Ausrücken ⇤</b> hebt das auf.</li>
  <li><b>▾ / ▸</b> klappt eine Phase auf oder zu.</li>
  <li><b>Phase verschieben:</b> Beginn der Phase ändern oder den Sammelbalken ziehen. Alle Einstiegs-Teilvorgänge werden entsprechend festgesetzt, der Rest folgt über die Abhängigkeiten.</li>
  <li><b>Status der Phase setzen</b> gilt für <i>alle</i> Teilvorgänge (mit Rückfrage).</li>
</ul>
<h3>Abhängigkeiten an Phasen</h3>
<p>Verknüpfungen von/zu einer Phase werden intern auf deren Teilvorgänge abgebildet. Eine Verknüpfung zwischen einer Phase und ihrem <i>eigenen</i> Teilvorgang ist nicht erlaubt.</p>
<h3>Meilensteine ◆</h3>
<p>Meilensteine haben Dauer 0 und liegen – wie in MS Project – am <b>Ende</b> des Tages. Sie eignen sich für Freigaben und Übergaben.</p>
<h3>Reihenfolge ändern</h3>
<p><b>↑ ↓</b> verschiebt innerhalb der Ebene, <b>Alt+Pfeiltasten</b> funktionieren genauso.</p>`,
  },
  {
    id: 'abhaengigkeiten', group: 'Planen', title: 'Abhängigkeiten & Verzögerung',
    summary: 'EA/AA/EE/AE, Verzögerung (Lag), Schreibweise in der Vorgänger-Spalte.',
    html: `
<h2>Abhängigkeiten &amp; Verzögerung</h2>
<p>Eine Abhängigkeit legt fest, wann ein Vorgang frühestens beginnen oder enden darf.</p>
<table>
  <tr><th>Kürzel</th><th>Englisch</th><th>Bedeutung</th></tr>
  <tr><td><b>EA</b> (Standard)</td><td>FS</td><td><b>E</b>nde→<b>A</b>nfang: Nachfolger startet, wenn der Vorgänger fertig ist</td></tr>
  <tr><td><b>AA</b></td><td>SS</td><td><b>A</b>nfang→<b>A</b>nfang: beide starten gemeinsam (oder versetzt)</td></tr>
  <tr><td><b>EE</b></td><td>FF</td><td><b>E</b>nde→<b>E</b>nde: beide enden gemeinsam</td></tr>
  <tr><td><b>AE</b></td><td>SF</td><td><b>A</b>nfang→<b>E</b>nde: selten – Nachfolger endet erst, wenn der Vorgänger beginnt</td></tr>
</table>
<h3>Schreibweise in der Spalte „Vorgänger“</h3>
<table>
  <tr><th>Eingabe</th><th>Wirkung</th></tr>
  <tr><td><code>3</code></td><td>Ende→Anfang zu PSP 3</td></tr>
  <tr><td><code>2, 4</code></td><td>zwei Vorgänger (Komma oder Semikolon)</td></tr>
  <tr><td><code>3AA</code></td><td>Anfang→Anfang zu PSP 3</td></tr>
  <tr><td><code>3EA+2T</code></td><td>Ende→Anfang mit <b>2 Arbeitstagen Verzögerung</b></td></tr>
  <tr><td><code>4EE-1T</code></td><td>Ende→Ende, Nachfolger endet 1 Tag <b>früher</b> (negative Verzögerung = Überlappung)</td></tr>
</table>
<p>Englische Kürzel (<code>FS</code>, <code>SS</code>, <code>FF</code>, <code>SF</code>) werden ebenfalls verstanden.</p>
<h3>Per Maus</h3>
<p>Blauen Punkt am Balkenende auf den Folgevorgang ziehen – das erzeugt Ende→Anfang ohne Verzögerung. Typ und Verzögerung ändern geht in der Spalte oder im Detaildialog.</p>
<h3>Zyklen</h3>
<p>Ein Kreis (A→B→A) wird abgelehnt; die Meldung nennt die beteiligten Vorgänge, der Plan bleibt unverändert.</p>`,
  },
  {
    id: 'termine', group: 'Planen', title: 'Termine, Constraints & kritischer Pfad',
    summary: 'Wie Termine berechnet werden, Einschränkungen, Puffer.',
    html: `
<h2>Termine, Constraints &amp; kritischer Pfad</h2>
<h3>So rechnet OpenPlan</h3>
<p>Jeder Vorgang beginnt so früh wie möglich – begrenzt durch Vorgänger, Projektstart und Einschränkungen. Gerechnet wird in <b>Arbeitstagen</b> nach dem Projektkalender (Standard Mo–Fr, Feiertage konfigurierbar unter <b>Einstellungen</b>). Dort wählst du ein <b>Bundesland</b> und übernimmst mit <b>Feiertage laden</b> die gesetzlichen Feiertage (Quelle: api-feiertage.de) für das Projektjahr und die zwei Folgejahre; eigene freie Tage (Brückentage, Betriebsferien) trägst du zusätzlich von Hand ein und bleiben beim erneuten Laden erhalten. Die API liefert derzeit nur 2026–2028; für spätere Jahre die Tage von Hand ergänzen.</p>
<h3>Einschränkungen (Constraints)</h3>
<p>Im Detaildialog (Doppelklick auf den Vorgang):</p>
<table>
  <tr><th>Einschränkung</th><th>Wirkung</th></tr>
  <tr><td>So früh wie möglich</td><td>Standard – nur Abhängigkeiten bestimmen den Termin</td></tr>
  <tr><td>Beginn frühestens am</td><td>Vorgang startet nicht vor dem Datum (📌). Entsteht auch beim Verschieben im Diagramm</td></tr>
  <tr><td>Manuell: Beginn am (fest)</td><td>Start ist fest; Vorgänger werden ignoriert („manuell geplant“)</td></tr>
  <tr><td>Ende spätestens am</td><td>wirkt auf den Puffer: zeigt, wie viel Luft bis zur Frist bleibt</td></tr>
</table>
<h3>Puffer &amp; kritischer Pfad</h3>
<ul>
  <li><b>Puffer</b> (Gesamtpuffer): wie viele Arbeitstage ein Vorgang sich verschieben darf, ohne das Projektende zu verschieben (im Detaildialog).</li>
  <li><b>Kritisch</b> = Puffer 0. Diese Vorgänge sind <b>rot</b>, ebenso die Pfeile dazwischen. Jede Verzögerung dort verschiebt das Projektende.</li>
  <li>Bei sehr linearen Plänen (z. B. ein Rollout Standort nach Standort) ist fast alles kritisch – das ist korrekt, kein Fehler.</li>
  <li>Mit dem Haken <b>Kritischer Pfad</b> in der Leiste blendest du die Rotfärbung aus.</li>
</ul>
<p class="help-tip">💡 Beginn lässt sich nicht <i>früher</i> als der Vorgänger erlauben, es sei denn du wählst „Manuell: Beginn am (fest)“.</p>`,
  },
  {
    id: 'status', group: 'Planen', title: 'Status & Fortschritt',
    summary: 'Offen, In Arbeit, Blockiert, Erledigt – und wie sie mit % zusammenhängen.',
    html: `
<h2>Status &amp; Fortschritt</h2>
<p>Jeder Vorgang hat einen Status: <b>Offen</b>, <b>In Arbeit</b>, <b>Blockiert</b> (mit optionalem Grund) oder <b>Erledigt</b>.</p>
<h3>Kopplung mit dem Fortschritt</h3>
<table>
  <tr><th>Du tust …</th><th>Ergebnis</th></tr>
  <tr><td>Status <b>Erledigt</b> setzen / Haken klicken</td><td>Fortschritt = 100 %</td></tr>
  <tr><td>Status <b>Offen</b> setzen</td><td>Fortschritt = 0 %</td></tr>
  <tr><td>Fortschritt auf <b>100 %</b> setzen</td><td>Status = Erledigt</td></tr>
  <tr><td>Fortschritt <b>&gt; 0 %</b> bei „Offen“</td><td>Status = In Arbeit</td></tr>
  <tr><td>Von Erledigt auf <b>In Arbeit</b> oder <b>Blockiert</b></td><td>Fortschritt sinkt auf 90 % (100 % passt nicht zu „nicht fertig“)</td></tr>
  <tr><td>Status <b>Blockiert</b></td><td>Fortschritt bleibt; Grund im Detaildialog eintragen (erscheint als Tooltip)</td></tr>
</table>
<h3>Sammelvorgänge</h3>
<p>Der Status einer Phase wird abgeleitet: alle Teilvorgänge erledigt → Erledigt; einer blockiert → Blockiert; sonst In Arbeit (wenn etwas begonnen oder erledigt ist) bzw. Offen. Setzt du den Status einer Phase selbst, gilt er für <b>alle Teilvorgänge</b>.</p>
<h3>Darstellung</h3>
<ul>
  <li><b>Erledigt:</b> Zeile grau und durchgestrichen, Balken blass mit ✓.</li>
  <li><b>Blockiert:</b> oranger Rand, Balken mit ⛔ und gestricheltem Rand; im Projektkopf zählt ein Chip „n blockiert“ (Klick filtert).</li>
</ul>
<h3>Mehrere Vorgänge auf einmal</h3>
<p>Mit <b>Strg-/Umschalt-Klick</b> markieren, dann <b>✓ Erledigt</b> oder <b>Status setzen …</b>. Der <b>Status-Filter</b> in der Leiste blendet erledigte Vorgänge aus.</p>
<p class="help-tip">💡 Der Fortschritt fließt in die Budget-Kennzahlen ein: Erledigte Vorgänge zählen voll als „Fertigstellungswert“ (EV).</p>`,
  },
  {
    id: 'basisplan', group: 'Planen', title: 'Basisplan & Tracking',
    summary: 'Plan einfrieren und Abweichungen verfolgen.',
    html: `
<h2>Basisplan &amp; Tracking</h2>
<p>Der <b>Basisplan</b> ist eine Momentaufnahme deines Plans (Termine und Plankosten), mit der du später den tatsächlichen Verlauf vergleichst.</p>
<h3>Setzen und löschen</h3>
<ul>
  <li><b>Basisplan setzen</b> (nur Verantwortlicher) speichert Beginn, Ende und Plankosten aller Vorgänge. Erneutes Setzen überschreibt.</li>
  <li><b>×</b> neben dem Button löscht den Basisplan.</li>
</ul>
<h3>Tracking im Gantt</h3>
<ul>
  <li>Unter jedem Balken zeigt ein <b>grauer Streifen</b> den Basisplan-Termin.</li>
  <li>Die Spalten <b>Δ Beginn</b> und <b>Δ Ende</b> nennen die Abweichung in Arbeitstagen: <span style="color:#dc2626">+3 T</span> = 3 Tage später als geplant, <span style="color:#16a34a">−2 T</span> = früher.</li>
  <li>Mit dem Haken <b>Basisplan</b> in der Leiste blendest du Streifen und Δ-Spalten aus.</li>
</ul>
<h3>Auswirkung auf das Budget</h3>
<p>Der Basisplan bestimmt das <b>Soll</b> der Kostenkennzahlen (BAC, PV). Spätere Planänderungen verändern das BAC nicht – genau so erkennst du Mehrkosten.</p>
<p class="help-tip">💡 Setze den Basisplan, sobald der Plan freigegeben ist – und vor den ersten Änderungen im laufenden Projekt.</p>`,
  },

  // ───────────────────────────── Team & Ressourcen ─────────────────────────────
  {
    id: 'ressourcen', group: 'Team & Ressourcen', title: 'Ressourcen',
    summary: 'Personen und Geräte anlegen, Verfügbarkeit, Tagessätze, Zuordnung.',
    html: `
<h2>Ressourcen</h2>
<p>Ressourcen sind Personen (oder Geräte), die du Vorgängen zuordnest.</p>
<h3>Anlegen</h3>
<p>Tab <b>Ressourcen</b> → Namen eintragen → <b>Hinzufügen</b>. <b>Max. Verfügbarkeit %</b> ist die Kapazität (100 = Vollzeit, 50 = halbe Stelle).</p>
<p>Wer Kosten sehen darf (Verantwortliche, ggf. Mitglieder), sieht zusätzlich <b>Tagessatz (EUR)</b>, <b>Kostenstelle</b> und <b>Kostenart</b>. Ändern dürfen das nur Verantwortliche.</p>
<p>Die Spalte <b>Benutzer</b> verknüpft eine Ressource mit einem Benutzer: ab zwei Zeichen suchen (ID, Name oder E-Mail), Treffer wählen, mit × wieder lösen. Sie wird gebraucht, damit <b>Arbeitspakete</b> übernommen werden können (siehe Thema „Arbeitspakete“). Ist der Ressourcenname noch leer, wird der Anzeigename des Benutzers vorgeschlagen.</p>
<h3>Funktion und Organigramm</h3>
<p>Die Spalte <b>Funktion</b> ist ein Freitext je Ressource <i>und Projekt</i>, z. B. „Projektleiter“, „Netzwerktechniker“ oder „Netzwerk-Lead“. Dieselbe Person kann in jedem Projekt eine andere Funktion haben. Die Spalte <b>Berichtet an</b> legt fest, wem die Ressource im <b>Organigramm</b> unterstellt ist; leer bedeutet: direkt der Projektleitung (dem Verantwortlichen). Zirkelbezüge werden abgewiesen. Wird die vorgesetzte Ressource gelöscht, hängen ihre Mitarbeiter wieder an der Projektleitung.</p>
<p>Das Organigramm zeigt der Tab <b>Organigramm</b> im Projekt; Vorgesetzte finden alle sichtbaren Projekte unter <b>Organigramm</b> in der Kopfzeile (Projekt wählen). <b>Gestrichelte</b> Kästchen sind Ressourcen ohne Benutzerkonto (Externe), graue sind Mitglieder ohne Ressource. Export als <b>PNG</b> (für Folien), <b>SVG</b> oder <b>PDF</b> (Seitenformat wählbar: Bildgröße, A4 quer, A3 quer, Folie 16:9).</p>
<p><b>Umhängen per Maus:</b> Mit Bearbeitungsrecht ziehst du ein Kästchen auf ein anderes (= wird ihm unterstellt) oder auf die Projektleitung (= direkt unterstellt). Nicht erlaubt sind Zirkel, also das Ablegen unter einem eigenen Untergebenen. Auf Touchgeräten bleibt die Spalte <b>Berichtet an</b>.</p>
<h3>Person zuordnen (ohne vorherige Ressource)</h3>
<p>Im Detaildialog eines Vorgangs gibt es <b>Person zuordnen</b>: Name oder E-Mail eintippen, Treffer wählen, Prozentwert setzen. OpenPlan legt die <b>verknüpfte Ressource</b> dabei automatisch an und gibt der Person Zugriff als <b>Mitarbeiter</b> – so entstehen Ressourcen nur für Leute, die wirklich Arbeit haben, und niemand muss vorher als Mitglied eingetragen werden.</p>
<h3>Zuordnen</h3>
<p>Doppelklick auf einen Vorgang → <b>Ressourcen</b>: Haken setzen und die <b>Zuordnung in %</b> eintragen (z. B. 50 % = halbtags). Die Zuordnung bestimmt Auslastung <i>und</i> Personalkosten (Dauer × Tagessatz × Zuordnung).</p>
<h3>Auslastung pro Woche</h3>
<p>Unter der Tabelle zeigt eine Matrix je Ressource und Kalenderwoche den <b>Spitzenwert</b>. <b>Rot</b> = mehr eingeplant als verfügbar. Tagesgenau siehst du das im Tab <b>Team</b>.</p>
<h3>Abwesenheiten</h3>
<p>Unter der Ressourcentabelle trägst du <b>Abwesenheiten</b> ein: Ressource, <b>Von</b>/<b>Bis</b> (beide Tage inklusive), <b>Art</b> (Urlaub, Schulung, Krank, Sonstiges) und eine Notiz. Verantwortliche und Bearbeiter pflegen alle; wer als <b>Mitarbeiter</b> mit einer Ressource verknüpft ist, trägt nur die <b>eigenen</b> ein. Eine Abwesenheit verschiebt keine Termine, sie nimmt der Ressource aber an den Arbeitstagen dieses Zeitraums die Kapazität: Im Tab <b>Team</b> zählt eingeplante Arbeit dann als Überlastung (⚠). Diese Einträge gelten je Projekt.</p>
<p><b>Persönliche Abwesenheiten:</b> Jeder trägt unter <b>Meine Abwesenheiten</b> (Kopfzeile) seinen Urlaub einmal selbst ein. Sie gelten automatisch in <i>allen</i> Projekten, in denen die Person über die Spalte <b>Benutzer</b> mit einer Ressource verknüpft ist, und erscheinen dort mit 👤 „persönlich“ (nur lesbar). „Krank“ sehen andere nur als „Sonstiges“, Notizen bleiben privat.</p>
<h3>Löschen</h3>
<p>Beim Löschen einer Ressource gehen ihre Zuordnungen und Abwesenheiten verloren (mit Rückfrage).</p>`,
  },
  {
    id: 'team', group: 'Team & Ressourcen', title: 'Team & Ressourcennutzung',
    summary: 'Auslastung je Person und Tag, Überlastung erkennen, per Ziehen umplanen.',
    html: `
<h2>Team &amp; Ressourcennutzung</h2>
<p>Pro Person eine Zeile mit der <b>Tageslast</b> (in %). Darunter stehen ihre Vorgänge als Balken.</p>
<h3>Lesen</h3>
<ul>
  <li><b>Grün</b> = innerhalb der Verfügbarkeit, <b>rot</b> = überlastet. Die Zahl im Kästchen ist die Summe der Zuordnungen an dem Tag.</li>
  <li>Links: <b>Spitzenlast / Verfügbarkeit</b> (z. B. <i>150 / 100 %</i>) und der <b>Aufwand in Personentagen</b> (PT).</li>
  <li><b>Schraffierte Bänder</b> in der Personenzeile sind <b>Abwesenheiten</b>; an diesen Tagen ist die Kapazität 0, eingeplante Arbeit wird rot und die Zeile links bekommt ein ⚠.</li>
  <li><b>Überlastung auflösen …</b> (erscheint bei Überlast, für Bearbeiter) schlägt Verschiebungen vor: Vorgänge werden nur <i>innerhalb ihres freien Puffers</i> nach hinten gerückt, sodass Nachfolger und Projektende unverändert bleiben. Du wählst aus und übernimmst – gesetzt wird „Beginn frühestens“, mit Strg+Z rücknehmbar. Begonnene, erledigte und manuell geplante Vorgänge bleiben unberührt, Überlast in der Vergangenheit wird ignoriert. Was im Puffer nicht lösbar ist, steht gesondert („braucht eine Entscheidung“): anders zuordnen, Termin bewusst verschieben oder Kapazität ändern.</li>
  <li>Der Chip oben nennt, wie viele Personen überlastet sind; <b>nur Überlastete</b> filtert die Liste.</li>
  <li><b>Nicht zugeordnet</b> (unten) sammelt Vorgänge ohne Ressource.</li>
</ul>
<p>Wie im Gantt: Die Tabelle links bleibt beim horizontalen Scrollen stehen, die <b>Trennlinie</b> lässt sich verschieben (Doppelklick = Standardbreite).</p>
<h3>Umplanen per Ziehen</h3>
<ul>
  <li><b>Horizontal</b> ziehen = Termin verschieben (setzt „Beginn frühestens“).</li>
  <li><b>Vertikal</b> auf die Zeile einer anderen Person = die Zuordnung wechselt (Prozentwert bleibt).</li>
  <li>In den Bereich <b>Nicht zugeordnet</b> ziehen = Zuordnung entfernen; aus diesem Bereich auf eine Person = zuordnen (100 %).</li>
  <li><b>Doppelklick</b> öffnet die Details.</li>
</ul>
<p class="help-tip">💡 Leser sehen die Ansicht, können aber nichts ziehen.</p>`,
  },
  {
    id: 'board', group: 'Team & Ressourcen', title: 'Board (Kanban)',
    summary: 'Vorgänge als Karten in den Spalten Offen, In Arbeit, Blockiert, Erledigt – Ziehen ändert den Status.',
    html: `
<h2>Board (Kanban)</h2>
<p>Das Board zeigt dieselben Vorgänge wie das Gantt, aber nach <b>Status</b> geordnet: <b>Offen</b>, <b>In Arbeit</b>, <b>Blockiert</b>, <b>Erledigt</b>. Es ist nur eine weitere <b>Sicht</b> – Termine, Abhängigkeiten und Fortschritt kommen weiter aus dem Plan. Sammelvorgänge (Phasen) erscheinen nicht als Karten; ihr Status leitet sich aus den Teilvorgängen ab.</p>
<h3>Status ändern</h3>
<ul>
  <li><b>Karte ziehen</b> in eine andere Spalte (Maus) – oder auf Touchgeräten und per Tastatur das <b>Statusfeld</b> unten auf der Karte benutzen.</li>
  <li>Es gelten dieselben Regeln wie überall: <b>Erledigt</b> setzt 100 %, <b>Offen</b> 0 %; siehe Thema „Status &amp; Fortschritt“.</li>
  <li><b>Blockiert:</b> beim Verschieben wird nach dem <b>Grund</b> gefragt (optional). Er steht danach auf der Karte.</li>
  <li><b>Wartende Vorgänger:</b> Hängt ein Vorgang von noch nicht erledigten Vorgängern ab, trägt die Karte „⛓ wartet auf n“. Beim Setzen auf <i>In Arbeit</i> oder <i>Erledigt</i> kommt eine Rückfrage; du kannst trotzdem bestätigen.</li>
  <li>Mitarbeiter ohne Planungsrecht können nur <b>eigene</b> Vorgänge verschieben; Betrachter sehen das Board, können aber nichts ändern.</li>
</ul>
<h3>Karte</h3>
<p>Auf der Karte stehen PSP-Nummer, Name, Zeitraum (rot mit ⚠, wenn überfällig oder Frist überschritten), Fortschritt, zugeordnete Personen und Kennzeichen: <b>!</b> kritischer Pfad (roter Rand; erledigte Vorgänge gelten nicht mehr als kritisch), ◆ Meilenstein, ◌ Pool-Paket ohne Bearbeiter, 💬 Kommentare. Ein Klick öffnet die Details.</p>
<h3>Filter &amp; Bahnen</h3>
<ul>
  <li><b>Suchen</b> in Name, PSP, Blockadegrund, Person und Phase.</li>
  <li><b>Nur meine</b> (Vorgänge deiner Ressource), <b>Nur Pool</b>, <b>Nur kritische</b>, <b>Erledigte ausblenden</b>.</li>
  <li><b>Bahnen</b>: Karten zusätzlich nach <i>Phase</i> oder <i>Person</i> gruppieren (bei mehreren Personen zählt die erste). Die Auswahl wird im Browser gemerkt.</li>
</ul>
<p class="help-tip">💡 Das Board plant nichts: Es gibt keine eigene Reihenfolge und keine eigenen Spalten. Zum Umplanen von Terminen oder Personen nimm Gantt bzw. Team.</p>`,
  },
  {
    id: 'pakete', group: 'Team & Ressourcen', title: 'Arbeitspakete',
    summary: 'Pakete direkt zuordnen oder im Pool zur Selbstübernahme bereitstellen.',
    html: `
<h2>Arbeitspakete</h2>
<p>Ein Arbeitspaket ist ein normaler Vorgang (mit Termin, Status, Dokumenten und Kosten), der entweder <b>direkt einer Ressource</b> zugeordnet wird oder <b>offen im Pool</b> liegt. Aus dem Pool ziehen sich Projektmitglieder ihre Pakete selbst.</p>
<h3>Einordnen unter einen Vorgang</h3>
<p>Ein Paket ist ein normaler Vorgang und kann unter jeder Phase oder jedem Vorgang liegen. Beim Anlegen wählst du dazu <b>gehört zu</b>; nachträglich geht es im Gantt über „Einrücken“ (⇥). Der übergeordnete Vorgang wird dadurch zum Sammelvorgang: Dauer, Ende, Fortschritt und Status berechnen sich aus seinen Paketen. Für viele gleichartige Schritte siehe „Geräte, Vorlagen &amp; Import“.</p>
<h3>Erledigungszeitraum (von – bis)</h3>
<p>Jedes Paket kann einen Zeitraum bekommen, in dem es erledigt werden soll: <b>von</b> = frühester Beginn (wirkt wie „Beginn frühestens am“ auf die Terminplanung), <b>bis</b> = <b>Frist</b>. Beides trägst du beim Anlegen im Tab <i>Pakete</i> ein oder später im Detaildialog („Beginn frühestens am“ + „Frist“). Liegt das geplante Ende nach der Frist, zeigen Paketliste, Tabelle und Dialog ein <b>⚠</b>. Die automatischen Erinnerungen (fällig, überfällig, Eskalation) richten sich nach der Frist, falls eine gesetzt ist. „von“ darf nicht nach „bis“ liegen.</p>
<h3>Anlegen</h3>
<ul>
  <li>Tab <b>Pakete</b> → Name und Dauer eintragen → unter <b>Offen im Pool</b> oder <b>Zuordnen: …</b> wählen → <b>Anlegen</b>.</li>
  <li>Jeder vorhandene Vorgang wird zum Paket: Doppelklick → <b>Arbeitspaket zur Selbstübernahme</b> aktivieren. (Sammelvorgänge gehen nicht.)</li>
</ul>
<h3>Übernehmen und zurückgeben</h3>
<ul>
  <li>Unter <b>Offen im Pool</b> steht jedes Paket, das keine Ressource hat. <b>Übernehmen</b> ordnet es dir zu (100 %) und setzt den Status von <i>offen</i> auf <i>in Arbeit</i>. Es kann nur <b>eine Person</b> ein Paket übernehmen.</li>
  <li><b>Zurückgeben</b> löst die Zuordnung wieder; das Paket liegt dann erneut im Pool. Zurückgeben dürfen die Person, die es übernommen hat, und der Verantwortliche („In den Pool“).</li>
  <li>Übernommen und zurückgegeben wird im <b>Verlauf</b> protokolliert.</li>
</ul>
<h3>Voraussetzungen</h3>
<ul>
  <li>Übernehmen dürfen <b>Bearbeiter</b> und der Verantwortliche. Leser sehen den Pool nur.</li>
  <li>Die Zuordnung läuft über eine <b>Ressource, die mit deinem Benutzer verknüpft ist</b> (Tab Ressourcen → Spalte Benutzer). Gibt es noch keine, legt OpenPlan beim ersten Übernehmen automatisch eine Ressource mit deinem Benutzernamen an.</li>
</ul>
<p class="help-tip">💡 Direkt zugeordnete Pakete erscheinen wie alle Vorgänge im Gantt und im Tab Team. Pool-Pakete stehen im Team-Planer unter <b>Nicht zugeordnet</b>, dort kannst du sie auch per Ziehen einer Person zuweisen.</p>`,
  },
  {
    id: 'geraete', group: 'Team & Ressourcen', title: 'Geräte, Vorlagen & Import',
    summary: 'Geräteliste (Excel/CSV) importieren: pro Gerät entstehen die Arbeitsschritte seiner Vorlage – mit Matrix-Ansicht.',
    html: `
<h2>Geräte, Vorlagen &amp; Import</h2>
<p>Für Rollouts mit vielen gleichartigen Geräten (z. B. Switche tauschen) legst du nicht jeden Schritt von Hand an: Du importierst eine <b>Geräteliste</b>, und OpenPlan erzeugt für jedes Gerät die <b>Arbeitsschritte seiner Vorlage</b> (bestellen, liefern, kommissionieren, konfigurieren, austauschen, testen …).</p>
<h3>Struktur im Plan</h3>
<p><b>Standort</b> (Phase) → <b>Gerät</b> (Vorgang, benannt nach dem Hostname) → <b>Schritte</b> (Arbeitspakete). Die Schritte sind nacheinander verkettet; eine Wartezeit (z. B. Lieferzeit) steht als Verzögerung dazwischen. Status, Fortschritt, Termine und Kosten von Gerät und Standort rechnen sich aus den Schritten hoch.</p>
<h3>Vorlagen (Menü „Vorlagen“)</h3>
<ul>
  <li>Eine Vorlage gehört zu einem <b>Gerätetyp</b> (Switch, Access Point, Firewall …). Der Name der Vorlage ist der Wert der Spalte „Gerätetyp“ in der Liste.</li>
  <li>Je Schritt: <b>Name, Rolle, Dauer, Wartezeit danach, Vorgänger</b>. Drei Schalter: <b>Preis</b> (der Preis der Liste wird als Plankosten an diesem Schritt gebucht), <b>Fenster</b> (das Wartungsfenster wird zum Erledigungszeitraum), <b>Lieferzeit</b> (die Spalte „Lieferzeit“ überschreibt die Wartezeit).</li>
  <li>Standardvorlagen für Switch, Access Point und Firewall sind angelegt – zusätzlich als englische Kopien („Switch (English)“ usw.), deren Name dann in der Spalte „Gerätetyp“ stehen muss. Bearbeiten dürfen Bearbeiter; Änderungen gelten für spätere Importe (bestehende Vorgänge bleiben unverändert).</li>
</ul>
<h3>Geräteliste importieren (Tab „Geräte“)</h3>
<ol>
  <li><b>Geräteliste importieren …</b> → Excel (.xlsx) oder CSV wählen. Pflichtspalten: <b>Hostname, Standort, Gerätetyp</b>. Ein Muster mit allen Spalten, Auswahllisten und deinen aktuellen Vorlagen lädst du mit <b>⬇ Muster-Excel herunterladen</b> (Menü „Vorlagen“ oder im Import-Dialog) – es wird bei jedem Download aus den aktuellen Vorlagen erzeugt.</li>
  <li><b>Spalten zuordnen</b> (wird vorgeschlagen), optional Zielvorgang, <b>Rollen → Ressourcen</b> festlegen. Rollen mit Ressource werden dieser zugeordnet; die übrigen Schritte gehen an „Verantwortlich“ der Zeile, sonst liegen sie als Pool-Pakete zur Selbstübernahme bereit.</li>
  <li><b>Vorschau prüfen</b>: zeigt neue/aktualisierte Geräte, Schritte, neue Standorte, Fehler je Zeile (unbekannter Gerätetyp, doppelter Hostname, Fenster „von nach bis“ …). Ohne „Zeilen überspringen“ wird entweder alles oder nichts importiert.</li>
  <li><b>Importieren</b>. Mit ↶ (Strg+Z) nimmst du den ganzen Import in einem Schritt zurück.</li>
</ol>
<h3>Location-Code &amp; Datenbereinigung</h3>
<ul>
  <li><b>Location-Code</b> (z. B. <code>LOC024</code>): Spalte „Location-Code“ / <code>Location_ID</code>. Der Standort-Phase wird der Code vorangestellt („LOC024 – Musterwerk“); alle Geräte mit demselben Code landen in <b>einer</b> Phase, egal wie der Ortsname geschrieben ist. Fehlt die Spalte, wird der Code aus Texten wie <code>LOC024__DE.Musterwerk</code> erkannt. Es genügt Standort <i>oder</i> Location-Code.</li>
  <li><b>Spalten werden erkannt</b>, auch bei Inventar-Exporten mit konfigurierbarem Präfix wie <code>INV_</code> (Umgebungsvariable <code>IMPORT_HEADER_PREFIXES</code>; Node Name, IP_Address, Serial_Number, Model_ID, City, Priority, Location_ID …). „City“ hat als Standort Vorrang vor „Location“.</li>
  <li><b>Bereinigung:</b> unsichtbare Zeichen (Zero-Width, Soft-Hyphen) und geschützte Leerzeichen werden entfernt, die Priorität wird vereinheitlicht („non business critical“ = „Non Business Critical“). Doppelte IP-Adressen oder Seriennummern erscheinen als Warnung im Bericht.</li>
</ul>
<p><b>Wiederholbar:</b> Der Hostname ist der Schlüssel. Beim erneuten Import werden Nachlieferungen ergänzt, Stammdaten und Wartungsfenster vorhandener Geräte aktualisiert – Status und erledigte Schritte bleiben. Preise brauchen das Kostenrecht (Verantwortliche/Admin); andernfalls werden sie ignoriert und das wird gemeldet.</p>
<h3>Matrix „Geräte × Schritte“</h3>
<ul>
  <li>Jede Zeile ein Gerät (gruppiert nach Standort), jede Spalte ein Schritt, jede Zelle der Status: ○ offen, ◐ in Arbeit, ✓ erledigt, ⛔ blockiert, ⚠ Frist überschritten, gestrichelter Rand = im Pool.</li>
  <li><b>Klick</b> wählt eine Zelle, <b>Strg-Klick</b> ergänzt, <b>Klick auf die Spaltenüberschrift</b> wählt den Schritt für alle gezeigten Geräte, <b>Klick auf den Hostnamen</b> alle Schritte des Geräts, <b>Klick auf den Standort</b> alle Schritte des Standorts. Danach den Status für die ganze Auswahl setzen. <b>Doppelklick</b> öffnet die Details (Termine, Kosten, Kommentare, Dokumente).</li>
  <li>Filter nach Vorlage, Standort, Suche (Hostname, Modell, IP), „nur unfertige“; <b>CSV-Export</b> für Berichte.</li>
</ul>
<p class="help-tip">💡 Einzelne Geräte ohne Excel legst du mit <b>+ Gerät aus Vorlage</b> an.</p>`,
  },
  {
    id: 'kalender', group: 'Team & Ressourcen', title: 'Kalenderansicht',
    summary: 'Vorgänge nach Monat, Woche oder als Liste.',
    html: `
<h2>Kalenderansicht</h2>
<p>Zeigt, was wann läuft – ohne Gantt. Gut für Auftraggeber, Teams und das Handy.</p>
<ul>
  <li><b>Monat / Woche</b> – Vorgänge als Balken über die Tage; Meilensteine mit ◆, kritische rot, erledigte blass und durchgestrichen, blockierte mit orangem Rand.</li>
  <li><b>Jahr</b> – alle zwölf Monate auf einen Blick: freie Tage grau, <b>Abwesenheiten</b> blau (dunkler = mehr Personen gleichzeitig), ◆ Meilensteine und ⚑ Fristen. Mit der Maus über einen Tag stehen Details im Tooltip, ein Klick springt in die Monatsansicht. Der Ressourcenfilter gilt auch hier.</li>
  <li><b>Liste</b> – Tabelle der Vorgänge des Zeitraums (mobil freundlich).</li>
  <li>In Monat und Woche zeigt ein farbiger Streifen am Tagesende, wer abwesend ist.</li>
  <li><b>‹ Heute ›</b> blättert; der Filter <b>Alle Ressourcen</b> zeigt nur die Vorgänge einer Person.</li>
  <li><b>Sammelvorgänge</b> blendet Phasen ein, <b>Erledigte ausblenden</b> räumt auf.</li>
  <li>Klick auf einen Balken oder eine Listenzeile öffnet die Details.</li>
</ul>`,
  },

  // ───────────────────────────── Kosten & Budget ─────────────────────────────
  {
    id: 'budget-uebersicht', group: 'Kosten & Budget', title: 'Budget: Übersicht & Kennzahlen',
    summary: 'Kacheln, Kostenverlauf, Aufschlüsselung, Abgleich.',
    html: `
<h2>Budget: Übersicht</h2>
<p>Der Tab <b>Budget</b> ist für <b>Verantwortliche und Admins</b> sichtbar; Mitglieder sehen ihn nur, wenn der Verantwortliche das unter <i>Budget &amp; Stammdaten</i> freigibt. Alle Beträge sind in <b>EUR</b>.</p>
<h3>Kacheln</h3>
<table>
  <tr><th>Kachel</th><th>Bedeutung</th></tr>
  <tr><td>Budget</td><td>Gesamtbudget und verbleibender Rest (Budget − Ist)</td></tr>
  <tr><td>Plan (aktuell)</td><td>Plankosten des heutigen Plans; darunter das Basisplan-Soll (BAC)</td></tr>
  <tr><td>Ist-Kosten (AC)</td><td>gebuchte Kosten; darunter der Fertigstellungswert (EV)</td></tr>
  <tr><td>Prognose bei Ende (EAC)</td><td>erwartete Gesamtkosten bei bisheriger Kosteneffizienz; Restkosten (ETC)</td></tr>
  <tr><td>Kostenindex (CPI)</td><td>EV ÷ AC. <b>≥ 1</b> = im Kostenrahmen</td></tr>
  <tr><td>Terminindex (SPI)</td><td>EV ÷ PV. <b>≥ 1</b> = im Zeitplan</td></tr>
</table>
<p>Der Rand der Index-Kacheln zeigt eine Ampel: grün ≥ 0,98 · gelb ≥ 0,90 · rot darunter. Rote Warnbalken erscheinen, wenn Plan oder Ist das Budget überschreiten oder die Prognose darüber liegt.</p>
<h3>Kostenverlauf</h3>
<p>Kumulierte Kurven pro Monat: <b>blau</b> Plan (Basisplan), <b>rot</b> Ist, <b>gelb gestrichelt</b> Budget, <b>grüner Punkt</b> Fertigstellungswert zum Stichtag. Liegt die rote Kurve über der blauen, gibst du mehr aus als geplant.</p>
<h3>Aufschlüsselungen</h3>
<ul>
  <li><b>Nach Kostenstelle / Kostenart</b> – Budget, Plan, Ist und Ist/Plan in %. Rote Zahlen = über Budget.</li>
  <li><b>Abgleich Kostenstelle × Kostenart</b> – Plan − Ist je Kombination; <b>CSV exportieren</b> für den Abgleich mit SAP.</li>
  <li><b>Nach Vorgang</b> – Plan, Basisplan, Ist und EV je Vorgang inkl. Phasensummen.</li>
</ul>
<p class="help-tip">💡 Ohne Basisplan beziehen sich EV und PV auf den aktuellen Plan – setze den Basisplan im Gantt, damit die Kennzahlen aussagekräftig sind. Begriffe: siehe <i>Kennzahlen (Glossar)</i>.</p>`,
  },
  {
    id: 'budget-plan', group: 'Kosten & Budget', title: 'Budget: Plankosten',
    summary: 'Personalkosten aus Ressourcen plus feste Kosten je Vorgang.',
    html: `
<h2>Plankosten</h2>
<p>Die Plankosten eines Vorgangs bestehen aus zwei Teilen:</p>
<ul>
  <li><b>Personalkosten</b> – automatisch: <i>Dauer × Tagessatz × Zuordnung %</i>. Tagessatz, Kostenstelle und Kostenart pflegst du an der Ressource.</li>
  <li><b>Feste Kosten</b> – Material, Lizenzen, Fremdleistungen, Reisekosten … Hier im Tab erfasst.</li>
</ul>
<h3>Feste Kosten erfassen</h3>
<p>Unten in der Tabelle: Vorgang wählen, Beschreibung, optional <b>Kostenstelle</b> und <b>Kostenart</b>, Betrag (<code>1.234,56</code> oder <code>1234.56</code>) → <b>+</b>. Bestehende Posten änderst du direkt in der Zeile, <b>×</b> löscht.</p>
<h3>Zeitliche Verteilung</h3>
<p>Kosten werden gleichmäßig über die Arbeitstage des Vorgangs verteilt (Meilensteine an ihrem Tag). Das ergibt den Plan-Verlauf (PV).</p>
<p class="help-tip">💡 Die Tabelle <b>Plankosten je Vorgang</b> trennt Personal und feste Kosten. Ressourcen ohne Tagessatz werden oben als Warnung gelistet – sie ergeben 0 € Personalkosten.</p>`,
  },
  {
    id: 'budget-ist', group: 'Kosten & Budget', title: 'Budget: Ist-Kosten & SAP-Import',
    summary: 'Buchungen erfassen oder per CSV importieren, Dubletten, Fehler.',
    html: `
<h2>Ist-Kosten</h2>
<p>Ist-Kosten sind gebuchte Beträge mit Datum, optional Kostenstelle, Kostenart, Vorgang, Belegnummer und Text. Gutschriften sind <b>negativ</b>.</p>
<h3>Manuell buchen</h3>
<p><b>+ Buchung</b>: Datum (<code>TT.MM.JJJJ</code>), Betrag, optional Zuordnungen. Zeilen lassen sich mit ✎ ändern und × löschen. Die Suche filtert nach Belegnummer und Text.</p>
<h3>CSV-Import (z. B. SAP-Export)</h3>
<ol>
  <li><b>CSV importieren …</b> und Datei wählen – OpenPlan prüft sofort (Vorschau, <b>noch nichts gebucht</b>).</li>
  <li>Ergebnis lesen: gültige Zeilen, Dubletten, Fehler je Zeile, die ersten Vorschauzeilen.</li>
  <li>Fehlerfrei? <b>Importieren</b>. Mit Fehlern wird <b>nichts</b> importiert (Alles-oder-nichts) – korrigiere die Datei oder wähle „trotz fehlerhafter Zeilen die gültigen importieren“.</li>
</ol>
<h3>Erwartetes Format</h3>
<table>
  <tr><th>Spalte (Überschrift)</th><th></th></tr>
  <tr><td><b>Buchungsdatum</b> / Datum / Budat</td><td>Pflicht; <code>15.10.2026</code> oder <code>2026-10-15</code></td></tr>
  <tr><td><b>Betrag</b> / Wert</td><td>Pflicht; <code>1.234,56</code>, <code>1,234.56</code>, <code>-12,50</code>, <code>12,50-</code>, <code>(100)</code></td></tr>
  <tr><td>Kostenstelle / Kostl</td><td>muss im Projekt existieren (oder automatisch anlegen lassen)</td></tr>
  <tr><td>Kostenart / Kstar</td><td>dito</td></tr>
  <tr><td>Belegnummer / Beleg</td><td>für den Dublettenschutz</td></tr>
  <tr><td>Text / Buchungstext</td><td>Beschreibung</td></tr>
  <tr><td>Vorgang / PSP-Nr.</td><td>PSP-Nummer des Vorgangs, z. B. <code>3.1</code></td></tr>
  <tr><td>Währung</td><td>nur <b>EUR</b>; andere Währungen werden als Fehler gemeldet</td></tr>
</table>
<ul>
  <li>Trennzeichen <code>;</code> <code>,</code> oder Tab; Zeichensatz UTF-8 oder Windows-1252 (Umlaute bleiben korrekt).</li>
  <li><b>Führende Nullen</b> bei Kostenstellen/-arten werden ignoriert (<code>100200</code> trifft <code>0000100200</code>).</li>
  <li><b>Dubletten:</b> gleiche Belegnummer + Kostenstelle + Kostenart + Betrag + Datum wird übersprungen – ein erneuter Import derselben Datei ist ungefährlich.</li>
  <li>Optionen: <b>unbekannte Kostenstellen/-arten anlegen</b>, <b>gültige trotz Fehlern importieren</b>.</li>
</ul>
<p class="help-tip">💡 <b>CSV exportieren</b> liefert alle Buchungen wieder heraus (Excel-freundlich, Semikolon, UTF-8 mit BOM).</p>`,
  },
  {
    id: 'budget-stamm', group: 'Kosten & Budget', title: 'Budget: Budgetzeilen & Stammdaten',
    summary: 'Budget festlegen, Kostenstellen und Kostenarten pflegen, Sichtbarkeit.',
    html: `
<h2>Budget &amp; Stammdaten</h2>
<h3>Budgetzeilen</h3>
<p>Eine Zeile ohne Kostenstelle und Kostenart ist das <b>Gesamtbudget</b>. Mit Kostenstelle und/oder Kostenart definierst du <b>Teilbudgets</b> (z. B. „Hardware 185.000 €“). Pro Kombination gibt es höchstens eine Zeile. <b>Budget speichern</b> übernimmt die Änderungen.</p>
<h3>Kostenstellen &amp; Kostenarten</h3>
<ul>
  <li>Einzeln anlegen (Nummer + Bezeichnung), mit ✎ ändern, mit × löschen. Gelöscht werden kann nur, was nirgends mehr verwendet wird.</li>
  <li><b>Liste einfügen / aus SAP importieren:</b> je Zeile <code>Nummer;Bezeichnung</code> (auch aus Excel kopiert, Tab erlaubt). Vorhandene Nummern werden aktualisiert.</li>
  <li>Die Stammdaten gelten <b>je Projekt</b>.</li>
</ul>
<h3>Sichtbarkeit</h3>
<p>Standardmäßig sehen nur Verantwortliche und Admins Kosten. Mit dem Haken <b>Projektmitglieder dürfen Kosten und Budget sehen</b> bekommen Mitglieder Lesezugriff – ändern dürfen weiterhin nur Verantwortliche.</p>`,
  },
  {
    id: 'kennzahlen', group: 'Kosten & Budget', title: 'Kennzahlen (Glossar)',
    summary: 'BAC, PV, EV, AC, CPI, SPI, EAC, ETC, VAC einfach erklärt.',
    html: `
<h2>Kennzahlen (Glossar)</h2>
<p>OpenPlan nutzt die <b>Earned-Value-Methode</b>: Geplantes, Erreichtes und Ausgegebenes werden in Euro verglichen.</p>
<table>
  <tr><th>Kürzel</th><th>Name</th><th>Bedeutung</th></tr>
  <tr><td><b>BAC</b></td><td>Budget at Completion</td><td>Gesamtkosten laut Basisplan</td></tr>
  <tr><td><b>PV</b></td><td>Planned Value</td><td>Plankosten, die bis zum Stichtag (heute) angefallen sein sollten</td></tr>
  <tr><td><b>EV</b></td><td>Earned Value</td><td>Wert der bisher erbrachten Leistung = Plankosten × Fortschritt %</td></tr>
  <tr><td><b>AC</b></td><td>Actual Cost</td><td>tatsächlich gebuchte Kosten</td></tr>
  <tr><td><b>CV</b></td><td>Cost Variance</td><td>EV − AC. Negativ = teurer als erwartet</td></tr>
  <tr><td><b>SV</b></td><td>Schedule Variance</td><td>EV − PV. Negativ = hinter dem Plan</td></tr>
  <tr><td><b>CPI</b></td><td>Cost Performance Index</td><td>EV ÷ AC. 0,9 = für 1 € Leistung zahlst du ca. 1,11 €</td></tr>
  <tr><td><b>SPI</b></td><td>Schedule Performance Index</td><td>EV ÷ PV. 0,9 = 10 % hinter dem Plan</td></tr>
  <tr><td><b>EAC</b></td><td>Estimate at Completion</td><td>Prognose der Gesamtkosten = BAC ÷ CPI</td></tr>
  <tr><td><b>ETC</b></td><td>Estimate to Complete</td><td>noch erwartete Kosten = EAC − AC</td></tr>
  <tr><td><b>VAC</b></td><td>Variance at Completion</td><td>BAC − EAC. Negativ = voraussichtlich Mehrkosten</td></tr>
</table>
<h3>Beispiel</h3>
<p>BAC 100.000 €, bisher 40 % geleistet (EV 40.000 €), aber 50.000 € ausgegeben: CPI = 0,8 → EAC = 125.000 € → du musst mit <b>25.000 € Mehrkosten</b> rechnen, wenn es so weitergeht.</p>`,
  },

  // ───────────────────────────── Zusammenarbeit ─────────────────────────────
  {
    id: 'dokumente', group: 'Zusammenarbeit', title: 'Dokumente & Links',
    summary: 'Lieferscheine, Stundenzettel, Excel-Tabellen oder OneDrive-Links an Vorgängen.',
    html: `
<h2>Dokumente &amp; Links</h2>
<p>An jedem Vorgang kannst du Dokumente ablegen – z. B. <b>Lieferscheine</b>, <b>Stundenzettel</b> oder <b>Excel-Tabellen</b>. Öffne dazu den Vorgang per Doppelklick; der Bereich <b>Dokumente &amp; Links</b> steht unter den Notizen. In der Tabelle zeigt ein <b>📎</b> neben dem Namen, dass Dokumente vorhanden sind.</p>
<h3>Hochladen</h3>
<ul>
  <li>Dateien in das Feld <b>ziehen</b> oder klicken, mehrere auf einmal möglich. Optional vorher einen <b>Kommentar</b> eintragen (z. B. „Lieferschein Nr. 4711“).</li>
  <li>Maximale Dateigröße standardmäßig <b>25 MB</b> (Administrator-Einstellung <code>MAX_UPLOAD_MB</code>).</li>
  <li>Nicht erlaubt sind ausführbare/skriptfähige Formate (z. B. <code>.exe</code>, <code>.bat</code>, <code>.ps1</code>, <code>.js</code>) sowie HTML und SVG.</li>
</ul>
<h3>Link zu OneDrive / SharePoint</h3>
<p><b>🔗 Link anhängen</b> → Freigabelink einfügen, optional Titel. Die Datei bleibt bei OneDrive (Berechtigungen und Versionen dort); OpenPlan speichert nur den Verweis. Erlaubt sind <code>http(s)</code>-Links.</p>
<h3>Öffnen &amp; Löschen</h3>
<ul>
  <li><b>Laden</b> lädt die Datei herunter; bei PDF und Bildern zeigt <b>Ansehen</b> eine Vorschau in neuem Tab. Links öffnen sich in neuem Tab.</li>
  <li><b>×</b> löscht (mit Rückfrage). Beim Löschen eines Vorgangs oder Projekts werden dessen Dateien mit entfernt.</li>
</ul>
<h3>Rechte</h3>
<p>Ansehen/Herunterladen: alle mit Zugriff aufs Projekt. Hochladen/Löschen: Verantwortliche und Editoren.</p>
<p class="help-tip">💡 Dokumente sind <b>nicht</b> Teil von JSON-/XML-Exporten. Fürs Backup den Ordner <code>data/</code> des Servers sichern.</p>`,
  },
  {
    id: 'rechte', group: 'Zusammenarbeit', title: 'Rollen, Verantwortlicher & Rechte',
    summary: 'Wer darf was – Admin, Verantwortlicher, Mitglieder.',
    html: `
<h2>Rollen, Verantwortlicher &amp; Rechte</h2>
<p class="help-tip">💡 Ist die Anmeldung über das <b>Active Directory</b> eingerichtet, melden sich Mitarbeiter mit ihrem Windows-Benutzernamen und -Passwort an. Das Konto entsteht beim ersten Login; das Passwort ändert man weiterhin im AD. Der lokale Admin bleibt als Notzugang bestehen.</p>
<h3>Globale Rolle (Benutzerkonto)</h3>
<table>
  <tr><th>Rolle</th><th>Darf</th></tr>
  <tr><td><b>admin</b></td><td>alles, in allen Projekten; Benutzer verwalten (Menü <b>Verwaltung</b>)</td></tr>
  <tr><td><b>editor</b></td><td>Projekte anlegen/importieren; planen in Projekten, in denen er Mitglied oder Verantwortlicher ist</td></tr>
  <tr><td><b>viewer</b></td><td>nur lesen – in den Projekten, in denen er Mitglied ist</td></tr>
  <tr><td><b>viewer + „Alle Projekte“</b></td><td>„Betrachter (alle Projekte)“: sieht <b>alle</b> Projekte, nur lesend – z. B. für Führungskräfte. Kosten nur, wenn ein Projekt sie für Mitglieder freigibt. Wird in der Verwaltung beim Benutzer gesetzt oder per AD-Gruppe (Betrachter-Gruppe).</td></tr>
</table>
<h3>Rolle im Projekt</h3>
<table>
  <tr><th>Rolle</th><th>Darf</th></tr>
  <tr><td><b>Verantwortlicher</b> (Projektleiter)</td><td>alles im Projekt: Einstellungen, Mitglieder, Basisplan, Budget &amp; Kosten, Löschen, Verantwortung übertragen</td></tr>
  <tr><td><b>Mitglied – Editor</b></td><td>Vorgänge, Termine, Status, Ressourcen-Zuordnung, Dokumente bearbeiten</td></tr>
  <tr><td><b>Mitglied – Leser</b></td><td>ansehen und Dokumente herunterladen</td></tr>
  <tr><td><b>Mitarbeiter</b> (automatisch)</td><td>ergibt sich aus der <b>Zuordnung</b>: Wer einem Vorgang zugeordnet ist, sieht das Projekt und darf an <i>seinen</i> Vorgängen Status, Fortschritt und Blockadegrund pflegen, Kommentare schreiben, Dokumente anhängen und Pool-Pakete übernehmen – aber nicht planen. Wird die Zuordnung entfernt, entfällt der Zugriff wieder.</td></tr>
</table>
<p>Jedes Projekt <b>hat genau einen Verantwortlichen</b>. Die globale Rolle <i>viewer</i> deckelt jede Projektrolle auf „lesen“.</p>
<h3>Sichtbarkeit</h3>
<p>Projekte sind nur für Verantwortliche, Mitglieder, <b>zugeordnete Mitarbeiter</b>, „Betrachter (alle Projekte)“ und Admins sichtbar. Alle anderen bekommen „nicht gefunden“ – sie erfahren nicht einmal, dass das Projekt existiert.</p>
<h3>Mitglieder verwalten</h3>
<p>Im Projekt <b>Einstellungen</b> (nur Verantwortlicher): Mitglied aus der Liste wählen → <b>Hinzufügen</b>, Rolle Editor/Leser einstellen.</p>
<h3>Verantwortung übertragen</h3>
<p>Einstellungen → <b>Verantwortlicher</b> neu wählen (nur Benutzer ohne Rolle viewer) → Speichern, Rückfrage bestätigen. Danach hast du ggf. keinen Zugriff mehr. Ein Benutzer, der noch Projekte verantwortet, kann nicht gelöscht werden.</p>
<h3>Kosten</h3>
<p>Kosten und Budget sieht nur der Verantwortliche (und Admins); der Verantwortliche kann das Lesen für Mitglieder freigeben. Details: <i>Budget &amp; Stammdaten</i>.</p>
<h3>Mein Konto</h3>
<p>Menü <b>Verwaltung</b>: Passwort ändern (mindestens 8 Zeichen); Admins legen dort auch Benutzer an.</p>`,
  },
  {
    id: 'verwaltung', group: 'Zusammenarbeit', title: 'Verwaltung: Anmeldung & Server-Zertifikat',
    summary: 'Active-Directory-Login und ACME-Zertifikat (nur Administratoren).',
    html: `
<h2>Verwaltung: Anmeldung &amp; Server-Zertifikat</h2>
<p>Unter <b>Verwaltung</b> (obere Leiste, nur für Administratoren) gibt es mehrere Bereiche: Benutzer, Anmeldung (AD), Benachrichtigung (E-Mail), Erinnerungen, Reports, Server-Zertifikat, Feiertags-API, Server-Umgebung (.env), API-Zugänge, Webhooks, Backup, Audit-Log und Release Notes (Änderungsverlauf je Version; jeder Bereich hat eine eigene Tab-Farbe). Zu E-Mail, Erinnerungen und Reports siehe „Benachrichtigungen &amp; Reports“.</p>
<h3>Benutzer</h3>
<p>Benutzer anlegen und löschen. Bei <b>Anmeldung</b> wählst du <i>lokal</i> (Passwort in OpenPlan) oder <i>Active Directory</i> (Passwort im AD, Konto ohne Passwort vorab anlegen).</p>
<p>Für lokale Konten gibt es <b>Passwort setzen</b> (Admin setzt ein neues Passwort) und für alle <b>Sitzungen beenden</b> (meldet den Benutzer überall ab). Nach einem Passwortwechsel – eigen oder durch den Admin – enden alle bisherigen Sitzungen des Benutzers; bei der eigenen Änderung bleibt die aktuelle bestehen.</p>
<h3>Anmeldung (Active Directory)</h3>
<ul>
  <li><b>Server:</b> LDAP-URL (bitte <code>ldaps://</code>), Base-DN und bei interner CA deren Zertifikat im PEM-Format. <b>Mehrere Server</b> (z. B. zwei Domain-Controller) trägst du mit Leerzeichen oder Komma hintereinander ein: Der nächste wird nur bei Verbindungsproblemen versucht, nie bei falschem Passwort. Der Verbindungstest nennt, welcher Server geantwortet hat, und listet die direkten Gruppen des Benutzers – praktisch zum Übernehmen der Gruppen-DNs.</li>
  <li><b>Anmeldung prüfen:</b> entweder nur die <b>Domain</b> eintragen (Anmeldung als <code>benutzer@domain</code>) oder einen <b>Service-Account</b> angeben, der den Benutzer sucht. Das Service-Passwort wird gespeichert, aber nie wieder angezeigt.</li>
  <li><b>Berechtigung:</b> Mit einer <b>Pflichtgruppe</b> dürfen sich nur deren Mitglieder anmelden. Die <b>Admin-Gruppe</b> macht Mitglieder zu OpenPlan-Administratoren. Neue Benutzer bekommen die gewählte Rolle.</li>
  <li><b>Verbindung testen</b> prüft die Werte aus dem Formular – auch ungespeichert – Schritt für Schritt (Bind, Benutzersuche, Passwort, Gruppen).</li>
  <li>Der lokale Admin bleibt immer als Notzugang bestehen. Passwörter von AD-Konten ändert man im AD.</li>
</ul>
<h3>Feiertags-API</h3>
<p>Der Bereich legt fest, woher <b>Feiertage laden</b> (Projekteinstellungen) die gesetzlichen Feiertage holt. Standard ist <code>https://get.api-feiertage.de</code>; eine eigene URL (z. B. ein interner Spiegel) muss dasselbe JSON-Format liefern. Der Server hängt <code>years=JJJJ</code> an oder ersetzt den Platzhalter <code>{year}</code>. <b>Verbindung testen</b> ruft die (auch ungespeicherte) URL für das laufende Jahr ab und zeigt das Ergebnis. Beim Ändern der URL wird der Zwischenspeicher geleert; er lässt sich auch von Hand leeren.</p>
<h3>Server-Umgebung (.env) &amp; Neustart</h3>
<ul>
  <li>Der Bereich bearbeitet die <b>.env</b> des Containers (Zugangsdaten, Proxy, Ports, AD-Voreinstellungen …). Kommentare in der Datei bleiben erhalten. <b>Passwörter und Schlüssel</b> (Namen mit PASSWORD, SECRET, TOKEN, _KEY …) werden nie angezeigt: leeres Feld = unverändert, ein neuer Wert ersetzt den alten. Namen schlägt die Eingabe vor (Autovervollständigung).</li>
  <li><b>Speichern</b> sichert zuerst die alte Datei (<code>data/env-backups/</code>, die letzten 10) und trägt die Änderung im Audit-Log ein – nur die <i>Namen</i> der Variablen, nie die Werte.</li>
  <li>Änderungen wirken erst nach <b>Container neu starten</b>: Die Anwendung beendet sich, Docker startet sie neu (Richtlinie <code>unless-stopped</code>), die Datei wird neu eingelesen und die Seite lädt selbst neu. Rund 10–30 Sekunden ist die Anwendung nicht erreichbar.</li>
  <li>Voraussetzung (Compose): <code>./.env:/app/.env</code> einbinden (Datei gehört uid 10001), <code>ENV_FILE=/app/.env</code>, <code>ALLOW_SELF_RESTART=1</code> und <code>restart: unless-stopped</code>. Sonst steht im Bereich „Nicht aktiviert“.</li>
</ul>
<p class="help-tip">💡 Startet die Anwendung nach einer Änderung nicht mehr (z. B. falscher Port), auf dem Host die gesicherte Datei aus <code>data/env-backups/</code> nach <code>.env</code> kopieren und <code>docker compose up -d</code> ausführen.</p>
<h3>Backup</h3>
<ul>
  <li><b>Jetzt sichern</b> erzeugt eine <code>.tar.gz</code> mit Datenbank (konsistent, auch im laufenden Betrieb) und allen Dokumenten. Passwörter und Schlüssel (JWT-Secret, TLS-Schlüssel) sind bewusst nicht enthalten.</li>
  <li><b>Automatisch:</b> täglich ab einer Uhrzeit, die letzten <i>n</i> Sicherungen bleiben. <b>Prüfen</b> öffnet das Archiv und führt eine Integritätsprüfung der Datenbank durch; <b>Herunterladen</b> holt sie zur externen Ablage.</li>
  <li><b>Wiederherstellen</b> geht nur offline per Kommandozeile (<code>python backup.py restore &lt;Datei&gt; --yes</code>, Anleitung im Bereich Backup). Die bisherigen Daten bleiben als <code>*.before-restore-…</code> erhalten.</li>
  <li>Tipp: <code>BACKUP_DIR</code> auf ein anderes Laufwerk legen und das Verzeichnis zusätzlich extern sichern.</li>
</ul>
<h3>Audit-Log</h3>
<p>Protokolliert Anmeldungen (auch <b>fehlgeschlagene</b>, mit IP), Benutzer-/Rechteänderungen, Einstellungen (AD, E-Mail, ACME, Erinnerungen), Datensicherung und das Löschen von Projekten. Suchen, nach Aktion filtern und als CSV exportieren; Einträge werden 365 Tage aufbewahrt.</p>
<h3>Server-Zertifikat (ACME)</h3>
<ul>
  <li>Trage die <b>Directory-URL</b> der CA (z. B. der internen step-ca), die <b>Domains</b> und optional eine E-Mail ein, speichere und klicke <b>Zertifikat anfordern</b>. Das Ergebnis erscheint oben (Aussteller, Domains, Ablauf, Fingerabdruck).</li>
  <li>Die CA bestätigt per <b>HTTP-01</b>: Port 80 der Domain muss zur App (Container-Port 8080) zeigen.</li>
  <li><b>Automatisch erneuern</b> prüft alle sechs Stunden und erneuert ab der eingestellten Zahl von Tagen vor Ablauf – auch wenn sich die Domainliste ändert.</li>
  <li>Mit <code>TLS_PORT</code> (z. B. 8443) startet der Container einen HTTPS-Listener, der erneuerte Zertifikate selbst nachlädt. Alternativ liegen Kette und Schlüssel in <code>data/tls/</code> für einen Reverse-Proxy. Heruntergeladen werden kann nur die öffentliche Kette, nie der Schlüssel.</li>
</ul>
<p class="help-tip">💡 Schlägt die Anforderung fehl, steht die Meldung der CA im Bereich „Letzter Lauf“ – meist ist Port 80 nicht erreichbar oder die CA-URL/das CA-Zertifikat falsch.</p>`,
  },
  {
    id: 'benachrichtigungen', group: 'Zusammenarbeit', title: 'Benachrichtigungen & Reports',
    summary: 'Glocke und E-Mail bei Zuteilung, Projektreports, Reports für Vorgesetzte und Kostenstellenverantwortliche.',
    html: `
<h2>Benachrichtigungen &amp; Reports</h2>
<h3>Bei Zuteilung</h3>
<p>Wird dir ein Vorgang oder Arbeitspaket zugeteilt (oder entzogen), erscheint es unter der <b>🔔 Glocke</b> in der oberen Leiste und – wenn der Mailversand eingerichtet ist – als <b>E-Mail</b>. Der Link öffnet direkt die Details des Vorgangs. Nach der Anmeldung geht es automatisch dorthin.</p>
<ul>
  <li>Voraussetzung: Deine <b>Ressource ist mit deinem Benutzer verknüpft</b> (Tab Ressourcen → Spalte <i>Benutzer</i>). Übernimmst du ein Paket selbst, bekommst du keine Nachricht.</li>
  <li>Deine <b>E-Mail-Adresse</b> trägst du unter <i>Verwaltung → Mein Konto</i> ein (bei AD-Konten kommt sie aus dem Verzeichnis). Dort schaltest du E-Mails auch ab; die Glocke bleibt.</li>
</ul>
<h3>Kommentare und @-Erwähnung</h3>
<p>Im Detaildialog eines Vorgangs gibt es unten <b>Kommentare</b>. Mit <b>@Name</b> (während des Tippens erscheinen Vorschläge) benachrichtigst du einen Projektbeteiligten gezielt; die Bearbeiter des Vorgangs erfahren ebenfalls von neuen Kommentaren. In der Tabelle zeigt <b>💬</b> die Anzahl. Löschen kann der Autor und der Verantwortliche. Leser sehen Kommentare, schreiben aber nicht.</p>
<h3>Automatische Erinnerungen</h3>
<ul>
  <li><b>Fällig:</b> Bearbeiter werden ein, zwei Tage vor dem Ende erinnert (Pool-Pakete ohne Bearbeiter: der Verantwortliche).</li>
  <li><b>Überfällig:</b> der Bearbeiter; nach einigen Tagen bekommt zusätzlich der Verantwortliche eine <b>Eskalation</b>.</li>
  <li><b>Blockiert:</b> ist ein Vorgang mehrere Tage blockiert, werden Verantwortlicher und Bearbeiter informiert (mit Grund).</li>
  <li>Jede Meldung kommt pro Vorgang und Termin nur <b>einmal</b>. Schwellen und Uhrzeit stellt der Administrator unter <i>Verwaltung → Erinnerungen</i> ein.</li>
</ul>
<h3>Projektreport</h3>
<p>Der Verantwortliche aktiviert ihn unter <b>Einstellungen → Automatischer Report</b>: Wochentag, Uhrzeit und Empfänger (Verantwortlicher oder alle Mitglieder). Der Report nennt Fortschritt, <b>überfällige</b> und <b>blockierte</b> Vorgänge, <b>anstehende</b> Termine (14 Tage), offene Pool-Pakete und – je Empfänger – die <b>eigenen offenen Vorgänge</b>, alles mit Links. <b>Vorschau</b> und <b>Jetzt senden</b> gibt es im selben Dialog.</p>
<h3>Übergreifende Reports</h3>
<ul>
  <li><b>Portfolio-Report</b> (für Vorgesetzte): alle oder ausgewählte Projekte mit Ampel, Fortschritt, Ende, Abweichung zum Basisplan, überfälligen und blockierten Vorgängen; optional mit Budget, Ist-Kosten und CPI.</li>
  <li><b>Kostenstellen-Report</b> (für Kostenstellenverantwortliche): je Projekt Budget, Plan, Ist und Rest der eigenen Kostenstelle, plus Summe. Es werden keine Vorgänge und keine anderen Kostenstellen gezeigt.</li>
  <li>Empfänger brauchen <b>keinen Projektzugriff</b>. Unter <b>Reports</b> (obere Leiste) sehen sie ihre Berichte online; per E-Mail kommen sie nach dem eingestellten Zeitplan.</li>
  <li>Einrichten: <i>Verwaltung → Reports</i> (nur Administratoren) – Report anlegen, Kostenstellen den Verantwortlichen zuordnen.</li>
</ul>
<p class="help-tip">💡 Der Mailversand (SMTP, Absender, öffentliche URL für die Links) wird unter <i>Verwaltung → Benachrichtigung (E-Mail)</i> eingerichtet und dort mit einer Testmail geprüft.</p>`,
  },
  {
    id: 'verlauf', group: 'Zusammenarbeit', title: 'Verlauf (Änderungsprotokoll)',
    summary: 'Nachvollziehen, wer was wann geändert hat.',
    html: `
<h2>Verlauf</h2>
<p>Der Tab <b>Verlauf</b> listet die letzten Änderungen am Projekt: Zeit (UTC), Benutzer, Aktion und Details (z. B. „Dauer 3 → 5“, „Dokument hochgeladen“, „Ist-Kosten-Import“).</p>
<ul>
  <li>Protokolliert werden Änderungen an Vorgängen, Abhängigkeiten, Ressourcen, Status, Basisplan, Mitgliedern, Budget und Dokumenten.</li>
  <li>Planänderungen lassen sich mit <b>↶ / Strg+Z</b> zurücknehmen (siehe „Gantt &amp; Vorgangstabelle“); für andere Änderungen hilft der Verlauf, sie gezielt von Hand zurückzusetzen.</li>
  <li>Arbeiten mehrere Personen gleichzeitig, aktualisiert sich die Ansicht automatisch innerhalb einer Sekunde. Bei gleichzeitiger Bearbeitung derselben Zelle gewinnt die zuletzt gespeicherte Änderung.</li>
</ul>`,
  },

  // ───────────────────────────── Referenz ─────────────────────────────
  {
    id: 'importexport', group: 'Referenz', title: 'Import & Export',
    summary: 'MS Project (XML), CSV für Excel, JSON.',
    html: `
<h2>Import &amp; Export</h2>
<h3>Export</h3>
<p>Im Gantt: <b>Export …</b></p>
<table>
  <tr><th>Format</th><th>Verwendung</th></tr>
  <tr><td><b>MS Project (XML)</b></td><td>MSPDI – lässt sich in MS Project öffnen: Vorgänge, Gliederung, Abhängigkeiten mit Verzögerung, Constraints, Ressourcen, Zuordnungen</td></tr>
  <tr><td><b>CSV (Excel)</b></td><td>Tabelle mit PSP, Name, Dauer, Termine, %, Vorgänger, Ressourcen, Puffer, kritisch (Semikolon, UTF-8)</td></tr>
  <tr><td><b>OpenPlan JSON</b></td><td>vollständiger Austausch zwischen OpenPlan-Instanzen</td></tr>
</table>
<h3>Import</h3>
<p>Projektliste → <b>Importieren …</b>: <code>.xml</code> (MS Project) oder <code>.json</code> (OpenPlan). Es entsteht immer ein <b>neues Projekt</b>, dessen Verantwortlicher du bist.</p>
<ul>
  <li>Aus MS Project werden Constraints außer „So früh wie möglich“, „Beginn frühestens“, „Muss beginnen am“ und „Ende spätestens“ zu „So früh wie möglich“.</li>
  <li>Inaktive Vorgänge werden übersprungen; Dauern werden in Arbeitstage (8 Stunden) umgerechnet.</li>
  <li>Kosten, Budget, Dokumente und Status werden nicht aus fremden Dateien übernommen (der Status wird aus dem Fortschritt abgeleitet).</li>
</ul>
<p class="help-tip">💡 Ist-Kosten sind nicht Teil des Projekt-Exports; dafür gibt es unter <i>Budget → Ist-Kosten</i> einen eigenen CSV-Export.</p>`,
  },
  {
    id: 'api', group: 'Referenz', title: 'API & Schnittstellen',
    summary: 'Swagger, API-Tokens, Webhooks – für Skripte und Fremdsysteme.',
    html: `
<h2>API &amp; Schnittstellen</h2>
<p>OpenPlan hat eine REST-API für Skripte und andere Systeme (z. B. Ansible, Checkmk, ServiceNow-Middleware, AutoPatch). Alles, was du in der Oberfläche tust, geht auch über die API.</p>
<h3>API-Dokumentation (Swagger)</h3>
<p>Administratoren öffnen sie über <b>Verwaltung → API-Doku ↗</b> (oder direkt <code>/docs</code>). Dort sind alle Endpunkte nach Themen gruppiert, mit Kurzbeschreibung, Feldern und der Möglichkeit, Aufrufe auszuprobieren (<b>Try it out</b>). Wurde die Seite aus einer angemeldeten OpenPlan-Sitzung geöffnet, nutzt „Try it out“ diese Anmeldung – <b>Änderungen sind echt</b>. Die maschinenlesbare Beschreibung (OpenAPI) liegt unter <code>/openapi.json</code>. Die Seite lädt nichts aus dem Internet.</p>
<table>
  <tr><th>Einstellung <code>API_DOCS</code></th><th>Wirkung</th></tr>
  <tr><td><code>1</code> (Standard)</td><td><code>/docs</code> und <code>/openapi.json</code> sind für jeden erreichbar, der den Server erreicht (die Endpunkte selbst brauchen weiter ein Token)</td></tr>
  <tr><td><code>admin</code></td><td>die Beschreibung ist nur für angemeldete Administratoren abrufbar</td></tr>
  <tr><td><code>0</code></td><td>Dokumentation ist abgeschaltet (404)</td></tr>
</table>
<p>Die Variable steht in der <code>.env</code> (Verwaltung → Server-Umgebung) und wirkt nach einem Neustart des Containers.</p>
<h3>Zugang für Skripte: API-Tokens</h3>
<p>Verwaltung → <b>API-Zugänge</b>: Name, Dienstkonto, Umfang (<b>nur lesen</b> oder <b>lesen und schreiben</b>), optional Projekte und Laufzeit. Das Token (<code>op_…</code>) wird <b>nur einmal</b> angezeigt. Das Dienstkonto hat keine Passwort-Anmeldung und muss im Projekt als Mitglied eingetragen sein. Ein Token lässt sich jederzeit widerrufen.</p>
<pre>curl -H "Authorization: Bearer op_…" https://&lt;server&gt;/api/projects</pre>
<h3>Webhooks und Rückmeldungen</h3>
<ul>
  <li><b>Verwaltung → Webhooks</b>: OpenPlan sendet Ereignisse (Statuswechsel, Blockade, Zuordnung, neues Gerät) signiert an eine <code>https://</code>-Adresse. Fehlgeschlagene Zustellungen werden wiederholt; das <b>Protokoll</b> zeigt jede Zustellung.</li>
  <li><b>Externe Referenzen</b> (Vorgangsdialog): z. B. die Nummer eines ServiceNow-Changes oder eines Ansible-Jobs mit Link. Skripte finden Vorgänge per Hostname oder Referenz.</li>
  <li><b>Rückmeldung</b>: ein Fremdsystem setzt Status, Fortschritt und Notiz eines Vorgangs und hängt dabei eine Referenz an.</li>
  <li><b>AutoPatch</b> meldet nach Patch- und CVE-Jobs je Server zurück; OpenPlan ordnet den Server per Hostname und DNS einem Gerät zu.</li>
</ul>
<p class="help-tip">💡 Eine ausführliche Anleitung mit Beispielen und der Signaturprüfung steht im Repository unter <code>docs/integration-api.md</code>.</p>`,
  },
  {
    id: 'tastatur', group: 'Referenz', title: 'Tastenkürzel & Tipps',
    summary: 'Schneller arbeiten.',
    html: `
<h2>Tastenkürzel &amp; Tipps</h2>
<table>
  <tr><th>Taste</th><th>Wirkung</th></tr>
  <tr><td><code>F1</code> oder <code>?</code></td><td>Hilfe zur aktuellen Seite öffnen/schließen</td></tr>
  <tr><td><code>Esc</code></td><td>Hilfe schließen, Zellbearbeitung abbrechen</td></tr>
  <tr><td><code>Einfg</code></td><td>Neuen Vorgang hinter der Auswahl einfügen</td></tr>
  <tr><td><code>Entf</code></td><td>Markierten Vorgang löschen (mit Rückfrage)</td></tr>
  <tr><td><code>Alt</code>+<code>→</code> / <code>←</code></td><td>Einrücken / Ausrücken</td></tr>
  <tr><td><code>Alt</code>+<code>↑</code> / <code>↓</code></td><td>Nach oben / unten verschieben</td></tr>
  <tr><td><code>Strg</code>+Klick / <code>Umschalt</code>+Klick</td><td>Mehrfachauswahl</td></tr>
  <tr><td><code>Strg</code>+<code>Z</code> / <code>Strg</code>+<code>Y</code></td><td>Planänderung rückgängig / wiederholen</td></tr>
  <tr><td><code>Enter</code></td><td>Zellbearbeitung übernehmen</td></tr>
</table>
<h3>Tipps</h3>
<ul>
  <li>Dauer eintragen, nicht Enddatum – der Plan rechnet das Ende selbst.</li>
  <li>Abhängigkeiten statt fester Termine: Verschiebt sich ein Vorgänger, zieht der Rest automatisch nach.</li>
  <li>Plan freigeben → <b>Basisplan setzen</b> → im Alltag nur noch Status/Fortschritt pflegen.</li>
  <li><b>Smartphone:</b> Die Kopfzeile wird zum Menü (☰). Im Projekt zeigt der Gantt-Tab eine <b>Liste</b> aus Karten (Tippen öffnet die Details, der Kreis links setzt erledigt/offen); mit <b>Zeitachse</b> wechselst du zum Gantt-Diagramm, unter <b>Werkzeuge</b> stehen Filter, Basisplan und Export. Die Reiter lassen sich seitlich wischen.</li>
  <li>Die Seite ist als <b>App installierbar</b> (Browser-Menü „Installieren“) und zeigt zuletzt geladene Daten auch offline an.</li>
  <li>Sprache (DE/EN) und Darstellung (automatisch, hell, dunkel) stellt jeder Benutzer selbst über die Schaltflächen in der oberen Leiste ein; die Auswahl wird im Profil gespeichert.</li>
</ul>`,
  },
  {
    id: 'faq', group: 'Referenz', title: 'Häufige Fragen',
    summary: 'Warum geht … nicht? Warum ist alles rot?',
    html: `
<h2>Häufige Fragen</h2>
<h3>Ich kann bei einer Phase (z. B. PSP 1) die Dauer nicht ändern.</h3>
<p>Phasen sind Sammelvorgänge: Dauer, Ende und Fortschritt ergeben sich aus den Teilvorgängen. Ändere die Teilvorgänge – oder ändere den <b>Beginn</b> der Phase bzw. ziehe den Sammelbalken, um die ganze Phase zu verschieben.</p>
<h3>Warum ist fast alles rot?</h3>
<p><b>Gesamtpuffer</b> = Arbeitstage, die ein Vorgang rutschen darf, ohne das <i>Projektende</i> zu verschieben; <b>freier Puffer</b> = Arbeitstage, die er rutschen darf, ohne einen <i>Nachfolger</i> zu verschieben (immer ≤ Gesamtpuffer). Bei Sammelvorgängen steht der kleinste Gesamtpuffer ihrer Teilvorgänge. Gerechnet wird nach Projektkalender – Abwesenheiten von Ressourcen verändern die Puffer nicht.</p>
<p>Rot = kritischer Pfad (Puffer 0). In linearen Plänen liegt fast alles darauf. Mit dem Haken <b>Kritischer Pfad</b> blendest du die Färbung aus. Parallele Arbeit schafft Puffer.</p>
<h3>Ich verschiebe einen Balken nach links, aber nichts passiert.</h3>
<p>Ein Vorgang kann nicht vor seinen Vorgänger. Wähle im Detaildialog <b>Manuell: Beginn am (fest)</b>, wenn du das bewusst willst. Die Meldung unter dem Balken erklärt die Begrenzung.</p>
<h3>Der Beginn eines Vorgangs springt nach dem Eintragen auf ein anderes Datum.</h3>
<p>Fällt das Datum auf ein Wochenende oder einen Feiertag, rutscht der Beginn auf den nächsten Arbeitstag.</p>
<h3>Ich sehe den Tab „Budget“ nicht.</h3>
<p>Kosten sind für Verantwortliche und Admins reserviert. Bitte den Verantwortlichen um Freigabe (Budget &amp; Stammdaten → Sichtbarkeit).</p>
<h3>Ein Projekt ist verschwunden.</h3>
<p>Entweder wurde die Mitgliedschaft entfernt, die Verantwortung übertragen oder das Projekt gelöscht. Frage den Verantwortlichen.</p>
<h3>Warum steht ein erledigter Vorgang plötzlich auf 90 %?</h3>
<p>Du hast ihn von „Erledigt“ auf „In Arbeit“ oder „Blockiert“ gesetzt. 100 % passt nicht zu „nicht fertig“, daher 90 %.</p>
<h3>Der Ist-Import meldet „Kostenstelle … unbekannt“.</h3>
<p>Lege die Kostenstelle unter <b>Budget &amp; Stammdaten</b> an, importiere die Stammdaten-Liste oder aktiviere im Import „unbekannte Kostenstellen/-arten automatisch anlegen“.</p>
<h3>Hochladen eines Dokuments wird abgelehnt.</h3>
<p>Mögliche Gründe: größer als das Limit (25 MB), leere Datei, nicht erlaubter Typ (ausführbar, HTML, SVG) oder du hast nur Leserechte. Alternativ: Link zur Datei in OneDrive anhängen.</p>`,
  },
]

/** Themen in der aktuellen Sprache (Gruppe bleibt der deutsche Schlüssel und wird beim Anzeigen übersetzt). */
const topicsEn: Topic[] = topicsDe.map(t => (helpEn[t.id] ? { ...t, ...helpEn[t.id] } : t))
const current = computed(() => (lang.value === 'en' ? topicsEn : topicsDe))
export const getTopics = () => current.value
export const getTopic = (id: string) => current.value.find(t => t.id === id)

/** Kontext → Thema: Route, Projekt-Tab und Budget-Unterreiter bestimmen die passende Hilfeseite. */
export function contextTopic(path: string, tab: string, sub: string): string {
  if (path.startsWith('/project/')) {
    if (tab === 'budget') return ({ overview: 'budget-uebersicht', plan: 'budget-plan', actuals: 'budget-ist', master: 'budget-stamm' } as Record<string, string>)[sub] ?? 'budget-uebersicht'
    return ({ gantt: 'gantt', team: 'team', board: 'board', packages: 'pakete', devices: 'geraete', calendar: 'kalender', resources: 'ressourcen', org: 'ressourcen', journal: 'verlauf' } as Record<string, string>)[tab] ?? 'gantt'
  }
  if (path === '/admin') return 'verwaltung'
  if (path === '/todo') return 'todo'
  if (path === '/overview') return 'uebersicht'
  if (path === '/dashboard') return 'dashboard'
  if (path === '/absences' || path === '/org') return 'ressourcen'
  if (path.startsWith('/help')) return 'start'
  return 'projekte'
}

const strip = (html: string) => html.replace(/<[^>]+>/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/\s+/g, ' ').trim()
const plainCache = { de: new Map(topicsDe.map(t => [t.id, strip(t.html)])), en: new Map(topicsEn.map(t => [t.id, strip(t.html)])) }
const plain = () => plainCache[lang.value]

export interface Hit { topic: Topic; score: number; snippet: string }
/** Volltextsuche über alle Themen (Titel zählt mehr als Text). */
export function search(q: string): Hit[] {
  const terms = q.toLowerCase().split(/\s+/).filter(t => t.length >= 2)
  if (!terms.length) return []
  const hits: Hit[] = []
  for (const t of getTopics()) {
    const text = plain().get(t.id)!, low = text.toLowerCase(), title = (t.title + ' ' + t.summary).toLowerCase()
    let score = 0
    let all = true
    for (const term of terms) {
      const inTitle = title.includes(term), n = low.split(term).length - 1
      if (!inTitle && n === 0) { all = false; break }
      score += (inTitle ? 10 : 0) + Math.min(n, 5)
    }
    if (!all) continue
    const at = Math.max(low.indexOf(terms[0]), 0)
    const start = Math.max(at - 40, 0)
    hits.push({ topic: t, score, snippet: (start > 0 ? '… ' : '') + text.slice(start, start + 140) + (start + 140 < text.length ? ' …' : '') })
  }
  return hits.sort((a, b) => b.score - a.score)
}

/** Markiert Suchbegriffe im HTML (nur in Textknoten, nie in Tags). */
export function highlight(html: string, q: string): string {
  const terms = q.toLowerCase().split(/\s+/).filter(t => t.length >= 2).map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  if (!terms.length) return html
  const re = new RegExp('(' + terms.join('|') + ')', 'gi')
  return html.split(/(<[^>]+>)/g).map(p => (p.startsWith('<') ? p : p.replace(re, '<mark>$1</mark>'))).join('')
}
