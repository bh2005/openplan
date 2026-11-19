"""Muster-Excel für den Geräteliste-Import – wird live aus der Vorlagen-Bibliothek erzeugt.

Die Auswahlliste „Gerätetyp“, das Blatt „Schritte (Vorlagen)“ und die Rollen entsprechen immer den aktuell gepflegten Vorlagen;
die Beispielzeilen verwenden vorhandene Gerätetypen und lassen sich ohne Änderung importieren (Kostenstelle 100200 / Kostenart 400100
ggf. mit „unbekannte Kostenstellen/-arten anlegen“).
"""
from __future__ import annotations

import datetime as dt
import io
from typing import Any, Dict, List

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

F = "Arial"
LASTROW = 500
FILL = {"pflicht": "1F3864", "geraet": "2F6DB5", "plan": "2E7D32", "kosten": "C55A11", "zust": "6B7280", "pruef": "9CA3AF"}
_thin = Side(style="thin", color="D0D5DD")
BOX = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)
BASE = Font(name=F, size=10)
BOLD = Font(name=F, size=10, bold=True)
WHITE = Font(name=F, size=10, bold=True, color="FFFFFF")

# (Überschrift, Gruppe, Breite, Hinweis) – Reihenfolge = Spalten A…W
COLS = [
    ("Hostname *", "pflicht", 18, "Pflicht. Eindeutig, ohne Leerzeichen. Schlüssel für Dublettenschutz und Nachimport."),
    ("Standort *", "pflicht", 22, "Pflicht. Wird zur Phase (Gruppe) im Projektplan."),
    ("Gerätetyp *", "pflicht", 15, "Pflicht. Wählt die Vorlage mit den Arbeitsschritten (Auswahlliste, siehe Blatt „Schritte (Vorlagen)“)."),
    ("Neues Modell (Bestellartikel)", "geraet", 24, "Artikel, der bestellt wird."),
    ("Altgerät Hostname", "geraet", 18, "Falls das Altgerät anders heißt."),
    ("Altgerät Modell", "geraet", 18, ""),
    ("Gebäude / Raum", "geraet", 18, ""),
    ("Rack / HE", "geraet", 12, "Position im Rack, z. B. R3 / HE 12."),
    ("Management-IP", "geraet", 15, ""),
    ("Konfigurationsprofil", "geraet", 20, "z. B. Access-24, Core, VLAN-Set Werk."),
    ("Seriennummer (neu)", "geraet", 18, "Wird meist erst nach der Lieferung ergänzt."),
    ("Wartungsfenster von", "plan", 14, "Datum TT.MM.JJJJ. Frühester Beginn des Schritts mit Schalter „Fenster“."),
    ("Wartungsfenster bis", "plan", 14, "Datum TT.MM.JJJJ. Frist des Schritts mit Schalter „Fenster“."),
    ("Priorität", "plan", 11, "Hoch / Mittel / Niedrig."),
    ("Lieferzeit (Tage)", "plan", 12, "Optional. Überschreibt die Wartezeit des Schritts mit Schalter „Lieferzeit“ (Arbeitstage)."),
    ("Preis netto (EUR)", "kosten", 14, "Wird als Plankosten am Schritt mit Schalter „Preis“ gebucht (Kostenrecht nötig)."),
    ("Kostenstelle", "kosten", 14, "Code der Kostenstelle (führende Nullen egal)."),
    ("Kostenart", "kosten", 12, "Code der Kostenart."),
    ("Bestellreferenz", "kosten", 16, "z. B. SAP-Bestellnummer."),
    ("Ansprechpartner vor Ort", "zust", 22, ""),
    ("Verantwortlich (Benutzer)", "zust", 20, "OpenPlan-Benutzername (Bearbeiter des Projekts): bekommt alle Schritte, die nicht über eine Rolle zugeordnet werden."),
    ("Bemerkung", "zust", 28, ""),
    ("Prüfung (nicht importiert)", "pruef", 26, "Automatische Plausibilitätsprüfung – nicht ausfüllen."),
]
D = dt.date
# (Hostname, Standort, Typ-Index 0..2, Modell, Altgerät-Host, Altgerät-Modell, Raum, Rack, IP, Profil, von, bis, Prio, Lieferzeit, Preis, KST, KA, Bestellref, Ansprechpartner)
EXAMPLES = [
    ("sw-kas-z-01", "Zentrale Kassel", 0, "Extreme 5520-24T", "sw-kas-alt-01", "Cisco C2960X-24", "Geb. A / R1.12", "R3 / HE 12", "10.20.1.11", "Access-24", D(2026, 11, 2), D(2026, 11, 6), "Hoch", 15, 3890.00, "100200", "400100", "4500012345", "M. Beispiel"),
    ("sw-kas-z-02", "Zentrale Kassel", 0, "Extreme 5520-24T", "sw-kas-alt-02", "Cisco C2960X-24", "Geb. A / R1.12", "R3 / HE 14", "10.20.1.12", "Access-24", D(2026, 11, 2), D(2026, 11, 6), "Hoch", 15, 3890.00, "100200", "400100", "4500012345", "M. Beispiel"),
    ("sw-kas-z-03", "Zentrale Kassel", 0, "Extreme 5520-48T", "sw-kas-alt-03", "Cisco C3850-48", "Geb. B / R2.03", "R1 / HE 20", "10.20.1.13", "Core-Access", D(2026, 11, 2), D(2026, 11, 6), "Hoch", 15, 5290.00, "100200", "400100", "4500012345", "M. Beispiel"),
    ("sw-hat-01", "Werk Hattorf", 0, "Extreme 5520-24T", "sw-hat-alt-01", "Cisco C2960X-24", "Halle 3 / SR1", "R1 / HE 8", "10.30.1.11", "Access-24", D(2026, 11, 16), D(2026, 11, 20), "Mittel", 15, 3890.00, "100300", "400100", "4500012346", "T. Muster"),
    ("sw-hat-02", "Werk Hattorf", 0, "Extreme 5520-24T", "sw-hat-alt-02", "Cisco C2960X-24", "Halle 3 / SR1", "R1 / HE 10", "10.30.1.12", "Access-24", D(2026, 11, 16), D(2026, 11, 20), "Mittel", 15, 3890.00, "100300", "400100", "4500012346", "T. Muster"),
    ("ap-hat-01", "Werk Hattorf", 1, "Extreme AP410C", None, "Cisco AIR-AP2802", "Halle 3 / Decke", None, "10.30.8.21", "WLAN-Werk", D(2026, 11, 16), D(2026, 11, 20), "Niedrig", 20, 640.00, "100300", "400200", "4500012346", "T. Muster"),
    ("sw-neu-01", "Werk Nord", 0, "Extreme 5520-24T", "sw-neu-alt-01", "Cisco C2960X-24", "Verwaltung / R0.01", "R1 / HE 5", "10.40.1.11", "Access-24", D(2026, 11, 30), D(2026, 12, 4), "Mittel", 15, 3890.00, "100400", "400100", "4500012347", "S. Probe"),
    ("fw-neu-01", "Werk Nord", 2, "Fortinet FG-100F", "fw-neu-alt-01", "Fortinet FG-100E", "Verwaltung / R0.01", "R1 / HE 1", "10.40.0.1", "FW-Standort", D(2026, 12, 1), D(2026, 12, 2), "Hoch", 25, 5150.00, "100400", "400100", "4500012347", "S. Probe"),
]


def _bezug(s: Dict[str, Any]) -> str:
    parts = []
    if s["books_price"]:
        parts.append("Preis / Kostenstelle / Kostenart → Plankosten")
    if s["takes_lead"]:
        parts.append("Lieferzeit (Tage) überschreibt die Wartezeit nach diesem Schritt")
    if s["uses_window"]:
        parts.append("Wartungsfenster von = Beginn frühestens, bis = Frist")
    return "; ".join(parts)


def build(templates: List[Dict[str, Any]]) -> bytes:
    """``templates``: Liste von {name, category, steps:[{position,name,role,duration,wait_days,pred_pos,books_price,uses_window,takes_lead}]}."""
    names = [t["name"] for t in templates] or ["Switch"]
    roles = sorted({s["role"] for t in templates for s in t["steps"] if s["role"]})
    wb = Workbook()
    wsA, ws, wsS, wsL = wb.active, None, None, None
    wsA.title = "Anleitung"
    ws = wb.create_sheet("Geräteliste")
    wsS = wb.create_sheet("Schritte (Vorlagen)")
    wsL = wb.create_sheet("Listen")

    # Listen
    lists = {"Gerätetyp": names, "Priorität": ["Hoch", "Mittel", "Niedrig"], "Rolle": roles}
    for c, (h, vals) in enumerate(lists.items(), 1):
        wsL.cell(1, c, h).font, wsL.cell(1, c).fill = WHITE, PatternFill("solid", fgColor=FILL["zust"])
        for r, v in enumerate(vals, 2):
            wsL.cell(r, c, v).font = BASE
        wsL.column_dimensions[get_column_letter(c)].width = 22
    wsL["E1"] = "Hinweis: Die Auswahllisten der Geräteliste kommen von hier und spiegeln die Vorlagen in OpenPlan (Menü „Vorlagen“)."
    wsL["E1"].font = Font(name=F, size=9, italic=True, color="6B7280")

    # Geräteliste
    for c, (h, g, w, tip) in enumerate(COLS, 1):
        cell = ws.cell(1, c, h)
        cell.font, cell.fill = WHITE, PatternFill("solid", fgColor=FILL[g])
        cell.alignment, cell.border = Alignment(wrap_text=True, vertical="center", horizontal="center"), BOX
        ws.column_dimensions[get_column_letter(c)].width = w
        if tip:
            cell.comment = Comment(tip, "OpenPlan")
    ws.row_dimensions[1].height = 42
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = "A1:%s%d" % (get_column_letter(len(COLS)), LASTROW)
    pick = []
    for i, want in enumerate(("Switch", "Access Point", "Firewall")):
        pick.append(next((n for n in names if n.lower() == want.lower()), names[min(i, len(names) - 1)]))
    for r, e in enumerate(EXAMPLES, 2):
        row = [e[0], e[1], pick[e[2]], e[3], e[4], e[5], e[6], e[7], e[8], e[9], None, e[10], e[11], e[12], e[13], e[14], e[15], e[16], e[17], e[18], None,
               "Beispiel – vor dem Import löschen" if r == 2 else None]
        for c, v in enumerate(row, 1):
            cell = ws.cell(r, c, v)
            cell.font, cell.border = BASE, BOX
            if isinstance(v, dt.date):
                cell.number_format = "DD.MM.YYYY"
            if c == 16:
                cell.number_format = '#,##0.00 "€"'
    for r in range(len(EXAMPLES) + 2, LASTROW + 1):
        for c in range(1, len(COLS) + 1):
            cell = ws.cell(r, c)
            cell.font, cell.border = BASE, BOX
            if c in (12, 13):
                cell.number_format = "DD.MM.YYYY"
            if c == 16:
                cell.number_format = '#,##0.00 "€"'
    W = len(COLS)
    for r in range(2, LASTROW + 1):
        ws.cell(r, W, '=IF(A%d="","",IF(COUNTIF($A$2:$A$%d,A%d)>1,"Hostname doppelt",IF(OR(B%d="",C%d=""),"Standort/Gerätetyp fehlt",IF(AND(L%d<>"",M%d<>"",L%d>M%d),"Fenster: von nach bis",IF(AND(P%d<>"",NOT(ISNUMBER(P%d))),"Preis keine Zahl","OK")))))'
                % (r, LASTROW, r, r, r, r, r, r, r, r, r))
        cell = ws.cell(r, W)
        cell.font, cell.border, cell.fill = Font(name=F, size=10, color="6B7280"), BOX, PatternFill("solid", fgColor="F3F4F6")

    def dv(kind, f1, rng, msg, f2=None, op=None):
        v = DataValidation(type=kind, formula1=f1, formula2=f2, operator=op, allow_blank=True, showErrorMessage=True, errorTitle="Eingabe prüfen", error=msg)
        ws.add_data_validation(v)
        v.add(rng)

    dv("list", "=Listen!$A$2:$A$%d" % (len(names) + 1), "C2:C%d" % LASTROW, "Bitte einen Gerätetyp aus der Liste wählen (Vorlagen in OpenPlan pflegen).")
    dv("list", "=Listen!$B$2:$B$4", "N2:N%d" % LASTROW, "Hoch, Mittel oder Niedrig.")
    dv("date", "36526", "L2:M%d" % LASTROW, "Bitte ein Datum eingeben (TT.MM.JJJJ).", op="greaterThan")
    dv("whole", "0", "O2:O%d" % LASTROW, "Ganze Zahl 0–365.", f2="365", op="between")
    dv("decimal", "0", "P2:P%d" % LASTROW, "Preis als Zahl ≥ 0 (ohne Währungszeichen).", op="greaterThanOrEqual")
    dv("custom", '=ISERROR(FIND(" ",A2))', "A2:A%d" % LASTROW, "Der Hostname darf keine Leerzeichen enthalten.")
    red = PatternFill("solid", bgColor="F8B4B4", fgColor="F8B4B4")
    ws.conditional_formatting.add("A2:A%d" % LASTROW, FormulaRule(formula=['AND($A2<>"",COUNTIF($A$2:$A$%d,$A2)>1)' % LASTROW], fill=red))
    ws.conditional_formatting.add("B2:C%d" % LASTROW, FormulaRule(formula=['AND($A2<>"",B2="")'], fill=red))
    ws.conditional_formatting.add("L2:M%d" % LASTROW, FormulaRule(formula=['AND($L2<>"",$M2<>"",$L2>$M2)'], fill=red))
    wl = get_column_letter(W)
    ws.conditional_formatting.add("%s2:%s%d" % (wl, wl, LASTROW), FormulaRule(formula=['AND(%s2<>"",%s2<>"OK")' % (wl, wl)], fill=red, font=Font(name=F, color="9B1C1C", bold=True)))

    # Schritte (Vorlagen)
    hdr = ["Vorlage (= Gerätetyp)", "Nr", "Arbeitsschritt", "Rolle", "Dauer (Arbeitstage)", "Wartezeit danach (Tage)", "Vorgänger (Nr)", "Bezug zur Geräteliste"]
    for c, h in enumerate(hdr, 1):
        cell = wsS.cell(1, c, h)
        cell.font, cell.fill = WHITE, PatternFill("solid", fgColor=FILL["pflicht"])
        cell.alignment, cell.border = Alignment(wrap_text=True, vertical="center", horizontal="center"), BOX
    wsS.row_dimensions[1].height = 34
    r = 2
    for t in templates:
        for s in t["steps"]:
            for c, v in enumerate([t["name"], s["position"], s["name"], s["role"], s["duration"], s["wait_days"], s["pred_pos"] or "", _bezug(s)], 1):
                cell = wsS.cell(r, c, v)
                cell.font, cell.border, cell.alignment = BASE, BOX, Alignment(wrap_text=True, vertical="top")
            r += 1
    for c, w in enumerate([20, 6, 44, 16, 12, 14, 12, 56], 1):
        wsS.column_dimensions[get_column_letter(c)].width = w
    wsS.freeze_panes = "A2"
    wsS.auto_filter.ref = "A1:H%d" % max(r - 1, 2)
    wsS.cell(r + 1, 1, "Hinweis: Dieses Blatt zeigt die aktuellen Vorlagen aus OpenPlan (Menü „Vorlagen“) und dient nur der Information – es wird nicht importiert. Der Gerätetyp in der Geräteliste wählt die Vorlage anhand ihres Namens.").font = Font(name=F, size=9, italic=True, color="6B7280")

    # Anleitung
    wsA.column_dimensions["A"].width = 26
    wsA.column_dimensions["B"].width = 100
    wsA.cell(1, 1, "Geräteliste für den OpenPlan-Import").font = Font(name=F, size=14, bold=True, color=FILL["pflicht"])
    wsA.row_dimensions[1].height = 26
    wsA.cell(2, 1, "Erzeugt am %s aus den aktuellen Vorlagen in OpenPlan." % dt.date.today().strftime("%d.%m.%Y")).font = Font(name=F, size=9, italic=True, color="6B7280")
    rows = [
        ("Zweck", "Aus dieser Liste legt OpenPlan für jedes Gerät die Arbeitsschritte seiner Vorlage an (bestellen, liefern, kommissionieren, konfigurieren, austauschen, testen …). Struktur im Plan: Standort (Phase) → Gerät → Schritte."),
        ("Eine Zeile = ein Gerät", "Blatt „Geräteliste“, Überschriften in Zeile 1, Daten ab Zeile 2 (bis Zeile %d). Die Beispielzeilen 2–9 sind fiktiv und lassen sich zum Ausprobieren direkt importieren – für echte Daten löschen oder überschreiben." % LASTROW),
        ("Pflichtangaben", "Nur drei Spalten sind Pflicht: Hostname, Standort, Gerätetyp (dunkelblau, mit *). Alles andere ist optional und kann auch später (per erneutem Import) ergänzt werden."),
        ("Farben der Überschriften", None),
        ("Hostname = Schlüssel", "Muss eindeutig sein. Beim erneuten Import werden vorhandene Hostnamen erkannt: Neue Geräte (Nachlieferungen) werden ergänzt, Stammdaten (z. B. Modell, IP) und Wartungsfenster aktualisiert, der erreichte Status bleibt unangetastet."),
        ("Formate", "Datum TT.MM.JJJJ · Preis als Zahl mit Komma/Punkt, ohne Währungszeichen · Kostenstelle/Kostenart als Code (führende Nullen egal) · Spaltennamen dürfen abweichen – im Import ordnest du sie zu."),
        ("Prüfspalte", "Die letzte Spalte prüft live: doppelter Hostname, fehlender Standort/Gerätetyp, Wartungsfenster „von nach bis“, Preis keine Zahl. Zeilen mit Fehlern sind rot. Diese Spalte wird nicht importiert."),
        ("Lieferzeit", "Die Spalte „Lieferzeit (Tage)“ überschreibt die Wartezeit des Schritts mit Schalter „Lieferzeit“ in der Vorlage (Arbeitstage)."),
        ("Wartungsfenster", "„von“ wird zum frühesten Beginn und „bis“ zur Frist des Schritts mit Schalter „Fenster“ (Erledigungszeitraum). Liegt das geplante Ende später, warnt OpenPlan mit ⚠ und erinnert/eskaliert nach der Frist."),
        ("Kosten", "Der Preis wird als Plankosten am Schritt mit Schalter „Preis“ gebucht (mit Kostenstelle/Kostenart); so erscheinen die Geräte im Budget und im Kostenstellen-Report. Unbekannte Kostenstellen/-arten legt der Import auf Wunsch an."),
        ("Verantwortlich", "Reihenfolge der Zuordnung: Rollen, denen du beim Import eine Ressource zuweist (z. B. Einkauf), haben Vorrang; alle übrigen Schritte des Geräts gehen an den hier eingetragenen OpenPlan-Benutzer (Benachrichtigung per Glocke/E-Mail); ohne beides liegen sie als Pool-Pakete zur Selbstübernahme bereit."),
        ("Weitere Blätter", "„Schritte (Vorlagen)“: aktuelle Arbeitsschritte je Gerätetyp (Rolle, Dauer, Wartezeit, Vorgänger). „Listen“: Auswahllisten (Gerätetypen = Vorlagen, Priorität, Rollen)."),
    ]
    r = 4
    for a, b in rows:
        wsA.cell(r, 1, a).font = BOLD
        wsA.cell(r, 1).alignment = Alignment(vertical="top", wrap_text=True)
        if b is None:
            for key, label in [("pflicht", "Pflicht (Hostname, Standort, Gerätetyp)"), ("geraet", "Gerätedaten"), ("plan", "Planung (Wartungsfenster, Priorität, Lieferzeit)"),
                               ("kosten", "Kosten (Preis, Kostenstelle, Kostenart, Bestellreferenz)"), ("zust", "Zuständigkeit / Bemerkung"), ("pruef", "Automatische Prüfung (nicht ausfüllen)")]:
                wsA.cell(r, 1, "").fill = PatternFill("solid", fgColor=FILL[key])
                wsA.cell(r, 2, label).font = BASE
                r += 1
            continue
        wsA.cell(r, 2, b).font = BASE
        wsA.cell(r, 2).alignment = Alignment(wrap_text=True, vertical="top")
        wsA.row_dimensions[r].height = max(18, 15 * (len(b) // 95 + 1))
        r += 1
    wsA.sheet_view.showGridLines = False
    wb.active = wb.sheetnames.index("Geräteliste")
    for s in wb.worksheets:
        s.sheet_view.tabSelected = (s.title == "Geräteliste")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
