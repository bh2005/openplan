from test_api import c, mk  # noqa: F401,E402  (setzt DATA_DIR/ADMIN_PASSWORD vor allen App-Importen)

import urllib.error  # noqa: E402

import feiertage  # noqa: E402

ITEMS = [
    {"date": "2026-01-01", "name": "Neujahr", "states": list(feiertage.STATES)},
    {"date": "2026-01-06", "name": "Heilige Drei Könige", "states": ["bw", "by", "st"]},
    {"date": "2026-06-04", "name": "Fronleichnam", "states": ["bw", "by", "he", "nw", "rp", "sl"]},
]


def fake(monkeypatch, calls):
    def _f(year, base=None):
        calls.append(year)
        return [{**e, "date": e["date"].replace("2026", str(year))} for e in ITEMS]
    monkeypatch.setattr(feiertage, "_fetch", _f)


def test_filter_by_state_and_cache(c, monkeypatch):
    calls = []
    fake(monkeypatch, calls)
    r = c.get("/api/holidays?state=nw&years=2031,2032").json()
    assert [h["name"] for h in r["holidays"]] == ["Neujahr", "Fronleichnam", "Neujahr", "Fronleichnam"]
    assert r["missing_years"] == []
    r = c.get("/api/holidays?state=st&years=2031").json()      # zweiter Aufruf kommt aus dem Cache
    assert [h["name"] for h in r["holidays"]] == ["Neujahr", "Heilige Drei Könige"]
    assert calls == [2031, 2032]


def test_api_down_uses_cache_or_fails(c, monkeypatch):
    def boom(year, base=None):
        raise urllib.error.URLError("proxy")
    monkeypatch.setattr(feiertage, "_fetch", boom)
    assert c.get("/api/holidays?state=nw&years=2041").status_code == 502          # kein Cache
    calls = []
    fake(monkeypatch, calls)
    c.get("/api/holidays?state=nw&years=2042")
    monkeypatch.setattr(feiertage, "_fetch", boom)
    monkeypatch.setattr(feiertage, "CACHE_DAYS", 0)                                  # abgelaufen -> Abruf scheitert -> alter Cache
    assert len(c.get("/api/holidays?state=nw&years=2042").json()["holidays"]) == 2


def test_unsupported_year_reported_missing(c, monkeypatch):
    monkeypatch.setattr(feiertage, "_fetch", lambda y, b=None: ITEMS if y == 2051 else [])
    r = c.get("/api/holidays?state=nw&years=2051,2052").json()
    assert r["missing_years"] == [2052] and len(r["holidays"]) == 2


def test_validation(c):
    assert c.get("/api/holidays?state=xx&years=2026").status_code == 422
    assert c.get("/api/holidays?state=nw&years=abc").status_code == 422
    assert c.get("/api/holidays?state=nw&years=2026,2027,2028,2029,2030,2031").status_code == 422
    assert len(c.get("/api/holidays/states").json()) == 16


def test_project_holiday_state(c):
    pid = mk(c)["project"]["id"]
    assert c.get("/api/projects/%d" % pid).json()["project"]["holiday_state"] == ""
    r = c.patch("/api/projects/%d" % pid, json={"holiday_state": "NW"})
    assert r.status_code == 200 and r.json()["project"]["holiday_state"] == "nw"
    assert c.patch("/api/projects/%d" % pid, json={"holiday_state": "zz"}).status_code == 422
    w = c.post("/api/projects/wizard", json={"name": "W", "start_date": "2026-10-12", "holiday_state": "he"}).json()
    assert w["project"]["holiday_state"] == "he"


def test_admin_url_setting_cache_and_test(c, monkeypatch):
    seen = []

    def _f(year, base=None):
        seen.append((year, base))
        return [dict(e, date=e["date"].replace("2026", str(year))) for e in ITEMS]
    monkeypatch.setattr(feiertage, "_fetch", _f)
    d = c.get("/api/admin/settings/holidays").json()
    assert d["url"] == "" and d["default"] == feiertage.DEFAULT_URL
    c.get("/api/holidays?state=nw&years=2061")
    assert seen[-1] == (2061, feiertage.DEFAULT_URL) and 2061 in [x["year"] for x in c.get("/api/admin/settings/holidays").json()["cache"]]
    assert c.put("/api/admin/settings/holidays", json={"url": "ftp://x"}).status_code == 422
    assert c.put("/api/admin/settings/holidays", json={"url": "https://"}).status_code == 422
    r = c.put("/api/admin/settings/holidays", json={"url": "https://intern.example/feiertage"})
    assert r.json()["url"] == "https://intern.example/feiertage" and r.json()["cache"] == []          # URL geändert -> Cache geleert
    c.get("/api/holidays?state=nw&years=2062")
    assert seen[-1] == (2062, "https://intern.example/feiertage")
    n = len(c.get("/api/admin/settings/holidays").json()["cache"])
    c.put("/api/admin/settings/holidays", json={"url": "https://intern.example/feiertage"})           # gleiche URL -> Cache bleibt
    assert len(c.get("/api/admin/settings/holidays").json()["cache"]) == n == 1
    t = c.post("/api/admin/settings/holidays/test", json={"url": "https://probe.example/x?a=1"}).json()
    assert t["ok"] and t["count"] == 3 and t["called"].startswith("https://probe.example/x?a=1&years=") and seen[-1][1] == "https://probe.example/x?a=1"
    assert c.get("/api/admin/settings/holidays").json()["url"] == "https://intern.example/feiertage"     # Test speichert nichts
    assert c.delete("/api/admin/settings/holidays/cache").json()["cache"] == []
    c.put("/api/admin/settings/holidays", json={"url": ""})
    assert c.get("/api/admin/settings/holidays").json()["url"] == ""


def test_admin_test_reports_failure_and_build_url(c, monkeypatch):
    def boom(year, base=None):
        raise urllib.error.URLError("nicht erreichbar")
    monkeypatch.setattr(feiertage, "_fetch", boom)
    t = c.post("/api/admin/settings/holidays/test", json={}).json()
    assert t["ok"] is False and "nicht erreichbar" in t["message"]
    assert feiertage.build_url("https://a/b", 2026) == "https://a/b?years=2026"
    assert feiertage.build_url("https://a/b?x=1", 2026) == "https://a/b?x=1&years=2026"
    assert feiertage.build_url("https://a/{year}.json", 2026) == "https://a/2026.json"


def test_admin_setting_needs_admin(c):
    c.post("/api/users", json={"username": "hol_ed", "password": "passwort-hol_ed", "role": "editor"})
    from test_api import _login
    ed = _login("hol_ed", "passwort-hol_ed")
    assert ed.get("/api/admin/settings/holidays").status_code == 403
    assert ed.put("/api/admin/settings/holidays", json={"url": ""}).status_code == 403
    assert ed.post("/api/admin/settings/holidays/test", json={}).status_code == 403
