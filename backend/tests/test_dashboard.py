from test_api import _login, c, mk  # noqa: F401,E402  (setzt DATA_DIR/ADMIN_PASSWORD vor allen App-Importen)

import datetime as dt  # noqa: E402

import dashboard  # noqa: E402
import overview  # noqa: E402

PW = "passwort-"


def add(cl, pid, name, dur=5, **kw):
    d = cl.post("/api/projects/%d/tasks" % pid, json={"name": name, "duration": dur, **kw}).json()
    return [t for t in d["tasks"] if t["name"] == name][0]["id"]


def status(cl, pid, ids, st):
    assert cl.post("/api/projects/%d/tasks/status" % pid, json={"task_ids": ids, "status": st}).status_code == 200


def by_name(d):
    return {p["name"]: p for p in d["projects"]}


def test_rag_rules_and_sections(c):
    # „heute“ liegt nach den Plandaten (Projektstart 2026-10-12) -> Vorgänge sind überfällig, solange sie nicht erledigt sind
    dashboard._today = overview._today = lambda: dt.date(2026, 11, 20)
    pr = {n: mk(c, n)["project"]["id"] for n in ("DB Grün", "DB Gelb", "DB Rot-Blockiert", "DB Rot-Prozent", "DB Rot-Frist", "DB Fertig", "DB Leer")}
    # Fertig: alles erledigt
    status(c, pr["DB Fertig"], [add(c, pr["DB Fertig"], "x")], "done")
    # Grün: nur Zukunft (Beginn nach „heute“)
    add(c, pr["DB Grün"], "Später", 3, constraint_type="SNET", constraint_date="2026-12-01")
    # Gelb: 1 von 12 überfällig (8 %) + erledigte
    ids = [add(c, pr["DB Gelb"], "G%d" % i) for i in range(12)]
    status(c, pr["DB Gelb"], ids[1:], "done")
    # Rot (Prozent): 2 von 12 überfällig (17 %)
    ids = [add(c, pr["DB Rot-Prozent"], "P%d" % i) for i in range(12)]
    status(c, pr["DB Rot-Prozent"], ids[2:], "done")
    # Rot (blockiert): ein blockierter Vorgang in der Zukunft
    b = add(c, pr["DB Rot-Blockiert"], "Blockiert", 3, constraint_type="SNET", constraint_date="2026-12-01")
    status(c, pr["DB Rot-Blockiert"], [b], "blocked")
    # Rot (Frist): geplantes Ende nach der Frist
    add(c, pr["DB Rot-Frist"], "Frist", 5, constraint_type="SNET", constraint_date="2026-12-01", deadline="2026-12-03")
    add(c, pr["DB Rot-Frist"], "Meilenstein", 0, constraint_type="SNET", constraint_date="2026-12-10")

    d = c.get("/api/dashboard").json()
    p = by_name(d)
    assert p["DB Grün"]["status"] == "green" and p["DB Grün"]["reasons"] == []
    assert p["DB Gelb"]["status"] == "yellow" and p["DB Gelb"]["reasons"][0]["key"] == "overdue"
    assert p["DB Rot-Prozent"]["status"] == "red" and p["DB Rot-Prozent"]["reasons"][0]["key"] == "overdue_pct" and p["DB Rot-Prozent"]["reasons"][0]["pct"] == 17
    assert p["DB Rot-Blockiert"]["status"] == "red" and p["DB Rot-Blockiert"]["blocked"] == 1
    assert p["DB Rot-Frist"]["status"] == "red" and p["DB Rot-Frist"]["deadline_missed"] == 1
    assert p["DB Fertig"]["status"] == "done" and p["DB Fertig"]["percent"] == 100 and p["DB Leer"]["status"] == "empty"
    order = [x["status"] for x in d["projects"]]
    assert order == sorted(order, key=lambda s: dashboard.ORDER[s])                      # rot zuerst, dann gelb, grün, fertig, leer
    k = d["kpi"]
    assert k["status"]["red"] >= 3 and k["blocked"] >= 1 and k["deadline_missed"] >= 1 and k["overdue"] >= 3
    kinds = {r["kind"] for r in d["risks"]["items"]}
    assert {"deadline", "blocked", "overdue"} <= kinds and d["risks"]["items"][0]["kind"] == "deadline"
    ms = [m for m in d["milestones"] if m["project"] == "DB Rot-Frist"]
    assert ms and ms[0]["date"] == "2026-12-10" and ms[0]["late"] is False
    assert p["DB Rot-Frist"]["next_milestone"]["name"] == "Meilenstein"
    assert d["cost"] is None or isinstance(d["cost"], dict)


def test_dashboard_is_scoped_and_masks_budget(c):
    dashboard._today = overview._today = lambda: dt.date(2026, 11, 20)
    c.post("/api/users", json={"username": "db_ed", "password": PW + "db_ed", "role": "editor"})
    pid = mk(c, "DB Fremd")["project"]["id"]
    add(c, pid, "T")
    ed = _login("db_ed", PW + "db_ed")
    assert "DB Fremd" not in by_name(ed.get("/api/dashboard").json())                   # kein Zugriff -> nicht sichtbar
    own = ed.post("/api/projects", json={"name": "DB Eigen", "start_date": "2026-10-12"}).json()["project"]["id"]
    d = ed.get("/api/dashboard").json()
    assert "DB Eigen" in by_name(d) and "DB Fremd" not in by_name(d)
    c.put("/api/projects/%d/members" % pid, json=[])
    assert all(p["budget"] is None or isinstance(p["budget"], dict) for p in d["projects"])
    assert c.get("/api/dashboard").status_code == 200 and own


def test_portfolio_report_uses_the_same_traffic_light(c):
    import database
    import portfolio
    today = dt.date(2026, 11, 20)
    dashboard._today = overview._today = lambda: today
    pr = {n: mk(c, n)["project"]["id"] for n in ("PF Grün", "PF Gelb", "PF Rot-Block", "PF Rot-Prozent", "PF Rot-Frist", "PF Fertig")}
    status(c, pr["PF Fertig"], [add(c, pr["PF Fertig"], "x")], "done")
    add(c, pr["PF Grün"], "Später", 3, constraint_type="SNET", constraint_date="2026-12-01")
    ids = [add(c, pr["PF Gelb"], "G%d" % i) for i in range(12)]
    status(c, pr["PF Gelb"], ids[1:], "done")
    ids = [add(c, pr["PF Rot-Prozent"], "P%d" % i) for i in range(12)]
    status(c, pr["PF Rot-Prozent"], ids[2:], "done")
    status(c, pr["PF Rot-Block"], [add(c, pr["PF Rot-Block"], "B", 3, constraint_type="SNET", constraint_date="2026-12-01")], "blocked")
    add(c, pr["PF Rot-Frist"], "Frist", 5, constraint_type="SNET", constraint_date="2026-12-01", deadline="2026-12-03")
    dash = by_name(c.get("/api/dashboard").json())
    db = database.connect()
    try:
        for name, pid in pr.items():
            line = portfolio.project_line(db, pid, False, today)
            assert line["rag"] == dash[name]["status"], name                          # Report und Dashboard zeigen dieselbe Farbe
            assert line["reasons"] == dash[name]["reasons"], name
        assert portfolio.project_line(db, pr["PF Rot-Block"], False, today)["rag"] == "red"      # früher nur gelb
        sub = {"project_ids": ",".join(str(i) for i in pr.values()), "include_costs": 0, "name": "x", "kind": "portfolio"}
        rep = portfolio.build_portfolio(db, sub, today)
        assert rep["counts"] == {"red": 3, "yellow": 1, "green": 1, "done": 1}
        txt = portfolio.render_text(rep, "", 1)
        assert "1 abgeschlossen" in txt and "Grund:" in txt and "Frist(en) überschritten" in txt
        assert "completed" in portfolio.render_text(rep, "", 1, "en") and "reason:" in portfolio.render_text(rep, "", 1, "en")
        assert "abgeschlossen" in portfolio.render_html(rep, "", 1)
    finally:
        db.close()
