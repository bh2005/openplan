from test_api import c, mk  # noqa: F401,E402  (setzt DATA_DIR/ADMIN_PASSWORD vor allen App-Importen)

import datetime as dt  # noqa: E402

import leveling  # noqa: E402


def setup(c, name, today=dt.date(2026, 10, 1)):
    leveling._today = lambda: today
    pid = mk(c, name)["project"]["id"]
    rid = [r for r in c.post("/api/projects/%d/resources" % pid, json={"name": "Anna", "max_units": 100}).json()["resources"]][0]["id"]
    return pid, rid


def add(c, pid, name, dur, rid=None, **kw):
    d = c.post("/api/projects/%d/tasks" % pid, json={"name": name, "duration": dur, **kw}).json()
    tid = [t for t in d["tasks"] if t["name"] == name][0]["id"]
    if rid:
        c.put("/api/tasks/%d/assignments" % tid, json=[{"resource_id": rid, "units": 100}])
    return tid


def test_overload_resolved_within_float(c):
    pid, rid = setup(c, "Lv1")
    a, b = add(c, pid, "A", 2, rid), add(c, pid, "B", 2, rid)
    add(c, pid, "Lang", 10)                                           # hält das Projektende offen -> A, B haben Puffer
    p = c.get("/api/projects/%d/leveling" % pid).json()
    assert p["conflicts_before"] == 2 and p["conflicts_after"] == 0
    assert len(p["moves"]) == 1 and p["moves"][0]["shift"] == 2 and p["moves"][0]["new_start"] == "2026-10-14"
    r = c.post("/api/projects/%d/leveling/apply" % pid, json={"moves": [{"task_id": p["moves"][0]["task_id"], "new_start": p["moves"][0]["new_start"]}]})
    assert r.status_code == 200
    moved = [t for t in r.json()["tasks"] if t["id"] == p["moves"][0]["task_id"]][0]
    assert moved["start"] == "2026-10-14" and moved["constraint_type"] == "SNET"
    p2 = c.get("/api/projects/%d/leveling" % pid).json()
    assert p2["moves"] == [] and p2["conflicts_before"] == 0
    assert c.post("/api/projects/%d/undo" % pid).json()["tasks"] is not None            # mit Undo rücknehmbar
    assert c.get("/api/projects/%d/leveling" % pid).json()["conflicts_before"] == 2


def test_absence_pushes_task_behind_absence(c):
    pid, rid = setup(c, "Lv2")
    add(c, pid, "A", 3, rid)
    add(c, pid, "Lang", 10)
    c.post("/api/projects/%d/absences" % pid, json={"resource_id": rid, "start_date": "2026-10-13", "end_date": "2026-10-14"})
    p = c.get("/api/projects/%d/leveling" % pid).json()
    assert [m["new_start"] for m in p["moves"]] == ["2026-10-15"] and p["conflicts_after"] == 0     # Di+Mi weg -> Start Do


def test_unresolved_when_no_float(c):
    pid, rid = setup(c, "Lv3")
    a, b = add(c, pid, "A", 2, rid), add(c, pid, "B", 2, rid)          # beide bilden das Projektende -> kein Puffer
    p = c.get("/api/projects/%d/leveling" % pid).json()
    assert p["moves"] == [] and p["conflicts_after"] == 2 and p["unresolved"][0]["resource"] == "Anna"


def test_past_done_and_manual_are_left_alone(c):
    pid, rid = setup(c, "Lv4", today=dt.date(2026, 12, 1))               # Konflikte liegen in der Vergangenheit
    add(c, pid, "A", 2, rid); add(c, pid, "B", 2, rid); add(c, pid, "Lang", 10)
    assert c.get("/api/projects/%d/leveling" % pid).json()["conflicts_before"] == 0
    pid, rid = setup(c, "Lv5")
    add(c, pid, "A", 2, rid, constraint_type="MSO", constraint_date="2026-10-12")
    add(c, pid, "B", 2, rid, constraint_type="MSO", constraint_date="2026-10-12"); add(c, pid, "Lang", 10)
    p = c.get("/api/projects/%d/leveling" % pid).json()
    assert p["moves"] == [] and p["conflicts_after"] == 2                  # manuell geplant = nicht verschiebbar


def test_apply_validation(c):
    pid, rid = setup(c, "Lv6")
    a = add(c, pid, "A", 2, rid); add(c, pid, "B", 2, rid)
    assert c.post("/api/projects/%d/leveling/apply" % pid, json={"moves": [{"task_id": a, "new_start": "2026-10-14"}]}).status_code == 422    # kein Puffer
    add(c, pid, "Lang", 10)
    assert c.post("/api/projects/%d/leveling/apply" % pid, json={"moves": [{"task_id": a, "new_start": "2026-10-17"}]}).status_code == 422    # Samstag
    assert c.post("/api/projects/%d/leveling/apply" % pid, json={"moves": [{"task_id": a, "new_start": "2026-10-12"}]}).status_code == 422    # keine Verschiebung
    assert c.post("/api/projects/%d/leveling/apply" % pid, json={"moves": [{"task_id": a, "new_start": "2026-10-14"}]}).status_code == 200
