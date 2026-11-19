"""Beispielprojekt: Netzwerk-Rollout – Umbau von Cisco auf Extreme Networks.

3 Mitarbeitende, 4 Standorte, 60 Geräte (4 Core, 8 Distribution, 40 Access, 8 WLAN-APs).
Das Projekt startet 6 Wochen in der Vergangenheit, bekommt einen Basisplan, dann Verzug,
Fortschritt, eine Blockade und Ist-Kosten – so zeigen alle Ansichten (Gantt/Tracking, Team,
Kalender, Budget) sofort sinnvolle Daten. Alle Termine hängen am heutigen Datum.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import budget
import cpm
import finance_api
import service as svc

MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
          "November", "Dezember"]
PERSONAL, HARDWARE, LICENSE, EXTERN, TRAINING, DISPOSAL = "600000", "410000", "420000", "400000", "430000", "440000"


def create_demo_project(db, user: Dict[str, Any], today: Optional[date] = None) -> int:
    import api  # lokal: api importiert dieses Modul

    today = today or date.today()
    start = today - timedelta(days=42)
    start -= timedelta(days=start.weekday())                       # Montag vor 6 Wochen
    holidays = ["2026-12-24", "2026-12-25", "2026-12-26", "2026-12-31", "2027-01-01"]
    desc = ("Austausch von 60 Cisco-Geräten gegen Extreme Networks an 4 Standorten mit 3 Mitarbeitern. "
            "Beispielprojekt: enthält Basisplan mit Verzug, eine Blockade (Lieferung) und – bewusst – eine "
            "Überlastung von Anna Becker während der Werk-Nord-Abnahme.")
    pid = db.execute(
        "INSERT INTO projects(name, description, start_date, work_days, holidays, owner_id) VALUES (?,?,?,?,?,?)",
        ("Beispiel: Netzwerk-Rollout Cisco → Extreme", desc, start.isoformat(), "0,1,2,3,4", ",".join(holidays),
         user["id"])).lastrowid

    # ── Stammdaten ──────────────────────────────────────────────────────────
    def master(table: str, rows: List[Tuple[str, str]]) -> Dict[str, int]:
        return {c: db.execute("INSERT INTO %s(project_id, code, name) VALUES (?,?,?)" % table, (pid, c, n)).lastrowid
                for c, n in rows}

    cc = master("cost_centers", [("0000100200", "IT Netzwerk & Infrastruktur"), ("0000400100", "Standort Zentrale"),
                                 ("0000400200", "Standort Werk Nord"), ("0000400300", "Standort Werk Süd"),
                                 ("0000400400", "Standort Logistikzentrum")])
    ct = master("cost_types", [(EXTERN, "Fremdleistungen"), (HARDWARE, "Hardware & Material"),
                               (LICENSE, "Lizenzen & Software"), (TRAINING, "Schulung"), (DISPOSAL, "Entsorgung"),
                               (PERSONAL, "Interne Leistungsverrechnung")])
    IT = cc["0000100200"]

    def resource(name: str, rate: float) -> int:
        return db.execute("INSERT INTO resources(project_id, name, max_units, cost_rate, cost_center_id, cost_type_id) "
                          "VALUES (?,?,100,?,?,?)", (pid, name, rate, IT, ct[PERSONAL])).lastrowid

    A = resource("Anna Becker (Netzwerk-Lead)", 680)
    B = resource("Ben Krause (Netzwerktechniker)", 540)
    C = resource("Chris Vogel (Netzwerktechniker)", 520)

    # ── Vorgänge ────────────────────────────────────────────────────────────
    pos: Dict[Optional[int], int] = {}
    ids: Dict[str, int] = {}

    def task(key: str, name: str, dur: int = 0, parent: Optional[str] = None, res: Tuple = (),
             pred: Tuple = (), items: Tuple = (), notes: str = "") -> int:
        par = ids[parent] if parent else None
        p = pos.get(par, 0)
        pos[par] = p + 1
        tid = db.execute("INSERT INTO tasks(project_id, parent_id, position, name, duration, notes) VALUES (?,?,?,?,?,?)",
                         (pid, par, p, name, dur, notes)).lastrowid
        ids[key] = tid
        for r, units in res:
            db.execute("INSERT INTO assignments(task_id, resource_id, units) VALUES (?,?,?)", (tid, r, units))
        for pr in pred:
            pk, typ, lag = (pr + ("FS", 0))[:3] if isinstance(pr, tuple) else (pr, "FS", 0)
            db.execute("INSERT INTO deps(project_id, pred_id, succ_id, type, lag) VALUES (?,?,?,?,?)",
                       (pid, ids[pk], tid, typ, lag))
        for desc_, amount, typ_code, cc_id in items:
            db.execute("INSERT INTO cost_items(project_id, task_id, cost_type_id, cost_center_id, amount, description) "
                       "VALUES (?,?,?,?,?,?)", (pid, tid, ct[typ_code], cc_id, amount, desc_))
        return tid

    task("P1", "Projektmanagement")
    task("pm1", "Kick-off & Projektplanung", 3, "P1", [(A, 60)])
    task("pm2", "Projektsteuerung & Statusmeetings", 60, "P1", [(A, 10)], ["pm1"])

    task("P2", "Konzeption & Vorbereitung")
    task("k1", "Bestandsaufnahme Cisco-Infrastruktur (60 Geräte, 4 Standorte)", 5, "P2", [(B, 100), (C, 100)], ["pm1"],
         notes="Ports, VLANs, PoE-Last, Uplinks und Konfigurationen sichern.")
    task("k2", "Zielarchitektur Extreme (VLAN-/IP-Konzept, Stacking, WLAN)", 6, "P2", [(A, 90)], ["k1"])
    task("k3", "Migrationskonzept & Rollback-Plan", 4, "P2", [(A, 90)], ["k2"])
    task("k4", "Wartungsfenster mit Fachbereichen abstimmen", 3, "P2", [(B, 50)], ["k2"])
    task("k5", "Freigabe Konzept", 0, "P2", (), ["k3", "k4"])

    task("P3", "Beschaffung & Logistik")
    task("b1", "Bestellung Extreme-Hardware & Lizenzen", 5, "P3", [(A, 20)], ["k5"], [
        ("Core-Switches 4 × 14.500 €", 58000, HARDWARE, IT), ("Distribution-Switches 8 × 5.200 €", 41600, HARDWARE, IT),
        ("Access-Switches 40 × 1.750 €", 70000, HARDWARE, IT), ("WLAN-Access-Points 8 × 620 €", 4960, HARDWARE, IT),
        ("Lizenzen ExtremeCloud IQ 60 × 180 € (5 Jahre)", 10800, LICENSE, IT)])
    task("b2", "Lieferung Hardware", 15, "P3", (), ["b1"], notes="Lieferzeit laut Angebot 3 Wochen.")
    task("b3", "Wareneingang & Inventarisierung", 2, "P3", [(C, 100)], ["b2"])
    task("b4", "Staging: Vorkonfiguration der 60 Geräte", 8, "P3", [(B, 100), (C, 100)], ["b3"])

    task("P4", "Rollout nach Standort")
    task("S1", "Standort Zentrale (24 Geräte)", 0, "P4")
    task("z1", "Core-Switches tauschen (2) – Wartungsfenster Wochenende", 2, "S1", [(A, 90), (B, 100)], ["b4"],
         [("Externe Elektriker (USV/Verkabelung)", 3800, EXTERN, cc["0000400100"])])
    task("z2", "Distribution-Switches tauschen (4)", 2, "S1", [(B, 100), (C, 100)], ["z1"])
    task("z3", "Access-Switches tauschen (14)", 4, "S1", [(B, 100), (C, 100)], ["z2"],
         [("Kabel & Patchmaterial", 2400, HARDWARE, cc["0000400100"])])
    task("z4", "WLAN-Access-Points montieren (4)", 1, "S1", [(C, 100)], ["z3"])
    task("z5", "Abnahmetest Zentrale", 2, "S1", [(A, 90)], ["z4"])
    task("z6", "Zentrale umgestellt", 0, "S1", (), ["z5"])
    task("S2", "Werk Nord (14 Geräte)", 0, "P4")
    task("n1", "Vorbereitung & Anreise", 1, "S2", [(B, 100), (C, 100)], ["z6"])
    task("n2", "Distribution & Access tauschen (14)", 3, "S2", [(B, 100), (C, 100)], ["n1"],
         [("Kabel & Patchmaterial", 1400, HARDWARE, cc["0000400200"])])
    task("n3", "Test & Abnahme Werk Nord", 1, "S2", [(A, 90)], ["n2"])
    task("n4", "Werk Nord umgestellt", 0, "S2", (), ["n3"])
    task("S3", "Werk Süd (12 Geräte)", 0, "P4")
    task("su1", "Distribution & Access tauschen (12)", 3, "S3", [(B, 100), (C, 100)], ["n4"],
         [("Kabel & Patchmaterial", 1200, HARDWARE, cc["0000400300"])])
    task("su2", "Test & Abnahme Werk Süd", 1, "S3", [(A, 90)], ["su1"])
    task("su3", "Werk Süd umgestellt", 0, "S3", (), ["su2"])
    task("S4", "Logistikzentrum (10 Geräte)", 0, "P4")
    task("l1", "Distribution & Access tauschen (10)", 2, "S4", [(B, 100), (C, 100)], ["su3"],
         [("Kabel & Patchmaterial", 1000, HARDWARE, cc["0000400400"])])
    task("l2", "Test & Abnahme Logistikzentrum", 1, "S4", [(A, 90)], ["l1"])
    task("l3", "Logistikzentrum umgestellt", 0, "S4", (), ["l2"])

    task("P5", "Abschluss & Übergabe")
    task("a1", "Rückbau Cisco-Altgeräte & Entsorgung (60 Geräte)", 5, "P5", [(C, 100)], ["l3"],
         [("Entsorgung 60 × 12 €", 720, DISPOSAL, IT)])
    task("a2", "Schulung Betriebsteam", 2, "P5", [(A, 50), (B, 50)], ["l3"],
         [("Externer Trainer", 3500, TRAINING, IT)])
    task("a3", "Dokumentation & Netzplan aktualisieren", 6, "P5", [(A, 60)], [("n2", "SS", 0)])
    task("a4", "Abnahme & Übergabe in den Betrieb", 0, "P5", (), ["a1", "a2", "a3"])
    task("pm3", "Projektabschluss & Lessons Learned", 2, "P1", [(A, 50)], ["a4"])

    db.execute("INSERT INTO budget_lines(project_id, cost_center_id, cost_type_id, amount) VALUES (?,NULL,NULL,?)", (pid, 260000))
    db.execute("INSERT INTO budget_lines(project_id, cost_center_id, cost_type_id, amount) VALUES (?,NULL,?,?)", (pid, ct[HARDWARE], 185000))
    db.execute("INSERT INTO budget_lines(project_id, cost_center_id, cost_type_id, amount) VALUES (?,NULL,?,?)", (pid, ct[LICENSE], 12000))

    # ── Basisplan, danach Verzug ────────────────────────────────────────────
    api.set_baseline(pid, user, db)
    db.execute("UPDATE tasks SET duration=7 WHERE id=?", (ids["k1"],))      # Bestandsaufnahme: +2 Tage
    db.execute("UPDATE tasks SET duration=5 WHERE id=?", (ids["k3"],))      # Migrationskonzept: +1 Tag

    # ── Fortschritt relativ zu heute ────────────────────────────────────────
    data = svc.load_project(db, pid, user)
    proj = svc.get_project_row(db, pid)
    cal = cpm.Calendar(start, svc.parse_days(proj["work_days"]), svc.parse_holidays(proj["holidays"]))
    by_key = {v: k for k, v in ids.items()}
    for t in data["tasks"]:
        if t["summary"]:
            continue
        fin, beg = date.fromisoformat(t["finish"]), date.fromisoformat(t["start"])
        if fin < today:
            status, pct = "done", 100.0
        elif beg <= today and t["duration"] > 0:
            elapsed = sum(1 for i in range((today - beg).days) if cal.is_working(beg + timedelta(days=i)))
            pct = float(min(90, max(10, round(100 * elapsed / t["duration"] / 10) * 10)))
            status = "in_progress"
        else:
            continue
        note = ""
        if by_key[t["id"]] == "b2" and status == "in_progress":
            status, note = "blocked", "Teillieferung der Distribution-Switches verzögert sich laut Lieferant um ca. 1 Woche."
        db.execute("UPDATE tasks SET status=?, percent=?, status_note=? WHERE id=?", (status, pct, note, t["id"]))

    # ── Ist-Kosten ──────────────────────────────────────────────────────────
    data = svc.load_project(db, pid, user)
    tmap = {t["id"]: t for t in data["tasks"]}

    def book(day: date, amount: float, task_key: Optional[str], cc_id: int, ct_code: str, ref: str, text: str) -> None:
        db.execute("INSERT INTO actuals(project_id, task_id, booking_date, cost_type_id, cost_center_id, amount, reference, "
                   "description, source, created_by) VALUES (?,?,?,?,?,?,?,?, 'manual', ?)",
                   (pid, ids[task_key] if task_key else None, min(day, today).isoformat(), ct[ct_code], cc_id, round(amount, 2),
                    ref, text, user["username"]))

    b1 = tmap[ids["b1"]]
    if b1["status"] == "done" or b1["percent"] > 0:
        d = date.fromisoformat(b1["finish"])
        book(d, 178900, "b1", IT, HARDWARE, "4900101", "Rechnung Extreme-Hardware inkl. Fracht (Plan: 174.560 €)")
        book(d, 10800, "b1", IT, LICENSE, "4900102", "Lizenzen ExtremeCloud IQ (5 Jahre)")
    items = [dict(r) for r in db.execute("SELECT * FROM cost_items WHERE project_id=?", (pid,))]
    labor = [ln for ln in budget.plan_lines(data["tasks"], data["assignments"], finance_api.raw_resources(db, pid), items,
                                            budget.Fx("EUR", {})) if ln["kind"] == "labor"]
    per_month: Dict[str, float] = {}
    for ln in labor:
        t = tmap[ln["task_id"]]
        if t["status"] == "done":
            per_month[t["finish"][:7]] = per_month.get(t["finish"][:7], 0.0) + ln["amount"] * 1.05
    for ym, amount in sorted(per_month.items()):
        y, m = int(ym[:4]), int(ym[5:])
        end = date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
        book(end, amount, None, IT, PERSONAL, "LV-" + ym, "Leistungsverrechnung IT-Netzwerk %s %d" % (MONTHS[m - 1], y))

    svc.bump(db, pid)
    svc.log(db, pid, user, "Beispielprojekt angelegt", "Netzwerk-Rollout Cisco → Extreme")
    return pid
