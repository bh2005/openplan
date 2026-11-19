import os
import sys
import tempfile

import pytest

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
os.environ.setdefault("ADMIN_PASSWORD", "testpass123")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


def login(u, p):
    cl = TestClient(app)
    cl.headers["Authorization"] = "Bearer " + cl.post("/api/auth/login", json={"username": u, "password": p}).json()["token"]
    return cl


@pytest.fixture(scope="module")
def c():
    with TestClient(app):  # Lifespan/DB-Init
        pass
    return login("admin", os.environ["ADMIN_PASSWORD"])


@pytest.fixture()
def proj(c):
    d = c.post("/api/projects", json={"name": "Fin", "start_date": "2026-10-12"}).json()
    pid = d["project"]["id"]
    t1 = c.post("/api/projects/%d/tasks" % pid, json={"name": "A", "duration": 5}).json()["tasks"][0]["id"]
    cc = c.post("/api/projects/%d/cost-centers" % pid, json={"code": "0000100200", "name": "IT"}).json()["cost_centers"][0]["id"]
    ct = c.post("/api/projects/%d/cost-types" % pid, json={"code": "400000", "name": "Fremdleistung"}).json()["cost_types"][0]["id"]
    return {"pid": pid, "t1": t1, "cc": cc, "ct": ct}


def test_plan_budget_and_controlling(c, proj):
    p = proj
    r = c.post("/api/projects/%d/resources" % p["pid"], json={"name": "Anna", "cost_rate": 100, "cost_center_id": p["cc"], "cost_type_id": p["ct"]}).json()
    rid = r["resources"][0]["id"]
    assert r["resources"][0]["cost_rate"] == 100 and r["cost_access"] == "edit"
    c.put("/api/tasks/%d/assignments" % p["t1"], json=[{"resource_id": rid, "units": 100}])
    c.post("/api/tasks/%d/cost-items" % p["t1"], json={"amount": 500, "cost_center_id": p["cc"], "cost_type_id": p["ct"], "description": "Lizenz"})
    assert c.put("/api/projects/%d/budget-lines" % p["pid"], json=[{"amount": 900}]).status_code == 200
    c.post("/api/projects/%d/actuals" % p["pid"], json={"booking_date": "2026-10-14", "amount": 400, "task_id": p["t1"],
                                                       "cost_center_id": p["cc"], "cost_type_id": p["ct"], "reference": "4900001"})
    c.patch("/api/tasks/%d" % p["t1"], json={"percent": 50})
    b = c.get("/api/projects/%d/budget?status=2026-10-16" % p["pid"]).json()
    s = b["summary"]
    assert s["plan"] == 1000 and s["bac"] == 1000 and s["ac"] == 400 and s["ev"] == 500   # 5 AT × 100 + 500
    assert s["plan_over_budget"] is True and s["budget"] == 900 and s["remaining_budget"] == 500
    assert s["cpi"] == pytest.approx(1.25) and s["pv"] == pytest.approx(1000)
    assert b["by_cost_center"][0]["plan"] == 1000 and b["by_cost_center"][0]["actual"] == 400
    assert b["per_task"][str(p["t1"])]["actual"] == 400

    # Basisplan friert Plankosten ein; spätere Planänderung ändert BAC nicht
    c.post("/api/projects/%d/baseline" % p["pid"])
    c.patch("/api/tasks/%d" % p["t1"], json={"duration": 10})
    s = c.get("/api/projects/%d/budget" % p["pid"]).json()["summary"]
    assert s["bac"] == 1000 and s["plan"] == 1500

    csv_ = c.get("/api/projects/%d/budget/export?what=matrix" % p["pid"])
    assert csv_.status_code == 200 and b"0000100200 IT" in csv_.content


def test_cost_permissions(c, proj):
    p = proj
    c.post("/api/users", json={"username": "fin_m", "password": "passwort-fin", "role": "editor"})
    uid = next(u["id"] for u in c.get("/api/users").json() if u["username"] == "fin_m")
    c.put("/api/projects/%d/members" % p["pid"], json=[{"user_id": uid, "role": "editor"}])
    m = login("fin_m", "passwort-fin")
    # Mitglied: Plan sichtbar, Kosten nicht
    assert m.get("/api/projects/%d/budget" % p["pid"]).status_code == 403
    assert m.get("/api/projects/%d/finance" % p["pid"]).status_code == 403
    assert m.post("/api/projects/%d/actuals" % p["pid"], json={"booking_date": "2026-10-14", "amount": 1}).status_code == 403
    r = c.post("/api/projects/%d/resources" % p["pid"], json={"name": "Geheim", "cost_rate": 999}).json()
    assert "cost_rate" not in m.get("/api/projects/%d" % p["pid"]).json()["resources"][0]
    # Freigabe: Mitglied darf lesen, aber nicht schreiben
    c.put("/api/projects/%d/finance/settings" % p["pid"], json={"members_see_costs": True})
    assert m.get("/api/projects/%d/budget" % p["pid"]).status_code == 200
    assert m.post("/api/projects/%d/actuals" % p["pid"], json={"booking_date": "2026-10-14", "amount": 1}).status_code == 403
    # Mitglied mit editor-Rechten darf Ressource anlegen, Kostensatz wird aber ignoriert
    rr = m.post("/api/projects/%d/resources" % p["pid"], json={"name": "Neu", "cost_rate": 500}).json()
    assert next(x for x in rr["resources"] if x["name"] == "Neu")["cost_rate"] == 0   # 500 wurde ignoriert
    assert r["resources"]


def test_master_data_rules(c, proj):
    p = proj
    assert c.post("/api/projects/%d/cost-centers" % p["pid"], json={"code": "0000100200"}).status_code == 409
    c.post("/api/tasks/%d/cost-items" % p["t1"], json={"amount": 10, "cost_center_id": p["cc"]})
    assert c.delete("/api/cost-centers/%d" % p["cc"]).status_code == 409          # noch referenziert
    imp = c.post("/api/projects/%d/cost-types/import" % p["pid"], json={"text": "Kostenart;Name\n410000;Material\n400000;Fremd (neu)"}).json()
    assert {x["code"]: x["name"] for x in imp["cost_types"]} == {"400000": "Fremd (neu)", "410000": "Material"}
    other = c.post("/api/projects", json={"name": "Anderes", "start_date": "2026-10-12"}).json()["project"]["id"]
    r = c.post("/api/projects/%d/actuals" % other, json={"booking_date": "2026-10-14", "amount": 1, "cost_center_id": p["cc"]})
    assert r.status_code == 422                                                    # fremde Kostenstelle


CSV = ("Buchungsdatum;Kostenstelle;Kostenart;Betrag;Währung;Belegnummer;Text\n"
       "15.10.2026;100200;400000;1.234,56;EUR;4900100;Beratung\n"
       "16.10.2026;0000100200;400000;-34,56;EUR;4900101;Gutschrift\n"
       "17.10.2026;999999;400000;10,00;EUR;4900102;falsche KST\n"
       "18.10.2026;100200;400000;5,00;USD;4900103;Fremdwährung\n")


def test_import_dry_run_atomic_and_duplicates(c, proj):
    p = proj
    f = {"file": ("sap.csv", CSV.encode("cp1252"), "text/csv")}
    r = c.post("/api/projects/%d/actuals/import" % p["pid"], files=f, data={"dry_run": "true"}).json()
    assert r["valid"] == 2 and r["error_count"] == 2 and r["sum"] == 1200.0     # führende Nullen werden normalisiert
    assert {e["row"] for e in r["errors"]} == {4, 5}
    # Echt-Import mit Fehlern: atomar -> nichts importiert
    r = c.post("/api/projects/%d/actuals/import" % p["pid"], files=f, data={"dry_run": "false"}).json()
    assert r["imported"] == 0
    assert c.get("/api/projects/%d/actuals" % p["pid"]).json()["total"] == 0
    # partial=true: gültige Zeilen werden übernommen
    r = c.post("/api/projects/%d/actuals/import" % p["pid"], files=f, data={"dry_run": "false", "partial": "true"}).json()
    assert r["imported"] == 2
    a = c.get("/api/projects/%d/actuals" % p["pid"]).json()
    assert a["total"] == 2 and a["sum"] == pytest.approx(1200.0)
    # Erneuter Import: Dubletten (Belegnummer) werden übersprungen
    r = c.post("/api/projects/%d/actuals/import" % p["pid"], files=f, data={"dry_run": "false", "partial": "true"}).json()
    assert r["imported"] == 0 and r["duplicates"] == 2


def test_import_create_missing_and_bad_header(c, proj):
    p = proj
    f = {"file": ("x.csv", b"Buchungsdatum;Kostenstelle;Betrag\n15.10.2026;777;10,00\n", "text/csv")}
    r = c.post("/api/projects/%d/actuals/import" % p["pid"], files=f, data={"dry_run": "false", "create_missing": "true"}).json()
    assert r["imported"] == 1 and r["new_cost_centers"] == ["777"]
    bad = {"file": ("x.csv", b"Foo;Bar\n1;2\n", "text/csv")}
    assert c.post("/api/projects/%d/actuals/import" % p["pid"], files=bad, data={"dry_run": "true"}).status_code == 422


def test_demo_project(c):
    d = c.post("/api/projects/demo").json()
    pid = d["project"]["id"]
    leaves = [t for t in d["tasks"] if not t["summary"]]
    assert len(d["resources"]) == 3 and d["project"]["owner"]["username"] == "admin"
    assert sum(1 for t in leaves if t["milestone"]) >= 6 and len(leaves) > 30
    names = " ".join(t["name"] for t in d["tasks"])
    assert "60 Geräte" in names and "Werk Nord" in names and "Logistikzentrum" in names
    st = {t["status"] for t in leaves}
    assert {"done", "open", "blocked"} <= st                      # Fortschritt, Blockade und offene Arbeit
    assert any(t["baseline_start"] for t in leaves)               # Basisplan vorhanden
    assert any(t["baseline_finish"] and t["finish"] > t["baseline_finish"] for t in leaves)   # ... mit Verzug
    b = c.get("/api/projects/%d/budget" % pid).json()
    s = b["summary"]
    assert s["budget"] == 260000 and s["ac"] > 90000 and s["bac"] > 200000 and s["ev"] > 0
    assert len(b["by_cost_center"]) >= 4 and len(b["by_cost_type"]) >= 5
    f = c.get("/api/projects/%d/finance" % pid).json()
    assert len(f["cost_centers"]) == 5 and len(f["cost_items"]) >= 10
    assert c.get("/api/projects/%d/actuals" % pid).json()["total"] >= 3
