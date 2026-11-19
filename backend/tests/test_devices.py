from test_api import _login, c, mk  # noqa: F401,E402  (setzt DATA_DIR/ADMIN_PASSWORD vor allen App-Importen)

import datetime as dt  # noqa: E402
import io  # noqa: E402

import pytest  # noqa: E402
from openpyxl import Workbook  # noqa: E402

import database  # noqa: E402
import devices  # noqa: E402

PW = "passwort-"
_IDS = {}
HEAD = "Hostname;Standort;Gerätetyp;Neues Modell;Wartungsfenster von;Wartungsfenster bis;Lieferzeit (Tage);Preis netto (EUR);Kostenstelle;Kostenart;Verantwortlich (Benutzer);Prüfung"


def team(c):
    if not _IDS:
        for n in ("dv_owner", "dv_anna", "dv_view"):
            _IDS[n] = c.post("/api/users", json={"username": n, "password": PW + n, "role": "viewer" if n == "dv_view" else "editor"}).json()["id"]
    owner, anna, view = (_login(n, PW + n) for n in ("dv_owner", "dv_anna", "dv_view"))
    pid = owner.post("/api/projects", json={"name": "Geräte", "start_date": "2026-10-12"}).json()["project"]["id"]
    owner.put("/api/projects/%d/members" % pid, json=[{"user_id": _IDS["dv_anna"], "role": "editor"}, {"user_id": _IDS["dv_view"], "role": "viewer"}])
    return owner, anna, view, pid


def csv_file(*rows, head=HEAD):
    return {"file": ("liste.csv", ("\n".join([head] + list(rows)) + "\n").encode("utf-8"), "text/csv")}


def do_import(client, pid, files, mapping, **form):
    data = {"mapping": __import__("json").dumps(mapping), "dry_run": "false", **{k: str(v).lower() if isinstance(v, bool) else str(v) for k, v in form.items()}}
    return client.post("/api/projects/%d/devices/import" % pid, files=files, data=data)


MAP = {"hostname": 0, "standort": 1, "typ": 2, "modell": 3, "fenster_von": 4, "fenster_bis": 5, "lieferzeit": 6, "preis": 7, "kostenstelle": 8, "kostenart": 9, "verantwortlich": 10}


def tasks_of(client, pid):
    return client.get("/api/projects/%d" % pid).json()


def test_templates_seed_and_crud(c):
    tpls = {t["name"]: t for t in c.get("/api/templates").json()}
    assert {"Switch", "Access Point", "Firewall"} <= set(tpls)
    sw = tpls["Switch"]
    assert [s["name"] for s in sw["steps"]][:2] == ["Bestellung auslösen", "Lieferung / Wareneingang"] and len(sw["steps"]) == 7
    assert sw["steps"][0]["books_price"] and sw["steps"][0]["takes_lead"] and sw["steps"][0]["wait_days"] == 10 and sw["steps"][4]["uses_window"]
    owner, anna, view, pid = team(c)
    body = {"name": "Server", "category": "Server", "description": "", "steps": [
        {"name": "Bestellen", "role": "Einkauf", "duration": 2, "wait_days": 5, "books_price": True},
        {"name": "Racken", "role": "Rechenzentrum", "duration": 1, "pred_pos": 1}]}
    r = anna.post("/api/templates", json=body)
    assert r.status_code == 201 and r.json()["steps"][1]["pred_pos"] == 1
    tid = r.json()["id"]
    assert anna.post("/api/templates", json=body).status_code == 409                       # Name (ohne Groß/Klein) einmalig
    assert view.post("/api/templates", json={**body, "name": "X"}).status_code == 403      # Leser dürfen nicht
    assert anna.post("/api/templates", json={**body, "name": "Y", "steps": [{"name": "A", "pred_pos": 2}]}).status_code == 422     # Vorgänger muss früher sein
    assert anna.post("/api/templates", json={**body, "name": "Z", "steps": [{"name": "A", "books_price": True}, {"name": "B", "books_price": True}]}).status_code == 422
    r = anna.put("/api/templates/%d" % tid, json={**body, "description": "neu", "steps": body["steps"] + [{"name": "Test", "pred_pos": 2}]})
    assert r.json()["description"] == "neu" and len(r.json()["steps"]) == 3
    assert view.get("/api/templates").status_code == 200 and anna.delete("/api/templates/%d" % tid).status_code == 200


def test_parse_dry_run_and_import(c):
    owner, anna, view, pid = team(c)
    res = owner.post("/api/projects/%d/resources" % pid, json={"name": "Einkauf-Team"}).json()["resources"][0]["id"]
    rows = ["sw-01;Kassel;Switch;Extreme 5520;02.11.2026;06.11.2026;15;3890,50;0000100200;400100;dv_anna;OK",
            "sw-02;Kassel;switch;Extreme 5520;02.11.2026;06.11.2026;;3890,50;100200;400100;;OK",
            "ap-01;Hattorf;Access Point;AP410C;;;;640;;;;OK"]
    files = csv_file(*rows)
    p = owner.post("/api/projects/%d/devices/parse" % pid, files=files).json()
    assert p["rows_total"] == 3 and p["mapping"]["hostname"] == 0 and p["mapping"]["typ"] == 2 and p["mapping"]["fenster_von"] == 4 and p["mapping"]["preis"] == 7
    assert "verantwortlich" in p["mapping"] and "pruef" not in p["mapping"] and len(p["sample"]) == 3
    before = len(tasks_of(owner, pid)["tasks"])
    # Kostenstelle unbekannt -> Fehler, nichts geschrieben (Trockenlauf)
    rep = owner.post("/api/projects/%d/devices/import" % pid, files=csv_file(*rows), data={"mapping": __import__("json").dumps(MAP), "dry_run": "true"}).json()
    assert rep["dry_run"] and rep["error_count"] == 2 and "Kostenstelle" in rep["errors"][0]["message"]
    assert len(tasks_of(owner, pid)["tasks"]) == before
    rep = owner.post("/api/projects/%d/devices/import" % pid, files=csv_file(*rows), data={"mapping": __import__("json").dumps(MAP), "dry_run": "true", "create_missing": "true"}).json()
    assert rep["error_count"] == 0 and rep["new"] == 3 and rep["steps"] == 7 + 7 + 5 and rep["sites_new"] == 2
    assert "100200" in rep["new_cost_centers"] or "0000100200" in rep["new_cost_centers"]
    assert len(tasks_of(owner, pid)["tasks"]) == before                                       # Trockenlauf schreibt nichts
    # echter Import mit Rollenzuordnung
    r = do_import(owner, pid, csv_file(*rows), MAP, create_missing=True, role_map=__import__("json").dumps({"Einkauf": res}))
    rep = r.json()
    assert r.status_code == 200 and rep["imported"] == 3 and rep["error_count"] == 0
    d = tasks_of(owner, pid)
    by = {t["name"]: t for t in d["tasks"]}
    assert by["Kassel"]["summary"] and by["sw-01"]["summary"] and by["Hattorf"]["summary"]
    assert by["sw-01"]["parent_id"] == by["Kassel"]["id"] and by["sw-01"]["ext_key"] == "sw-01" and by["sw-01"]["attrs"]["modell"] == "Extreme 5520"
    kids = [t for t in d["tasks"] if t["parent_id"] == by["sw-01"]["id"]]
    assert [k["tpl_step"] for k in kids] == list(range(1, 8)) and kids[0]["name"] == "Bestellung auslösen"
    # Verkettung: EA, Lag = Lieferzeit-Override (15) statt Vorlage (10); sw-02 ohne Angabe -> 10
    deps = {(x["pred_id"], x["succ_id"]): x for x in d["deps"]}
    assert deps[(kids[0]["id"], kids[1]["id"])]["lag"] == 15 and deps[(kids[1]["id"], kids[2]["id"])]["lag"] == 0
    kids2 = [t for t in d["tasks"] if t["parent_id"] == by["sw-02"]["id"]]
    assert {(x["pred_id"], x["succ_id"]): x for x in d["deps"]}[(kids2[0]["id"], kids2[1]["id"])]["lag"] == 10
    # Wartungsfenster -> Beginn frühestens + Frist am Schritt „Austausch vor Ort“
    ex = kids[4]
    assert ex["name"] == "Austausch vor Ort" and ex["constraint_type"] == "SNET" and ex["constraint_date"] == "2026-11-02" and ex["deadline"] == "2026-11-06"
    # Zuordnung: Rolle Einkauf -> Ressource; übrige Schritte -> Verantwortlich (anna) bzw. Pool
    asg = {(a["task_id"]): a["resource_id"] for a in d["assignments"]}
    anna_res = next(r for r in d["resources"] if r["user_id"] == _IDS["dv_anna"])["id"]
    assert asg[kids[0]["id"]] == res and asg[kids[3]["id"]] == anna_res and kids[3]["pool"] is False
    assert all(t["pool"] and t["id"] not in asg for t in kids2 if t["tpl_step"] >= 3)        # sw-02: kein Verantwortlicher -> Rolle Einkauf (Schritt 1+2), Rest im Pool
    assert kids2[0]["id"] in asg and kids2[1]["id"] in asg and kids2[2]["pool"] is True
    # Plankosten am Bestell-Schritt (Kostenstelle ohne führende Nullen gleich), Kosten stehen im Budget
    fin = owner.get("/api/projects/%d/finance" % pid).json()
    items = [i for i in fin["cost_items"] if i["task_id"] in (kids[0]["id"], kids2[0]["id"])]
    assert sorted(i["amount"] for i in items) == [3890.5, 3890.5] and len({i["cost_center_id"] for i in items}) == 1
    # Rollenzuordnung gemerkt
    assert owner.get("/api/projects/%d/role-map" % pid).json()["map"] == {"Einkauf": res}


def test_reimport_updates_without_duplicates_and_keeps_status(c):
    owner, anna, view, pid = team(c)
    rows = ["rr-01;Zentrale;Switch;Alt-Modell;;;;;;;;OK"]
    do_import(owner, pid, csv_file(*rows), MAP)
    d = tasks_of(owner, pid)
    dev = next(t for t in d["tasks"] if t["name"] == "rr-01")
    first = next(t for t in d["tasks"] if t["parent_id"] == dev["id"])
    owner.patch("/api/tasks/%d" % first["id"], json={"status": "done"})
    n = len(tasks_of(owner, pid)["tasks"])
    rows2 = ["rr-01;Zentrale;Switch;Neues-Modell;09.11.2026;13.11.2026;;;;;;OK", "rr-02;Zentrale;Switch;Nachlieferung;;;;;;;;OK"]
    rep = do_import(owner, pid, csv_file(*rows2), MAP).json()
    assert rep["updated"] == 1 and rep["new"] == 1 and rep["steps"] == 7
    d = tasks_of(owner, pid)
    assert len(d["tasks"]) == n + 1 + 7                                                      # nur das neue Gerät + seine Schritte
    dev = next(t for t in d["tasks"] if t["name"] == "rr-01")
    assert dev["attrs"]["modell"] == "Neues-Modell" and "Neues-Modell" in dev["notes"]
    kids = [t for t in d["tasks"] if t["parent_id"] == dev["id"]]
    assert next(k for k in kids if k["tpl_step"] == 1)["status"] == "done"                  # Status bleibt
    ex = next(k for k in kids if k["tpl_step"] == 5)
    assert ex["constraint_date"] == "2026-11-09" and ex["deadline"] == "2026-11-13"        # Fenster nachgetragen
    assert sum(1 for t in d["tasks"] if t["name"] == "Zentrale") == 1                       # Standort wiederverwendet


def test_errors_partial_and_rights(c, tmp_path):
    owner, anna, view, pid = team(c)
    rows = ["ok-01;Standort A;Switch;M;;;;;;;;OK",
            "ok-01;Standort A;Switch;M;;;;;;;;OK",                      # doppelt
            "x-02;Standort A;Drucker;M;;;;;;;;OK",                      # keine Vorlage
            "x-03;;Switch;M;;;;;;;;OK",                                 # Standort fehlt
            "x-04;Standort B;Switch;M;10.11.2026;02.11.2026;;;;;;OK",   # Fenster von > bis
            "x-05;Standort B;Switch;M;;;;;;;niemand;OK",               # Benutzer unbekannt
            "gut-06;Standort B;Firewall;M;;;;;;;;OK"]
    n0 = len(tasks_of(owner, pid)["tasks"])
    rep = do_import(owner, pid, csv_file(*rows), MAP).json()
    msgs = " | ".join(e["message"] for e in rep["errors"])
    assert rep["error_count"] == 5 and rep["imported"] == 0 and len(tasks_of(owner, pid)["tasks"]) == n0     # alles oder nichts
    for frag in ("bereits vor", "Keine Vorlage", "Pflicht", "liegt nach", "niemand"):
        assert frag in msgs
    rep = do_import(owner, pid, csv_file(*rows), MAP, partial=True).json()
    assert rep["imported"] == 2 and {t["name"] for t in tasks_of(owner, pid)["tasks"]} >= {"ok-01", "gut-06"}          # nur gültige Zeilen
    # Spalten fehlen / Leser / Preise ohne Kostenrecht
    r = owner.post("/api/projects/%d/devices/import" % pid, files=csv_file("a;b;c"), data={"mapping": '{"hostname":0}', "dry_run": "true"})
    assert r.status_code == 422 and "Spalte fehlt" in r.json()["detail"]
    assert view.post("/api/projects/%d/devices/parse" % pid, files=csv_file("a;b;c")).status_code == 403
    rep = do_import(anna, pid, csv_file("pr-01;Standort C;Switch;M;;;;999;;;;OK"), MAP).json()
    assert rep["imported"] == 1 and any("Preise wurden ignoriert" in w for w in rep["warnings"])
    assert not [i for i in owner.get("/api/projects/%d/finance" % pid).json()["cost_items"] if i["amount"] == 999]
    # Rückgängig macht den gesamten Import in einem Schritt rückgängig
    n = len(tasks_of(owner, pid)["tasks"])
    do_import(owner, pid, csv_file("un-01;Standort D;Switch;M;;;;;;;;OK"), MAP)
    assert len(tasks_of(owner, pid)["tasks"]) == n + 1 + 1 + 7
    u = owner.post("/api/projects/%d/undo" % pid)
    assert u.status_code == 200, u.text
    assert len(u.json()["tasks"]) == n


def test_excel_upload_and_single_device(c):
    owner, anna, view, pid = team(c)
    wb = Workbook()
    ws = wb.active
    ws.title = "Geräteliste"
    ws.append(["Hostname *", "Standort *", "Gerätetyp *", "Neues Modell (Bestellartikel)", "Wartungsfenster von", "Wartungsfenster bis", "Preis netto (EUR)", "Kostenstelle", "Prüfung (nicht importiert)"])
    ws.append(["xl-01", "Werk Süd", "Switch", "Extreme", dt.date(2026, 11, 2), dt.date(2026, 11, 4), 4200.5, "100200", "OK"])
    ws.append([None] * 9)
    ws.append(["xl-02", "Werk Süd", "Access Point", "AP", None, None, None, None, "OK"])
    buf = io.BytesIO()
    wb.save(buf)
    files = {"file": ("liste.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    p = owner.post("/api/projects/%d/devices/parse" % pid, files=files).json()
    assert p["sheet"] == "Geräteliste" and p["rows_total"] == 2 and p["mapping"]["modell"] == 3 and p["mapping"]["fenster_von"] == 4 and p["mapping"]["preis"] == 6
    files = {"file": ("liste.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = owner.post("/api/projects/%d/devices/import" % pid, files=files, data={"mapping": __import__("json").dumps(p["mapping"]), "dry_run": "false", "create_missing": "true"})
    rep = r.json()
    assert r.status_code == 200 and rep["imported"] == 2 and rep["error_count"] == 0
    d = tasks_of(owner, pid)
    ex = next(t for t in d["tasks"] if t["name"] == "Austausch vor Ort" and t["deadline"] == "2026-11-04")
    assert ex["constraint_date"] == "2026-11-02"
    assert any(i["amount"] == 4200.5 for i in owner.get("/api/projects/%d/finance" % pid).json()["cost_items"])
    # einzelnes Gerät aus Vorlage
    tid = next(t["id"] for t in c.get("/api/templates").json() if t["name"] == "Firewall")
    d = owner.post("/api/projects/%d/devices" % pid, json={"template_id": tid, "hostname": "fw-solo", "standort": "Werk Süd", "modell": "FG-100F"}).json()
    dev = next(t for t in d["tasks"] if t["name"] == "fw-solo")
    assert len([t for t in d["tasks"] if t["parent_id"] == dev["id"]]) == 6
    assert owner.post("/api/projects/%d/devices" % pid, json={"template_id": tid, "hostname": "fw-solo", "standort": "x"}).status_code == 200      # vorhanden -> Aktualisierung
    assert owner.post("/api/projects/%d/devices" % pid, json={"template_id": 99999, "hostname": "a"}).status_code == 404


def test_sample_xlsx_matches_templates_and_imports(c):
    from openpyxl import load_workbook
    r = c.get("/api/templates/sample.xlsx")
    assert r.status_code == 200 and "spreadsheetml" in r.headers["content-type"]
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Anleitung", "Geräteliste", "Schritte (Vorlagen)", "Listen"]
    names = {t["name"] for t in c.get("/api/templates").json()}
    assert {x.value for x in wb["Listen"]["A"][1:] if x.value} == names
    assert names <= {x.value for x in wb["Schritte (Vorlagen)"]["A"] if x.value}
    # die erzeugte Datei lässt sich unverändert importieren (Trockenlauf)
    owner, anna, view, pid = team(c)
    files = {"file": ("m.xlsx", r.content, "application/octet-stream")}
    parsed = owner.post("/api/projects/%d/devices/parse" % pid, files=files).json()
    mapping = {k: v for k, v in parsed["mapping"].items() if k != "verantwortlich"}
    rep = owner.post("/api/projects/%d/devices/import" % pid, files={"file": ("m.xlsx", r.content, "application/octet-stream")},
                     data={"mapping": __import__("json").dumps(mapping), "dry_run": "true", "create_missing": "true"}).json()
    assert rep["error_count"] == 0 and rep["new"] == 8, rep


def _inventory_xlsx():
    """Inventarliste im Stil des Monitoring-Exports (Präfix INV_, Location-Code, unsichtbare Zeichen, uneinheitliche Priorität)."""
    wb = Workbook()
    ws = wb.active
    ws.append(["Node Name", "IP_Address", "INV_Serial_Number", "INV_Model_ID", "INV_City", "Inv_Location", "Location", "INV_Priority",
               "Inv_Location_ID", "INV_Function"])
    ws.append(["r-de-ne-core-01", "192.0.2.2", "FDO1", "WS-C3750X-24S-S", "Musterwerk", "Germany-Musterwerk-Am Werk 6", "LOC024__DE.Musterwerk", "Business Critical", "LOC024", "Switch"])
    ws.append(["sw-de-ne-acc-01", "192.0.2.3", "FDO2", "WS-C2960S-24TS-L", "Muster​werk", "Germany-Musterwerk", "LOC024_DE.Musterwerk", "non business critical", "LOC024", "Switch"])
    ws.append(["sw-de-ne-acc-02", "192.0.2.3", "FDO2", "IE-4000-8GT4G-E", "Musterwerk ", "Germany-Musterwerk", "", "Low Priority", "LOC024", "Switch"])
    ws.append(["sw-de-el-acc-01", "198.51.100.5", "FDO9", "WS-C2960S-24TS-L", "Ellers", "", "", "LOW PRIORITY", "", "Switch"])
    ws.append(["sw-de-ne-acc-03", "192.0.2.9", "FDO7", "WS-C2960S-24TS-L", "Musterwerk", "", "LOC024__DE.Musterwerk", "Low Priority", "", "Switch"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_inventory_columns_location_code_and_cleaning(c, monkeypatch):
    monkeypatch.setattr(devices, "IMPORT_HEADER_PREFIXES", ["inv"])      # Präfix per IMPORT_HEADER_PREFIXES konfigurierbar
    owner, anna, view, pid = team(c)
    f = lambda: {"file": ("inventar.xlsx", _inventory_xlsx(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}      # noqa: E731
    p = owner.post("/api/projects/%d/devices/parse" % pid, files=f()).json()
    m = p["mapping"]
    # Spalten werden trotz Präfix INV_ erkannt; „City“ gewinnt vor „Location“ als Standort; Code aus Inv_Location_ID
    assert (m["hostname"], m["ip"], m["alt_seriennummer"], m["alt_modell"], m["standort"], m["prio"], m["loc"]) == (0, 1, 2, 3, 4, 7, 8)
    assert p["cleaned"] >= 2                                                         # Zero-Width-Zeichen und geschütztes Leerzeichen
    # Gerätetyp gibt es in der Liste nicht -> aus der Funktion (Spalte 9) ableiten: hier einfach „Switch“-Spalte zuordnen
    m["typ"] = 9
    r = owner.post("/api/projects/%d/devices/import" % pid, files=f(), data={"mapping": __import__("json").dumps(m), "dry_run": "false"}).json()
    assert r["error_count"] == 0 and r["new"] == 5, r
    d = tasks_of(owner, pid)
    sites = [t["name"] for t in d["tasks"] if t["summary"] and t["parent_id"] is None]
    assert sorted(sites) == ["Ellers", "LOC024 – Musterwerk"]                           # Musterwerk in allen Schreibweisen = ein Standort, Code im Phasennamen
    assert len([t for t in d["tasks"] if t["parent_id"] and t["name"].startswith("sw-de-ne") or t["name"] == "r-de-ne-core-01"]) >= 4
    dev = next(t for t in d["tasks"] if t["name"] == "sw-de-ne-acc-02")
    assert dev["attrs"]["loc"] == "LOC024" and dev["attrs"]["standort"] == "Musterwerk" and dev["attrs"]["prio"] == "Low Priority"
    assert next(t for t in d["tasks"] if t["name"] == "sw-de-ne-acc-01")["attrs"]["prio"] == "Non Business Critical"       # vereinheitlicht
    assert next(t for t in d["tasks"] if t["name"] == "sw-de-el-acc-01")["attrs"]["prio"] == "Low Priority"
    warn = " | ".join(r["warnings"])
    assert "IP-Adresse 192.0.2.3" in warn and "Seriennummer FDO2" in warn and "bereinigt" in warn


def test_location_code_from_text_and_required_site_or_code(c):
    owner, anna, view, pid = team(c)
    head = "Hostname;Standort;Gerätetyp"
    rows = ["h-1;LOC024__DE.Musterwerk;Switch", "h-2;LOC024_Musterwerk_Germany;Switch", "h-3;;Switch"]
    dry = do_import(owner, pid, csv_file(*rows, head=head), {"hostname": 0, "standort": 1, "typ": 2}, dry_run=True).json()
    assert dry["error_count"] == 1 and "Pflicht" in dry["errors"][0]["message"]
    r = do_import(owner, pid, csv_file(*rows, head=head), {"hostname": 0, "standort": 1, "typ": 2}, partial=True).json()
    assert r["new"] == 2 and r["error_count"] == 1
    sites = [t["name"] for t in tasks_of(owner, pid)["tasks"] if t["summary"] and t["parent_id"] is None]
    assert sites == ["LOC024__DE.Musterwerk"]                                           # Code aus Text erkannt: beide Zeilen = ein Standort
    # nur Location-Code ohne Standort-Spalte
    r = do_import(owner, pid, csv_file("h-4;LOC077;Switch", head="Hostname;Location-Code;Gerätetyp"), {"hostname": 0, "loc": 1, "typ": 2}).json()
    assert r["new"] == 1
    assert "LOC077" in [t["name"] for t in tasks_of(owner, pid)["tasks"] if t["summary"] and t["parent_id"] is None]
