"""Gesetzliche Feiertage je Bundesland (Quelle: https://get.api-feiertage.de).

Die API liefert je Jahr alle Feiertage mit einem Flag je Bundesland. ``?all_states=true`` würde nur die bundesweiten
Feiertage zurückgeben, deshalb wird ohne diesen Parameter abgefragt und serverseitig nach Bundesland gefiltert.
Antworten werden je Jahr in ``app_settings`` (Schlüssel ``holidays:<jahr>``) zwischengespeichert; ist die API nicht
erreichbar, wird der (auch abgelaufene) Cache verwendet.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

import audit
from auth import current_user, require_admin
from database import get_db

log = logging.getLogger("openplan.holidays")
router = APIRouter(prefix="/api")

DEFAULT_URL = "https://get.api-feiertage.de"      # in der Verwaltung änderbar (app_settings „holidays_api“)
CACHE_DAYS = 30
STATES = {
    "bw": "Baden-Württemberg", "by": "Bayern", "be": "Berlin", "bb": "Brandenburg", "hb": "Bremen", "hh": "Hamburg",
    "he": "Hessen", "mv": "Mecklenburg-Vorpommern", "ni": "Niedersachsen", "nw": "Nordrhein-Westfalen",
    "rp": "Rheinland-Pfalz", "sl": "Saarland", "sn": "Sachsen", "st": "Sachsen-Anhalt", "sh": "Schleswig-Holstein",
    "th": "Thüringen",
}


def build_url(base: str, year: int) -> str:
    """Basis-URL + Jahr: mit Platzhalter ``{year}`` oder als Parameter ``years=`` angehängt."""
    if "{year}" in base:
        return base.replace("{year}", str(year))
    return "%s%syears=%d" % (base, "&" if "?" in base else "?", year)


def get_url(db) -> str:
    row = db.execute("SELECT value FROM app_settings WHERE key='holidays_api'").fetchone()
    return (json.loads(row["value"]).get("url") if row else "") or DEFAULT_URL


def _fetch(year: int, base: str = DEFAULT_URL) -> List[Dict[str, Any]]:
    """Ein Jahr von der API holen (Proxy aus HTTPS_PROXY wird von urllib übernommen)."""
    req = urllib.request.Request(build_url(base, year), headers={"User-Agent": "openplan"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))
    if data.get("status") != "success":
        raise ValueError("API-Status: %s" % data.get("status"))
    out = []
    for e in data.get("feiertage") or []:
        states = [s for s in STATES if str(e.get(s)) == "1"]
        out.append({"date": e["date"], "name": e.get("fname") or "", "states": states})
    return out


def year_items(db, year: int) -> Optional[List[Dict[str, Any]]]:
    """Feiertage eines Jahres (Cache, sonst API); ``None`` wenn weder Cache noch API Daten haben."""
    key = "holidays:%d" % year
    row = db.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    cached = json.loads(row["value"]) if row else None
    if cached and (dt.date.today() - dt.date.fromisoformat(cached["fetched"])).days < CACHE_DAYS:
        return cached["items"]
    try:
        items = _fetch(year, get_url(db))
    except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
        log.warning("Feiertage %d nicht abrufbar: %s", year, e)
        return cached["items"] if cached else None
    if not items:                                   # Jahr nicht (mehr) von der API unterstützt
        return cached["items"] if cached else []
    db.execute("INSERT INTO app_settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               (key, json.dumps({"fetched": dt.date.today().isoformat(), "items": items})))
    return items


@router.get("/holidays/states")
def states(user=Depends(current_user)):
    return [{"code": c, "name": n} for c, n in sorted(STATES.items(), key=lambda x: x[1])]


@router.get("/holidays")
def holidays(state: str, years: str, user=Depends(current_user), db=Depends(get_db, scope="function")):
    """``state``: Länderkürzel (z. B. ``nw``), ``years``: kommagetrennt, höchstens 5 Jahre."""
    state = state.lower()
    if state not in STATES:
        raise HTTPException(422, "Unbekanntes Bundesland")
    try:
        ys = sorted({int(y) for y in years.split(",") if y.strip()})
    except ValueError:
        raise HTTPException(422, "Ungültige Jahresangabe")
    if not ys or len(ys) > 5 or ys[0] < 2000 or ys[-1] > 2100:
        raise HTTPException(422, "Bis zu 5 Jahre zwischen 2000 und 2100 angeben")
    out, missing = [], []
    for y in ys:
        items = year_items(db, y)
        if not items:
            missing.append(y)
            continue
        out += [{"date": e["date"], "name": e["name"]} for e in items if state in e["states"]]
    if not out and missing:
        raise HTTPException(502, "Feiertage konnten nicht von api-feiertage.de geladen werden (und es gibt keinen Cache)")
    return {"state": state, "holidays": sorted(out, key=lambda e: e["date"]), "missing_years": missing}


# ── Verwaltung: URL der Feiertags-API ─────────────────────────────────────
class HolidaysApiIn(BaseModel):
    url: str = Field("", max_length=500)             # leer = Standard


class HolidaysApiTest(BaseModel):
    url: Optional[str] = Field(None, max_length=500)  # ungespeicherter Wert aus dem Formular; None = gespeicherte URL


def _clean(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    p = urllib.parse.urlsplit(url)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise HTTPException(422, "Die URL muss mit http:// oder https:// beginnen und einen Host enthalten")
    return url


def _admin_state(db) -> Dict[str, Any]:
    cache = []
    for r in db.execute("SELECT key, value FROM app_settings WHERE key LIKE 'holidays:%' ORDER BY key"):
        v = json.loads(r["value"])
        cache.append({"year": int(r["key"].split(":")[1]), "fetched": v.get("fetched"), "count": len(v.get("items", []))})
    row = db.execute("SELECT value FROM app_settings WHERE key='holidays_api'").fetchone()
    return {"url": (json.loads(row["value"]).get("url") if row else "") or "", "default": DEFAULT_URL, "cache": cache}


def _clear_cache(db) -> None:
    db.execute("DELETE FROM app_settings WHERE key LIKE 'holidays:%'")


@router.get("/admin/settings/holidays")
def admin_get(admin=Depends(require_admin), db=Depends(get_db, scope="function")):
    return _admin_state(db)


@router.put("/admin/settings/holidays")
def admin_save(body: HolidaysApiIn, request: Request, admin=Depends(require_admin), db=Depends(get_db, scope="function")):
    url = _clean(body.url)
    changed = url != _admin_state(db)["url"]
    db.execute("INSERT INTO app_settings(key, value) VALUES ('holidays_api', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               (json.dumps({"url": url}),))
    if changed:
        _clear_cache(db)                              # Daten einer anderen Quelle nicht weiterverwenden
    audit.log(db, admin, "settings.holidays", "url=%s" % (url or "Standard"), audit.ip_of(request))
    return _admin_state(db)


@router.delete("/admin/settings/holidays/cache")
def admin_clear_cache(request: Request, admin=Depends(require_admin), db=Depends(get_db, scope="function")):
    _clear_cache(db)
    audit.log(db, admin, "settings.holidays.cache", "geleert", audit.ip_of(request))
    return _admin_state(db)


@router.post("/admin/settings/holidays/test")
def admin_test(body: HolidaysApiTest, admin=Depends(require_admin), db=Depends(get_db, scope="function")):
    """Ruft die API für das laufende Jahr ab (nichts wird gespeichert) und meldet das Ergebnis."""
    base = _clean(body.url) if body.url is not None else get_url(db)
    base = base or DEFAULT_URL
    year = dt.date.today().year
    called = build_url(base, year)
    try:
        items = _fetch(year, base)
    except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
        return {"ok": False, "called": called, "message": "%s: %s" % (type(e).__name__, e)}
    if not items:
        return {"ok": False, "called": called, "message": "Die API lieferte für %d keine Feiertage" % year}
    return {"ok": True, "called": called, "year": year, "count": len(items),
            "sample": [{"date": e["date"], "name": e["name"]} for e in items[:3]]}
