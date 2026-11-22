"""Weitere Beispielprojekte (zweisprachig, Sprache des anlegenden Benutzers): Server-Migration auf ein neues Cluster und
Transition eines Release-Wechsels.

Wie ``demo.py``: Der Plan startet in der Vergangenheit, bekommt einen Basisplan, danach Verzug, Fortschritt relativ zu heute, eine
Blockade und Ist-Kosten – damit zeigen Gantt/Tracking, Team, Kalender und Budget sofort sinnvolle Daten.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import budget
import cpm
import finance_api
import service as svc
from i18n import norm

PERSONAL, HARDWARE, LICENSE, EXTERN, TRAINING, DISPOSAL = "600000", "410000", "420000", "400000", "430000", "440000"
COST_TYPE_NAMES = {
    EXTERN: ("Fremdleistungen", "External services"), HARDWARE: ("Hardware & Material", "Hardware & material"),
    LICENSE: ("Lizenzen & Software", "Licences & software"), TRAINING: ("Schulung", "Training"), DISPOSAL: ("Entsorgung", "Disposal"),
    PERSONAL: ("Interne Leistungsverrechnung", "Internal cost allocation"),
}
MONTHS = {"de": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"],
          "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]}


class Kit:
    """Gemeinsamer Aufbau: Projekt, Stammdaten, Ressourcen, Vorgänge, Budget, Basisplan, Verzug, Fortschritt, Ist-Kosten."""

    template = False                       # True: nur Struktur (Phasen, Vorgänge, Meilensteine) – keine Ressourcen, Kosten, Basisplan, Fortschritt

    @classmethod
    def attach(cls, db, user: Dict[str, Any], pid: int) -> "Kit":
        """Struktur aus einer Projektart in ein bestehendes (leeres) Projekt schreiben (Assistent „Neues Projekt“)."""
        k = object.__new__(cls)
        k.db, k.user, k.lang, k.template, k.pid = db, user, norm(user.get("lang")), True, pid
        k.today = date.today()
        k.start = date.fromisoformat(db.execute("SELECT start_date FROM projects WHERE id=?", (pid,)).fetchone()["start_date"])
        k.pos, k.ids, k.cc, k.ct, k.main_cc = {}, {}, {}, {}, 0
        return k

    def __init__(self, db, user: Dict[str, Any], today: Optional[date], weeks_back: int, name: Tuple[str, str], desc: Tuple[str, str]):
        self.db, self.user = db, user
        self.lang = norm(user.get("lang"))
        self.today = today or date.today()
        start = self.today - timedelta(days=7 * weeks_back)
        self.start = start - timedelta(days=start.weekday())                  # Montag
        self.pid = db.execute("INSERT INTO projects(name, description, start_date, work_days, holidays, owner_id) VALUES (?,?,?,?,?,?)",
                              (self.L(*name), self.L(*desc), self.start.isoformat(), "0,1,2,3,4", "", user["id"])).lastrowid
        self.pos: Dict[Optional[int], int] = {}
        self.ids: Dict[str, int] = {}
        self.cc: Dict[str, int] = {}
        self.ct: Dict[str, int] = {}
        self.main_cc = 0

    def L(self, de: str, en: str) -> str:
        return en if self.lang == "en" else de

    # ── Stammdaten ──
    def cost_centers(self, rows: List[Tuple[str, str, str]]) -> None:
        if self.template:
            return
        for code, de, en in rows:
            self.cc[code] = self.db.execute("INSERT INTO cost_centers(project_id, code, name) VALUES (?,?,?)", (self.pid, code, self.L(de, en))).lastrowid
        self.main_cc = self.cc[rows[0][0]]
        for code, (de, en) in COST_TYPE_NAMES.items():
            self.ct[code] = self.db.execute("INSERT INTO cost_types(project_id, code, name) VALUES (?,?,?)", (self.pid, code, self.L(de, en))).lastrowid

    def resource(self, de: str, en: str, rate: float) -> Optional[int]:
        if self.template:
            return None
        return self.db.execute("INSERT INTO resources(project_id, name, max_units, cost_rate, cost_center_id, cost_type_id) VALUES (?,?,100,?,?,?)",
                               (self.pid, self.L(de, en), rate, self.main_cc, self.ct[PERSONAL])).lastrowid

    # ── Vorgänge ──
    def task(self, key: str, de: str, en: str, dur: int = 0, parent: Optional[str] = None, res: Tuple = (), pred: Tuple = (),
             items: Tuple = (), notes: Tuple[str, str] = ("", "")) -> int:
        par = self.ids[parent] if parent else None
        p = self.pos.get(par, 0)
        self.pos[par] = p + 1
        tid = self.db.execute("INSERT INTO tasks(project_id, parent_id, position, name, duration, notes) VALUES (?,?,?,?,?,?)",
                              (self.pid, par, p, self.L(de, en), dur, self.L(*notes))).lastrowid
        self.ids[key] = tid
        for r, units in res:
            if r is not None:
                self.db.execute("INSERT INTO assignments(task_id, resource_id, units) VALUES (?,?,?)", (tid, r, units))
        for pr in pred:
            pk, typ, lag = (pr + ("FS", 0))[:3] if isinstance(pr, tuple) else (pr, "FS", 0)
            self.db.execute("INSERT INTO deps(project_id, pred_id, succ_id, type, lag) VALUES (?,?,?,?,?)", (self.pid, self.ids[pk], tid, typ, lag))
        for ide, ien, amount, code, cc_code in ([] if self.template else items):
            self.db.execute("INSERT INTO cost_items(project_id, task_id, cost_type_id, cost_center_id, amount, description) VALUES (?,?,?,?,?,?)",
                            (self.pid, tid, self.ct[code], self.cc[cc_code] if cc_code else self.main_cc, amount, self.L(ide, ien)))
        return tid

    def budget_lines(self, total: float, parts: Dict[str, float]) -> None:
        if self.template:
            return
        self.db.execute("INSERT INTO budget_lines(project_id, cost_center_id, cost_type_id, amount) VALUES (?,NULL,NULL,?)", (self.pid, total))
        for code, amount in parts.items():
            self.db.execute("INSERT INTO budget_lines(project_id, cost_center_id, cost_type_id, amount) VALUES (?,NULL,?,?)", (self.pid, self.ct[code], amount))

    # ── Abschluss: Basisplan, Verzug, Fortschritt, Blockade, Ist-Kosten ──
    def finish(self, delays: Dict[str, int], block: Tuple[str, Tuple[str, str]], log_name: Tuple[str, str], prefix: str) -> int:
        import api  # lokal: api importiert dieses Modul
        db, pid, user, today = self.db, self.pid, self.user, self.today
        api.set_baseline(pid, user, db)
        for key, dur in delays.items():
            db.execute("UPDATE tasks SET duration=? WHERE id=?", (dur, self.ids[key]))

        data = svc.load_project(db, pid, user)
        proj = svc.get_project_row(db, pid)
        cal = cpm.Calendar(self.start, svc.parse_days(proj["work_days"]), svc.parse_holidays(proj["holidays"]))
        by_id = {v: k for k, v in self.ids.items()}
        running: List[int] = []
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
                running.append(t["id"])
            else:
                continue
            db.execute("UPDATE tasks SET status=?, percent=?, status_note='' WHERE id=?", (status, pct, t["id"]))
        bkey, bnote = block
        target = self.ids[bkey] if self.ids[bkey] in running else (running[-1] if running else None)   # Blockade, notfalls an einem laufenden Vorgang
        if target:
            db.execute("UPDATE tasks SET status='blocked', status_note=? WHERE id=?", (self.L(*bnote), target))

        # Ist-Kosten: Rechnungen zu erledigten Vorgängen mit Planposten, dazu monatliche Leistungsverrechnung
        data = svc.load_project(db, pid, user)
        tmap = {t["id"]: t for t in data["tasks"]}
        n = 0
        for it in [dict(r) for r in db.execute("SELECT * FROM cost_items WHERE project_id=? ORDER BY id", (pid,))]:
            t = tmap[it["task_id"]]
            if t["status"] != "done":
                continue
            n += 1
            factor = (1.03, 0.97, 1.0, 1.05)[n % 4]
            day = min(date.fromisoformat(t["finish"]), today)
            db.execute("INSERT INTO actuals(project_id, task_id, booking_date, cost_type_id, cost_center_id, amount, reference, description, source, created_by) "
                       "VALUES (?,?,?,?,?,?,?,?, 'manual', ?)",
                       (pid, it["task_id"], day.isoformat(), it["cost_type_id"], it["cost_center_id"], round(it["amount"] * factor, 2),
                        "%s%02d" % (prefix, n), self.L("Rechnung: ", "Invoice: ") + it["description"], user["username"]))
        items = [dict(r) for r in db.execute("SELECT * FROM cost_items WHERE project_id=?", (pid,))]
        labor = [ln for ln in budget.plan_lines(data["tasks"], data["assignments"], finance_api.raw_resources(db, pid), items, budget.Fx("EUR", {}))
                 if ln["kind"] == "labor"]
        per_month: Dict[str, float] = {}
        for ln in labor:
            t = tmap[ln["task_id"]]
            if t["status"] == "done":
                per_month[t["finish"][:7]] = per_month.get(t["finish"][:7], 0.0) + ln["amount"] * 1.05
        for ym, amount in sorted(per_month.items()):
            y, m = int(ym[:4]), int(ym[5:])
            end = date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
            db.execute("INSERT INTO actuals(project_id, task_id, booking_date, cost_type_id, cost_center_id, amount, reference, description, source, created_by) "
                       "VALUES (?,?,?,?,?,?,?,?, 'manual', ?)",
                       (pid, None, min(end, today).isoformat(), self.ct[PERSONAL], self.main_cc, round(amount, 2), "LV-" + ym,
                        self.L("Leistungsverrechnung %s %d", "Internal cost allocation %s %d") % (MONTHS[self.lang][m - 1], y), user["username"]))
        svc.bump(db, pid)
        svc.log(db, pid, user, self.L("Beispielprojekt angelegt", "Sample project created"), self.L(*log_name))
        return pid


def _migration(k: "Kit") -> None:
    """Struktur (Phasen, Vorgänge, Meilensteine); mit Ressourcen, Budget und Planposten, solange ``k.template`` nicht gesetzt ist."""
    k.cost_centers([("0000100300", "IT Infrastruktur", "IT infrastructure"), ("0000100310", "Rechenzentrum", "Data centre")])
    DC = "0000100310"
    A = k.resource("Mara Lindner (Projektleitung / Virtualisierung)", "Mara Lindner (Project lead / virtualisation)", 700)
    B = k.resource("Jonas Keller (Systemadministrator)", "Jonas Keller (System administrator)", 560)
    C = k.resource("Selin Aydin (Storage & Netzwerk)", "Selin Aydin (Storage & network)", 560)
    D = k.resource("Tom Richter (Backup & Monitoring)", "Tom Richter (Backup & monitoring)", 520)
    t = k.task

    t("P1", "Projektmanagement", "Project management")
    t("pm1", "Kickoff & Projektplanung", "Kick-off & project planning", 2, "P1", [(A, 100)])
    t("pm2", "Projektsteuerung & Statusmeetings", "Project control & status meetings", 70, "P1", [(A, 10)], ["pm1"])

    t("P2", "Analyse & Konzeption", "Analysis & design")
    t("k1", "Bestandsaufnahme VMs & Hosts (120 VMs)", "Inventory of VMs & hosts (120 VMs)", 5, "P2", [(B, 100), (C, 50)], ["pm1"])
    t("k2", "Abhängigkeiten & Anwendungslandkarte", "Dependencies & application map", 4, "P2", [(B, 60)], ["k1"])
    t("k3", "Zielarchitektur Cluster (4 Nodes, Ceph, Netzwerk)", "Target architecture cluster (4 nodes, Ceph, network)", 6, "P2", [(A, 80), (C, 60)], ["k1"])
    t("k4", "Migrationsstrategie & Wellenplanung", "Migration strategy & wave planning", 4, "P2", [(A, 80)], ["k2", "k3"])
    t("k5", "Backup-, Restore- und Rollback-Konzept", "Backup, restore and rollback concept", 3, "P2", [(D, 80)], ["k3"])
    t("k6", "Wartungsfenster mit Fachbereichen abstimmen", "Agree maintenance windows with business units", 3, "P2", [(A, 40)], ["k4"])
    t("k7", "Freigabe Konzept (Gate 1)", "Design approval (Gate 1)", 0, "P2", (), ["k5", "k6"])

    t("P3", "Aufbau Zielumgebung", "Build target environment")
    t("b1", "Bestellung Hardware & Lizenzen", "Order hardware & licences", 3, "P3", [(A, 20)], ["k7"], [
        ("Cluster-Nodes 4 × 18.500 €", "Cluster nodes 4 × €18,500", 74000, HARDWARE, DC), ("NVMe-SSDs 16 × 1.150 €", "NVMe SSDs 16 × €1,150", 18400, HARDWARE, DC),
        ("Switches 2 × 6.800 €", "Switches 2 × €6,800", 13600, HARDWARE, DC), ("Backup-Server", "Backup server", 8200, HARDWARE, DC),
        ("Hypervisor-Subskription 4 Nodes (3 Jahre)", "Hypervisor subscription 4 nodes (3 years)", 9600, LICENSE, DC)])
    t("b2", "Lieferung Hardware", "Hardware delivery", 15, "P3", (), ["b1"], notes=("Lieferzeit laut Angebot 3 Wochen.", "Lead time per quote: 3 weeks."))
    t("b3", "Rack, Verkabelung & Stromanbindung", "Racking, cabling & power", 3, "P3", [(B, 100), (C, 100)], ["b2"],
      [("Externe Elektriker (Stromanbindung)", "External electricians (power connection)", 2400, EXTERN, DC)])
    t("b4", "Hypervisor-Installation auf 4 Nodes", "Hypervisor installation on 4 nodes", 2, "P3", [(B, 100)], ["b3"])
    t("b5", "Cluster & Shared Storage einrichten", "Set up cluster & shared storage", 4, "P3", [(B, 60), (C, 100)], ["b4"])
    t("b6", "Netzwerk, VLANs & Firewall-Regeln", "Network, VLANs & firewall rules", 3, "P3", [(C, 100)], ["b4"])
    t("b7", "Backup-Server & Monitoring anbinden", "Connect backup server & monitoring", 3, "P3", [(D, 100)], ["b5"])
    t("b8", "Technischer Abnahmetest Zielumgebung", "Technical acceptance test of target environment", 2, "P3", [(B, 60), (C, 60), (D, 60)], ["b6", "b7"])

    t("P4", "Pilot & Test", "Pilot & test")
    t("t1", "Pilotmigration (5 unkritische VMs)", "Pilot migration (5 non-critical VMs)", 3, "P4", [(B, 100)], ["b8"])
    t("t2", "Performance- und Failover-Tests", "Performance and failover tests", 3, "P4", [(C, 100), (D, 60)], ["t1"])
    t("t3", "Restore-Test aus Backup", "Restore test from backup", 1, "P4", [(D, 100)], ["t1"])
    t("t4", "Go/No-Go-Entscheidung (Gate 2)", "Go/No-Go decision (Gate 2)", 0, "P4", (), ["t2", "t3"])

    t("P5", "Migrationswellen", "Migration waves")
    prev = "t4"
    waves = [("1", "Welle 1: Test & Entwicklung (30 VMs)", "Wave 1: test & development (30 VMs)", 1, 3, 1, [(B, 100), (C, 50)]),
             ("2", "Welle 2: Datei- und Anwendungsserver (40 VMs)", "Wave 2: file and application servers (40 VMs)", 1, 4, 1, [(B, 100), (C, 50)]),
             ("3", "Welle 3: Datenbankserver (30 VMs)", "Wave 3: database servers (30 VMs)", 2, 4, 2, [(B, 100), (C, 100)]),
             ("4", "Welle 4: Geschäftskritische Systeme (20 VMs)", "Wave 4: business-critical systems (20 VMs)", 2, 3, 2, [(B, 100), (C, 100), (D, 50)])]
    for n, de, en, prep, mig, ver, team in waves:
        t("W" + n, de, en, 0, "P5")
        t("w%s1" % n, "Vorbereitung & Kommunikation", "Preparation & communication", prep, "W" + n, [(A, 40), (B, 50)], [prev])
        t("w%s2" % n, "Migration & Cutover", "Migration & cutover", mig, "W" + n, team, ["w%s1" % n])
        t("w%s3" % n, "Verifikation & Abnahme", "Verification & acceptance", ver, "W" + n, [(B, 50), (D, 50)], ["w%s2" % n])
        prev = "w%s3" % n

    t("P6", "Abschluss & Rückbau", "Closure & decommissioning")
    t("a1", "Hypercare (2 Wochen)", "Hypercare (2 weeks)", 10, "P6", [(B, 40), (D, 30)], ["w43"])
    t("a2", "Rückbau & Entsorgung Altsystem (6 Hosts)", "Decommissioning & disposal of old system (6 hosts)", 4, "P6", [(B, 100)], ["a1"],
      [("Entsorgung 6 Hosts", "Disposal of 6 hosts", 900, DISPOSAL, DC)])
    t("a3", "Lizenzkündigung Altplattform", "Terminate licences of old platform", 2, "P6", [(A, 50)], ["a1"])
    t("a4", "Dokumentation & Betriebsübergabe", "Documentation & handover to operations", 5, "P6", [(A, 50), (D, 50)], ["w43"],
      [("Schulung Betriebsteam", "Training of operations team", 3200, TRAINING, DC)])
    t("a5", "Abnahme & Projektende", "Acceptance & project end", 0, "P6", (), ["a2", "a3", "a4"])
    t("pm3", "Projektabschluss & Lessons Learned", "Project closure & lessons learned", 2, "P1", [(A, 50)], ["a5"])

    k.budget_lines(190000, {HARDWARE: 125000, LICENSE: 12000})


def create_migration_project(db, user: Dict[str, Any], today: Optional[date] = None) -> int:
    """Migration von Servern (120 VMs) von einem Hypervisor auf ein neues Cluster, in vier Wellen."""
    k = Kit(db, user, today, 6, ("Beispiel: Server-Migration Hypervisor → neues Cluster", "Sample: Server migration hypervisor → new cluster"),
            ("Migration von 120 virtuellen Servern von der bisherigen Hypervisor-Plattform auf ein neues 4-Node-Cluster (Ceph) in vier Wellen. "
             "Beispielprojekt: enthält Basisplan mit Verzug, eine Blockade (Lieferung der SSDs) und – bewusst – eine Überlastung von Selin Aydin beim Cluster-Aufbau.",
             "Migration of 120 virtual servers from the existing hypervisor platform to a new 4-node cluster (Ceph) in four waves. "
             "Sample project: contains a baseline with delay, a block (SSD delivery) and – deliberately – an overload of Selin Aydin during the cluster build."))
    _migration(k)
    return k.finish({"k1": 7, "k4": 5}, ("b2", ("Lieferung der NVMe-SSDs verzögert sich laut Lieferant um ca. 1 Woche.", "NVMe SSD delivery is delayed by about 1 week according to the supplier.")),
                    ("Server-Migration Hypervisor → neues Cluster", "Server migration hypervisor → new cluster"), "4910")


def _release(k: "Kit") -> None:
    """Struktur (Phasen, Vorgänge, Meilensteine); mit Ressourcen, Budget und Planposten, solange ``k.template`` nicht gesetzt ist."""
    k.cost_centers([("0000200100", "IT Anwendungen", "IT applications"), ("0000200200", "Fachbereich Finanzen", "Finance department")])
    FIN = "0000200200"
    A = k.resource("Lena Hartmann (Release Managerin)", "Lena Hartmann (Release manager)", 720)
    B = k.resource("Paul Neumann (Testmanager)", "Paul Neumann (Test manager)", 560)
    C = k.resource("Yusuf Demir (Plattform-Engineer)", "Yusuf Demir (Platform engineer)", 580)
    D = k.resource("Nora Fischer (Key-Userin Fachbereich)", "Nora Fischer (Key user business)", 480)
    E = k.resource("Felix Brandt (Schulung & Kommunikation)", "Felix Brandt (Training & communication)", 500)
    t = k.task

    t("P1", "Projektmanagement", "Project management")
    t("pm1", "Kickoff & Transition-Plan", "Kick-off & transition plan", 2, "P1", [(A, 100)])
    t("pm2", "Steuerung & Statusmeetings", "Control & status meetings", 60, "P1", [(A, 10)], ["pm1"])

    t("P2", "Planung & Bewertung", "Planning & assessment")
    t("p1", "Release-Scope bewerten (Release Notes, Breaking Changes)", "Assess release scope (release notes, breaking changes)", 4, "P2", [(A, 60), (B, 40)], ["pm1"])
    t("p2", "Impact-Analyse Schnittstellen & Anpassungen", "Impact analysis interfaces & customisations", 5, "P2", [(C, 80), (B, 40)], ["p1"])
    t("p3", "Risikobewertung & Rollback-Strategie", "Risk assessment & rollback strategy", 3, "P2", [(A, 50), (C, 50)], ["p2"])
    t("p4", "Zeitplan & Change-Freigabe (CAB)", "Schedule & change approval (CAB)", 2, "P2", [(A, 50)], ["p3"])
    t("p5", "Freigabe Transition-Plan (Gate 1)", "Approval of transition plan (Gate 1)", 0, "P2", (), ["p4"])

    t("P3", "Vorbereitung Zielumgebung", "Prepare target environment")
    t("v1", "Testumgebung aufbauen (Kopie der Produktion)", "Build test environment (copy of production)", 3, "P3", [(C, 100)], ["p5"],
      [("Zusätzliche Test-Lizenzen und Hosting", "Additional test licences and hosting", 4200, LICENSE, None)])
    t("v2", "Release 13 in Testumgebung einspielen", "Install release 13 in test environment", 2, "P3", [(C, 100)], ["v1"])
    t("v3", "Eigenentwicklungen & Schnittstellen anpassen", "Adapt customisations & interfaces", 8, "P3", [(C, 60), (B, 40)], ["v2"],
      [("Externe Entwicklung Schnittstellen", "External development of interfaces", 18000, EXTERN, None)])
    t("v4", "Datenmigration: Probelauf 1", "Data migration: trial run 1", 3, "P3", [(C, 80)], ["v3"])

    t("P4", "Test & Abnahme", "Test & acceptance")
    t("t1", "Testplan & Testfälle aktualisieren", "Update test plan & test cases", 4, "P4", [(B, 100)], ["p5"])
    t("t2", "Systemtest & Regression", "System test & regression", 6, "P4", [(B, 100), (C, 30)], ["v3", "t1"])
    t("t3", "Benutzerabnahmetest (UAT) mit Fachbereich", "User acceptance test (UAT) with business", 5, "P4", [(D, 100), (B, 50)], ["t2"])
    t("t4", "Performance- und Lasttest", "Performance and load test", 3, "P4", [(C, 60)], ["t2"])
    t("t5", "Datenmigration: Generalprobe (Probelauf 2)", "Data migration: dress rehearsal (trial run 2)", 2, "P4", [(C, 80), (D, 30)], ["v4", "t3"])
    t("t6", "Go/No-Go-Entscheidung (Gate 2)", "Go/No-Go decision (Gate 2)", 0, "P4", (), ["t3", "t4", "t5"])

    t("P5", "Schulung & Kommunikation", "Training & communication")
    t("c1", "Schulungskonzept & -unterlagen", "Training concept & materials", 4, "P5", [(E, 100)], ["p5"])
    t("c2", "Key-User-Schulung", "Key user training", 2, "P5", [(E, 100), (D, 50)], ["c1", "t2"],
      [("Externer Trainer Key-User", "External trainer for key users", 3600, TRAINING, FIN)])
    t("c3", "Anwenderschulungen in Wellen", "End-user training in waves", 5, "P5", [(E, 100)], ["c2", "t3"],
      [("Schulungsräume & Material", "Training rooms & materials", 2200, TRAINING, FIN)])
    t("c4", "Ankündigung & Kommunikationsplan Go-Live", "Go-live announcement & communication plan", 2, "P5", [(E, 50), (A, 20)], ["p5"])

    t("P6", "Cutover & Go-Live", "Cutover & go-live")
    t("g1", "Cutover-Runbook & Zeitplan", "Cutover runbook & schedule", 2, "P6", [(A, 60), (C, 60)], ["t6"])
    t("g2", "Change-Freeze Produktion", "Production change freeze", 1, "P6", [(A, 30)], ["g1", "c3"])
    t("g3", "Produktion sichern & Release einspielen (Wochenende)", "Back up production & install release (weekend)", 2, "P6", [(C, 100), (B, 50)], ["g2"])
    t("g4", "Datenmigration & Smoke-Test", "Data migration & smoke test", 1, "P6", [(C, 100), (B, 100), (D, 50)], ["g3"])
    t("g5", "Go-Live (Gate 3)", "Go-live (Gate 3)", 0, "P6", (), ["g4"])

    t("P7", "Hypercare & Übergabe", "Hypercare & handover")
    t("h1", "Hypercare (2 Wochen, erhöhte Bereitschaft)", "Hypercare (2 weeks, increased standby)", 10, "P7", [(C, 40), (B, 30), (E, 30)], ["g5"])
    t("h2", "Incidents & Nacharbeiten", "Incidents & rework", 5, "P7", [(C, 50), (B, 30)], ["g5"])
    t("h3", "Wissensübergabe an den Betrieb (Service Transition)", "Knowledge transfer to operations (service transition)", 3, "P7", [(C, 50), (A, 30)], ["h1"])
    t("h4", "Betriebsdokumentation & Runbooks aktualisieren", "Update operations documentation & runbooks", 3, "P7", [(C, 60), (E, 30)], ["h2"])
    t("h5", "Release 12 abschalten & archivieren", "Decommission & archive release 12", 2, "P7", [(C, 80)], ["h3", "h4"],
      [("Archivierung Altdaten", "Archiving of legacy data", 1500, EXTERN, None)])
    t("h6", "Übergabe in den Regelbetrieb (Abnahme)", "Handover to regular operations (acceptance)", 0, "P7", (), ["h5"])
    t("pm3", "Projektabschluss & Lessons Learned", "Project closure & lessons learned", 2, "P1", [(A, 50)], ["h6"])

    k.budget_lines(95000, {EXTERN: 25000, LICENSE: 8000, TRAINING: 9000})


def create_release_project(db, user: Dict[str, Any], today: Optional[date] = None) -> int:
    """Transition eines Release-Wechsels (Service Transition): Bewertung, Test, Schulung, Cutover, Hypercare, Übergabe."""
    k = Kit(db, user, today, 5, ("Beispiel: Transition Release-Wechsel (ERP 12 → 13)", "Sample: Transition release change (ERP 12 → 13)"),
            ("Transition-Projekt für den Wechsel der Kernanwendung ERP von Release 12 auf 13: Bewertung, Test und Abnahme, Schulung, Cutover am Wochenende, Hypercare und Übergabe in den Betrieb. "
             "Beispielprojekt: enthält Basisplan mit Verzug, eine Blockade (fehlende Testdaten im Abnahmetest) und drei Freigabe-Gates.",
             "Transition project for the change of the core ERP application from release 12 to 13: assessment, testing and acceptance, training, weekend cutover, hypercare and handover to operations. "
             "Sample project: contains a baseline with delay, a block (missing test data in the acceptance test) and three approval gates."))
    _release(k)
    return k.finish({"p2": 6, "v3": 10}, ("t3", ("UAT blockiert: Testdaten des Fachbereichs fehlen noch.", "UAT blocked: test data from the business department is still missing.")),
                    ("Transition Release-Wechsel (ERP 12 → 13)", "Transition release change (ERP 12 → 13)"), "4920")


def _network(k: "Kit") -> None:
    """Rollout von Netzwerkgeräten (Struktur; die Geräte kommen danach per Geräteliste-Import in den Tab „Geräte“)."""
    t = k.task
    t("P1", "Projektmanagement", "Project management")
    t("pm1", "Kickoff & Projektplanung", "Kick-off & project planning", 2, "P1")
    t("pm2", "Projektsteuerung & Statusmeetings", "Project control & status meetings", 60, "P1", (), ["pm1"])
    t("P2", "Konzeption & Vorbereitung", "Design & preparation")
    t("k1", "Bestandsaufnahme der Alt-Infrastruktur", "Inventory of the existing infrastructure", 5, "P2", (), ["pm1"])
    t("k2", "Zielarchitektur (VLAN-/IP-Konzept, Stacking, WLAN)", "Target architecture (VLAN/IP concept, stacking, WLAN)", 6, "P2", (), ["k1"])
    t("k3", "Migrationskonzept & Rollback-Plan", "Migration concept & rollback plan", 4, "P2", (), ["k2"])
    t("k4", "Wartungsfenster mit Fachbereichen abstimmen", "Agree maintenance windows with business units", 3, "P2", (), ["k2"])
    t("k5", "Freigabe Konzept (Gate 1)", "Design approval (Gate 1)", 0, "P2", (), ["k3", "k4"])
    t("P3", "Beschaffung & Logistik", "Procurement & logistics")
    t("b1", "Bestellung Hardware & Lizenzen", "Order hardware & licences", 5, "P3", (), ["k5"])
    t("b2", "Lieferung Hardware", "Hardware delivery", 15, "P3", (), ["b1"])
    t("b3", "Wareneingang & Inventarisierung", "Goods receipt & inventory", 2, "P3", (), ["b2"])
    t("b4", "Staging: Vorkonfiguration der Geräte", "Staging: pre-configuration of the devices", 8, "P3", (), ["b3"])
    t("P4", "Rollout nach Standort", "Rollout by site")
    t("S1", "Standort 1 (hier die Geräteliste importieren: Tab „Geräte“)", "Site 1 (import the device list here: tab \"Devices\")", 0, "P4")
    t("s11", "Vorbereitung & Anreise", "Preparation & travel", 1, "S1", (), ["b4"])
    t("s12", "Geräte tauschen", "Replace devices", 3, "S1", (), ["s11"])
    t("s13", "Test & Abnahme", "Test & acceptance", 1, "S1", (), ["s12"])
    t("s14", "Standort 1 umgestellt", "Site 1 migrated", 0, "S1", (), ["s13"])
    t("P5", "Abschluss & Übergabe", "Closure & handover")
    t("a1", "Rückbau Altgeräte & Entsorgung", "Dismantling of old devices & disposal", 5, "P5", (), ["s14"])
    t("a2", "Schulung Betriebsteam", "Training of the operations team", 2, "P5", (), ["s14"])
    t("a3", "Dokumentation & Netzplan aktualisieren", "Update documentation & network diagram", 6, "P5", (), ["s12"])
    t("a4", "Abnahme & Übergabe in den Betrieb", "Acceptance & handover to operations", 0, "P5", (), ["a1", "a2", "a3"])
    t("pm3", "Projektabschluss & Lessons Learned", "Project closure & lessons learned", 2, "P1", (), ["a4"])


def _patchpanel(k: "Kit") -> None:
    """Einbau Patchfelder / Verkabelung (Struktur). Unter „Patchaufträge (aus Portwerk)“ hängt Portwerk je Patchauftrag einen Vorgang ein
    (Vertrag mit Portwerk: Sammelvorgang, dessen Name „Portwerk“ enthält)."""
    t = k.task
    t("P1", "Projektmanagement", "Project management")
    t("pm1", "Kickoff & Projektplanung", "Kick-off & project planning", 1, "P1")
    t("pm2", "Projektsteuerung & Abstimmung mit dem Betrieb", "Project control & alignment with operations", 20, "P1", (), ["pm1"])
    t("P2", "Planung", "Planning")
    t("p1", "Bestandsaufnahme Räume, Racks und Trassen", "Survey of rooms, racks and cable routes", 3, "P2", (), ["pm1"])
    t("p2", "Patchfeld- und Belegungsplanung (in Portwerk)", "Patch panel and port assignment planning (in Portwerk)", 3, "P2", (), ["p1"])
    t("p3", "Material bestellen (Patchfelder, Kabel, Etiketten)", "Order material (patch panels, cables, labels)", 2, "P2", (), ["p2"])
    t("p4", "Freigabe Planung", "Planning approval", 0, "P2", (), ["p3"])
    t("P3", "Installation", "Installation")
    t("i1", "Patchfelder und Kabelführungen montieren", "Mount patch panels and cable management", 3, "P3", (), ["p4"])
    t("i2", "Installationskabel verlegen", "Lay installation cables", 5, "P3", (), ["p4"])
    t("i3", "Auflegen und beschriften (Kabeletiketten)", "Terminate and label (cable labels)", 3, "P3", (), ["i1", "i2"])
    t("P4", "Messung & Dokumentation", "Measurement & documentation")
    t("m1", "Strecken messen, Messprotokolle ablegen", "Test links, file test reports", 2, "P4", (), ["i3"])
    t("m2", "Bestand in Portwerk erfassen (Geräte, Ports, Kabel)", "Record inventory in Portwerk (devices, ports, cables)", 2, "P4", (), ["i3"])
    t("PA", "Patchaufträge (aus Portwerk)", "Patch orders (from Portwerk)")
    t("pa1", "Alle Patchaufträge bestätigt", "All patch orders confirmed", 0, "PA", (), ["m1", "m2"])
    t("P5", "Abnahme & Übergabe", "Acceptance & handover")
    t("a1", "Abnahme (Soll/Ist-Abgleich in Portwerk ohne Abweichung)", "Acceptance (Portwerk target/actual check without deviations)", 1, "P5", (), ["pa1"])
    t("a2", "Übergabe in den Betrieb", "Handover to operations", 0, "P5", (), ["a1"])


TEMPLATES: Dict[str, Callable[["Kit"], None]] = {"network": _network, "migration": lambda k: _migration(k), "release": lambda k: _release(k),
                                                 "patchpanel": _patchpanel}


def apply_template(db, user: Dict[str, Any], pid: int, kind: str) -> None:
    """Struktur der gewählten Projektart in ein bestehendes Projekt schreiben (ohne Ressourcen, Kosten, Basisplan, Fortschritt)."""
    TEMPLATES[kind](Kit.attach(db, user, pid))


KINDS: Dict[str, Callable[..., int]] = {"migration": create_migration_project, "release": create_release_project}
