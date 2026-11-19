"""Eingang für Job-Ergebnisse von AutoPatch: ordnet Server den Geräten eines Projekts zu und setzt den passenden Schritt.

Zuordnung (``match``): 1. gleicher Hostname, 2. gleicher Kurzname (``web01`` ↔ ``web01.corp.example``), 3. nur per DNS – ein Gerät, dessen
Hostname zur gemeldeten IP auflöst. Bei 1./2. wird zusätzlich per DNS geprüft (``dns``): löst der Gerätename zu einer anderen IP auf als der
gemeldete Server, wird **nichts** gesetzt (``dns_conflict``) – derselbe Name für zwei verschiedene Maschinen soll keinen falschen Status erzeugen.
Nicht auflösbare Namen werden mit Warnung (``dns: unresolved``) übernommen. ``dns: "off"`` schaltet die Prüfung ab.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from typing import Any, Dict, List, Literal, Optional, Set

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import access
import service as svc
import webhooks
from auth import current_user
from database import get_db

router = APIRouter(prefix="/api/integrations")

MAX_DNS_LOOKUPS = 300                        # je Anfrage, Obergrenze für die reine DNS-Zuordnung
# Standard-Schrittnamen je Job-Art (Teilstring-Regex, ohne Beachtung der Groß-/Kleinschreibung)
STEP_DEFAULT = {"patch": r"patch|update|aktualisier", "cve_check": r"cve|schwachstell|vulnerab"}


def resolve(name: str) -> Set[str]:
    """IP-Adressen eines Namens (leer, wenn nicht auflösbar). Wird in Tests ersetzt."""
    try:
        ipaddress.ip_address(name)
        return {name}
    except ValueError:
        pass
    try:
        return {i[4][0].split("%")[0] for i in socket.getaddrinfo(name, None, proto=socket.IPPROTO_TCP)}
    except (socket.gaierror, UnicodeError):
        return set()


def _norm(h: str) -> str:
    return h.strip().lower().rstrip(".")


def _short(h: str) -> str:
    try:
        ipaddress.ip_address(h)
        return h
    except ValueError:
        return h.split(".")[0]


class ApHost(BaseModel):
    hostname: str = Field(min_length=1, max_length=255)
    ip: Optional[str] = Field(None, max_length=64)
    status: Literal["success", "failed", "skipped", "running", "pending"]
    packages_updated: int = 0
    reboot_required: bool = False
    error: str = Field("", max_length=2000)


class ApJob(BaseModel):
    id: int
    name: str = Field("", max_length=200)
    type: Literal["patch", "cve_check"] = "patch"
    url: str = Field("", max_length=500)


class ApResults(BaseModel):
    job: ApJob
    results: List[ApHost] = Field(max_length=500)
    project_id: Optional[int] = None                  # leer = alle Projekte, in denen das Konto Bearbeiter ist
    step: Optional[str] = Field(None, max_length=80)  # Teilstring/Regex des Schrittnamens; sonst Standard je Job-Art
    dns: Literal["verify", "off"] = "verify"


def _devices(db, user, project_id: Optional[int]) -> List[Dict[str, Any]]:
    pids = [project_id] if project_id is not None else [r["id"] for r in db.execute("SELECT id FROM projects")]
    out = []
    for pid in pids:
        if access.level_of(db, user, pid) < 3:                    # setzen darf nur Bearbeiter/Verantwortliche
            if project_id is not None:
                raise HTTPException(403 if access.level_of(db, user, pid) else 404, "Kein Bearbeiterzugriff auf das Projekt")
            continue
        for r in db.execute("SELECT id, name, project_id FROM tasks WHERE project_id=? AND ext_key IS NOT NULL", (pid,)):
            out.append({"id": r["id"], "host": _norm(r["name"]), "project_id": pid})
    return out


def _step_of(db, dev_id: int, pattern: str) -> Dict[str, Any]:
    rx = re.compile(pattern, re.I)
    kids = [r for r in db.execute("SELECT * FROM tasks WHERE parent_id=? ORDER BY position, id", (dev_id,)) if rx.search(r["name"])]
    if not kids:
        return {"error": "no_step"}
    if len(kids) > 1:
        return {"error": "ambiguous_step", "names": [k["name"] for k in kids]}
    return {"task": kids[0]}


@router.post("/autopatch/results")
def autopatch_results(body: ApResults, user=Depends(current_user), db=Depends(get_db, scope="function")):
    """Nimmt das Ergebnis eines AutoPatch-Jobs entgegen und setzt je Server den passenden Schritt (Status, Notiz, Referenz ``autopatch``).

    Antwort: ``{"applied": n, "items": [{hostname, outcome, ...}]}``; mögliche ``outcome``-Werte: applied, unchanged, already_done, skipped,
    no_device, ambiguous_device, dns_conflict, no_step, ambiguous_step."""
    try:
        pattern = body.step or STEP_DEFAULT[body.job.type]
        re.compile(pattern)
    except re.error:
        raise HTTPException(422, "step ist kein gültiger regulärer Ausdruck")
    devs = _devices(db, user, body.project_id)
    cache: Dict[str, Set[str]] = {}
    lookups = [0]

    def res(name: str) -> Set[str]:
        if name not in cache:
            lookups[0] += 1
            cache[name] = resolve(name)
        return cache[name]

    verify = body.dns == "verify"
    ref = "job-%d" % body.job.id
    items, applied = [], 0
    for h in body.results:
        want_name = _norm(h.hostname)
        item: Dict[str, Any] = {"hostname": h.hostname, "outcome": "", "task_id": None, "project_id": None, "device": None, "match": None, "dns": None, "step": None}
        items.append(item)
        by_name = [d for d in devs if d["host"] == want_name]
        match = "name"
        if not by_name:
            by_name, match = [d for d in devs if _short(d["host"]) == _short(want_name)], "short"
        if not by_name and verify and h.ip:                       # nur per DNS: Gerät, dessen Name zur gemeldeten IP auflöst
            cand = [d for d in devs if lookups[0] < MAX_DNS_LOOKUPS and h.ip in res(d["host"])]
            by_name, match = cand, "dns"
        if not by_name:
            item["outcome"] = "no_device"
            continue
        if len(by_name) > 1:
            item.update(outcome="ambiguous_device", match=match, message="%d Geräte passen: %s" % (len(by_name), ", ".join(d["host"] for d in by_name[:5])))
            continue
        dev = by_name[0]
        item.update(match=match, device=dev["host"], project_id=dev["project_id"])
        if verify:
            want = {h.ip} if h.ip else res(want_name)
            have = res(dev["host"])
            item["dns"] = "unresolved" if not want or not have else ("ok" if want & have else "mismatch")
            if item["dns"] == "mismatch":
                item.update(outcome="dns_conflict", message="%s löst zu %s auf, der Server meldet %s" % (dev["host"], ", ".join(sorted(have)), ", ".join(sorted(want))))
                continue
        st = _step_of(db, dev["id"], pattern)
        if "error" in st:
            item.update(outcome=st["error"], message=", ".join(st.get("names", [])))
            continue
        t = st["task"]
        item["task_id"], item["step"] = t["id"], t["name"]
        if h.status in ("skipped",):
            item["outcome"] = "skipped"
            continue
        if t["status"] == "done":                                 # abgeschlossene Schritte nicht wieder öffnen (z. B. monatliche Folgeläufe)
            item["outcome"] = "already_done"
            continue
        if h.status == "success":
            new, note = "done", ("Neustart nötig" if h.reboot_required else "")
        elif h.status == "failed":
            new, note = "blocked", ("AutoPatch-Job #%d fehlgeschlagen" % body.job.id + (": " + h.error.strip().splitlines()[-1] if h.error.strip() else ""))[:300]
        else:                                                     # running/pending
            new, note = ("in_progress" if t["status"] == "open" else t["status"]), None
        changed, _ = webhooks.apply_task_event(db, user, t, status=new, note=note, system="autopatch", ref=ref, url=body.job.url,
                                                journal="Rückmeldung (AutoPatch)")
        item["outcome"] = "applied" if changed else "unchanged"
        applied += 1 if changed else 0
    return {"applied": applied, "items": items}
