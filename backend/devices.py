"""Vorlagen für Arbeitsschritte + Geräteliste-Import (Excel/CSV).

* **Vorlagen** (``task_templates`` + ``task_template_steps``): globale Bibliothek je Gerätetyp (z. B. Switch): geordnete Schritte mit Rolle,
  Dauer, Wartezeit (Lieferzeit), Vorgänger und drei Schaltern: Preis → Plankosten, Wartungsfenster → Erledigungszeitraum, Lieferzeit-Override.
* **Import**: jede Zeile = ein Gerät → Struktur *Standort (Phase) → Gerät (Vorgang, Schlüssel = Hostname) → Schritte (Pakete)*, Schritte verkettet (EA +
  Wartezeit). Zuordnung der Schritte: Rolle → Ressource (Projekt-Rollenzuordnung) vor „Verantwortlich“ vor Pool (Selbstübernahme).
* Wiederholbar: vorhandene Hostnamen werden aktualisiert (Stammdaten/Fenster), Status und Schritte bleiben; Nachlieferungen kommen neu dazu.
* Trockenlauf = dieselbe Logik in einem SAVEPOINT, der zurückgerollt wird.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

import access
import budget
import history
import service as svc
import webhooks
from auth import current_user, require_editor
from config import IMPORT_HEADER_PREFIXES
from database import get_db
from finance_api import _decode, _norm_code, _parse_date

router = APIRouter(prefix="/api", dependencies=[Depends(history.record, scope="function")])   # Import ist mit „Rückgängig“ zurücknehmbar
MAX_ROWS = 1000
NOTE_MARK = "[Import]"

# ── Felder der Geräteliste (Schlüssel, Beschriftung, Pflicht, erkannte Spaltennamen) ───────────────────────────────
FIELDS: List[Tuple[str, str, bool, List[str]]] = [
    ("hostname", "Hostname", True, ["hostname", "nodename", "host", "gerätename", "geraetename", "name", "gerät", "geraet"]),
    ("standort", "Standort", False, ["standort", "ort", "werk", "city", "site", "location"]),
    ("loc", "Location-Code", False, ["location-code", "locationcode", "locationid", "standortcode", "standortkürzel", "standortkuerzel", "standort-id", "locid", "loc"]),
    ("typ", "Gerätetyp", True, ["gerätetyp", "geraetetyp", "typ", "kategorie", "gerätekategorie", "devicetype", "type"]),
    ("modell", "Neues Modell", False, ["neuesmodell", "neuesmodell(bestellartikel)", "modell", "bestellartikel", "artikel", "model"]),
    ("alt_host", "Altgerät Hostname", False, ["altgerätehostname", "altgeräthostname", "althostname", "altgeraethostname", "oldhostname", "olddevicehostname"]),
    ("alt_modell", "Altgerät Modell", False, ["altgerätmodell", "altgeraetmodell", "altmodell", "olddevicemodel", "oldmodel", "modelid"]),
    ("alt_seriennummer", "Altgerät Seriennummer", False, ["altgerätseriennummer", "altgeraetseriennummer", "seriennummer(alt)", "altseriennummer", "oldserial", "serialnumber"]),
    ("raum", "Gebäude / Raum", False, ["gebäude/raum", "gebaeude/raum", "raum", "gebäude", "gebaeude", "building/room", "room", "building"]),
    ("rack", "Rack / HE", False, ["rack/he", "rack", "he", "position", "rack/ru", "ru"]),
    ("ip", "Management-IP", False, ["management-ip", "managementip", "ip", "ip-adresse", "ipadresse", "ipaddress"]),
    ("profil", "Konfigurationsprofil", False, ["konfigurationsprofil", "profil", "konfig", "vlan", "configurationprofile", "profile", "config"]),
    ("seriennummer", "Seriennummer (neu)", False, ["seriennummer(neu)", "seriennummer", "sn", "serial"]),
    ("fenster_von", "Wartungsfenster von", False, ["wartungsfenstervon", "fenstervon", "von", "wartungvon", "maintenancewindowfrom", "windowfrom", "from"]),
    ("fenster_bis", "Wartungsfenster bis", False, ["wartungsfensterbis", "fensterbis", "bis", "wartungbis", "maintenancewindowto", "windowto", "to"]),
    ("prio", "Priorität", False, ["priorität", "prioritaet", "prio", "priority"]),
    ("lieferzeit", "Lieferzeit (Tage)", False, ["lieferzeit(tage)", "lieferzeit", "lieferzeittage", "leadtime(days)", "leadtime", "leadtimedays"]),
    ("preis", "Preis netto (EUR)", False, ["preisnetto(eur)", "preisnetto", "preis", "preiseur", "betrag", "price", "pricenet(eur)", "pricenet", "priceeur"]),
    ("kostenstelle", "Kostenstelle", False, ["kostenstelle", "kst", "costcenter"]),
    ("kostenart", "Kostenart", False, ["kostenart", "ka", "costtype"]),
    ("bestellref", "Bestellreferenz", False, ["bestellreferenz", "bestellnummer", "bestellung", "sapbestellung", "po", "orderreference", "ordernumber", "order"]),
    ("ansprech", "Ansprechpartner vor Ort", False, ["ansprechpartnervorort", "ansprechpartner", "kontakt", "contactonsite", "contact"]),
    ("verantwortlich", "Verantwortlich (Benutzer)", False, ["verantwortlich(benutzer)", "verantwortlich", "bearbeiter", "zuständig", "zustaendig", "responsible(user)", "responsible", "assignee"]),
    ("bemerkung", "Bemerkung", False, ["bemerkung", "notiz", "kommentar", "hinweis", "remark", "note", "comment"]),
]
FIELD_KEYS = [f[0] for f in FIELDS]
ATTR_LABEL = {k: lbl for k, lbl, _r, _a in FIELDS}


_INVISIBLE = re.compile("[\u200b\u200c\u200d\u2060\ufeff\u00ad]")


def clean_text(s: str) -> str:
    """Unsichtbare Zeichen (Zero-Width, Soft-Hyphen, BOM) entfernen, geschützte Leerzeichen normalisieren, trimmen."""
    return _INVISIBLE.sub("", s).replace("\u00a0", " ").replace("\u202f", " ").strip()


def _norm_header(h: Any) -> str:
    n = re.sub(r"[\s*:_]", "", clean_text(str(h or "")).lower())
    for pre in IMPORT_HEADER_PREFIXES:                             # optionale Präfixe ignorieren (Umgebungsvariable IMPORT_HEADER_PREFIXES)
        if pre and n.startswith(pre) and len(n) > len(pre):
            return n[len(pre):]
    return n


def suggest_mapping(headers: List[Any]) -> Dict[str, int]:
    """Spalten den Feldern zuordnen; bei mehreren Treffern gewinnt der Alias mit der höchsten Priorität (Reihenfolge in FIELDS)."""
    norm = [_norm_header(h) for h in headers]
    out: Dict[str, int] = {}
    for key, _lbl, _req, aliases in FIELDS:
        for a in aliases:
            na = _norm_header(a)
            idx = next((i for i, h in enumerate(norm) if h and h == na and i not in out.values()), None)
            if idx is not None:
                out[key] = idx
                break
    return out


# ── Datei lesen (xlsx / csv) ────────────────────────────────────────────────
def read_table(raw: bytes, filename: str, stats: Optional[Dict[str, int]] = None) -> Tuple[str, List[List[Any]]]:
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(413, "Datei zu groß (max. 10 MB)")
    name = (filename or "").lower()
    if name.endswith((".xlsx", ".xlsm")) or raw[:2] == b"PK":
        from openpyxl import load_workbook
        try:
            wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        except Exception:
            raise HTTPException(422, "Die Excel-Datei konnte nicht gelesen werden")
        sheet = next((s for s in wb.sheetnames if s.lower().replace("ä", "ae") in ("geräteliste", "geraeteliste")), wb.sheetnames[0])
        rows = []
        for r in wb[sheet].iter_rows(values_only=True):
            row = [_scrub(c.date() if isinstance(c, dt.datetime) else c, stats) for c in r]
            if any(c not in (None, "") for c in row):
                rows.append(row)
        return sheet, rows
    text = _decode(raw)
    head = text.splitlines()[0] if text.strip() else ""
    delim = max(";\t,", key=lambda d: head.count(d))
    return "CSV", [[_scrub(c, stats) for c in r] for r in csv.reader(io.StringIO(text), delimiter=delim) if any(x.strip() for x in r)]


def _scrub(v: Any, stats: Optional[Dict[str, int]]) -> Any:
    """Textzellen bereinigen (unsichtbare Zeichen); zählt die geänderten Zellen."""
    if not isinstance(v, str):
        return v
    c = clean_text(v)
    if stats is not None and c != v.strip(" \t\r\n"):
        stats["cleaned"] = stats.get("cleaned", 0) + 1
    return c


# ── Vorlagen ────────────────────────────────────────────────────────────────
SEED = {
    "Switch": [
        ("Bestellung auslösen", "Einkauf", 1, 10, None, 1, 0, 1),
        ("Lieferung / Wareneingang", "Einkauf", 1, 0, 1, 0, 0, 0),
        ("Kommissionieren und etikettieren", "Lager", 1, 0, 2, 0, 0, 0),
        ("Konfigurieren (Staging)", "Netzwerk-Team", 1, 0, 3, 0, 0, 0),
        ("Austausch vor Ort", "Vor-Ort-Team", 1, 0, 4, 0, 1, 0),
        ("Test und Abnahme", "Netzwerk-Team", 1, 0, 5, 0, 0, 0),
        ("Monitoring/CMDB eintragen, Altgerät zurücknehmen", "Netzwerk-Team", 1, 0, 6, 0, 0, 0),
    ],
    "Access Point": [
        ("Bestellung auslösen", "Einkauf", 1, 15, None, 1, 0, 1),
        ("Lieferung / Wareneingang", "Einkauf", 1, 0, 1, 0, 0, 0),
        ("Konfigurieren / Controller-Eintrag", "Netzwerk-Team", 1, 0, 2, 0, 0, 0),
        ("Montage vor Ort", "Vor-Ort-Team", 1, 0, 3, 0, 1, 0),
        ("Test und Abnahme (Ausleuchtung)", "Netzwerk-Team", 1, 0, 4, 0, 0, 0),
    ],
    "Firewall": [
        ("Bestellung auslösen", "Einkauf", 1, 20, None, 1, 0, 1),
        ("Lieferung / Wareneingang", "Einkauf", 1, 0, 1, 0, 0, 0),
        ("Konfiguration und Regelwerk vorbereiten", "Netzwerk-Team", 3, 0, 2, 0, 0, 0),
        ("Austausch vor Ort (Wartungsfenster)", "Vor-Ort-Team", 1, 0, 3, 0, 1, 0),
        ("Test und Abnahme", "Netzwerk-Team", 1, 0, 4, 0, 0, 0),
        ("Monitoring/CMDB eintragen, Altgerät zurücknehmen", "Netzwerk-Team", 1, 0, 5, 0, 0, 0),
    ],
}


def seed_defaults(conn) -> None:
    """Standardvorlagen (Netzwerk) anlegen, solange die Bibliothek leer ist."""
    if conn.execute("SELECT COUNT(*) FROM task_templates").fetchone()[0]:
        return
    for name, steps in SEED.items():
        tid = conn.execute("INSERT INTO task_templates(name, category, description, created_by) VALUES (?,?,?,?)",
                           (name, "Netzwerk", "Standardvorlage (Entwurf) – Schritte, Rollen und Dauer in der Vorlagen-Bibliothek anpassbar", "system")).lastrowid
        for pos, (n, role, dur, wait, pred, books, win, lead) in enumerate(steps, 1):
            conn.execute("INSERT INTO task_template_steps(template_id, position, name, role, duration, wait_days, pred_pos, books_price, uses_window, takes_lead) "
                         "VALUES (?,?,?,?,?,?,?,?,?,?)", (tid, pos, n, role, dur, wait, pred, books, win, lead))


SEED_EN = {
    "Switch (English)": [
        ("Place order", "Purchasing", 1, 10, None, 1, 0, 1),
        ("Delivery / goods receipt", "Purchasing", 1, 0, 1, 0, 0, 0),
        ("Pick and label", "Warehouse", 1, 0, 2, 0, 0, 0),
        ("Configure (staging)", "Network team", 1, 0, 3, 0, 0, 0),
        ("On-site replacement", "On-site team", 1, 0, 4, 0, 1, 0),
        ("Test and acceptance", "Network team", 1, 0, 5, 0, 0, 0),
        ("Add to monitoring/CMDB, take back old device", "Network team", 1, 0, 6, 0, 0, 0),
    ],
    "Access Point (English)": [
        ("Place order", "Purchasing", 1, 15, None, 1, 0, 1),
        ("Delivery / goods receipt", "Purchasing", 1, 0, 1, 0, 0, 0),
        ("Configure / controller entry", "Network team", 1, 0, 2, 0, 0, 0),
        ("On-site installation", "On-site team", 1, 0, 3, 0, 1, 0),
        ("Test and acceptance (coverage check)", "Network team", 1, 0, 4, 0, 0, 0),
    ],
    "Firewall (English)": [
        ("Place order", "Purchasing", 1, 20, None, 1, 0, 1),
        ("Delivery / goods receipt", "Purchasing", 1, 0, 1, 0, 0, 0),
        ("Prepare configuration and rule set", "Network team", 3, 0, 2, 0, 0, 0),
        ("On-site replacement (maintenance window)", "On-site team", 1, 0, 3, 0, 1, 0),
        ("Test and acceptance", "Network team", 1, 0, 4, 0, 0, 0),
        ("Add to monitoring/CMDB, take back old device", "Network team", 1, 0, 5, 0, 0, 0),
    ],
}


def seed_english(conn) -> None:
    """Englische Kopien der Standardvorlagen (eigene Namen, die deutschen bleiben unverändert) – einmalig je Datenbank."""
    if conn.execute("SELECT 1 FROM app_settings WHERE key='seed_templates_en'").fetchone():
        return
    for name, steps in SEED_EN.items():
        if conn.execute("SELECT 1 FROM task_templates WHERE lower(name)=lower(?)", (name,)).fetchone():
            continue
        tid = conn.execute("INSERT INTO task_templates(name, category, description, created_by) VALUES (?,?,?,?)",
                           (name, "Network (English)", "Default template (draft, English copy) – adjust steps, roles and duration in the template library", "system")).lastrowid
        for pos, (n, role, dur, wait, pred, books, win, lead) in enumerate(steps, 1):
            conn.execute("INSERT INTO task_template_steps(template_id, position, name, role, duration, wait_days, pred_pos, books_price, uses_window, takes_lead) "
                         "VALUES (?,?,?,?,?,?,?,?,?,?)", (tid, pos, n, role, dur, wait, pred, books, win, lead))
    conn.execute("INSERT INTO app_settings(key, value) VALUES ('seed_templates_en', '1')")


class StepIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    role: str = Field("", max_length=60)
    duration: int = Field(1, ge=0, le=5000)
    wait_days: int = Field(0, ge=0, le=365)
    pred_pos: Optional[int] = Field(None, ge=1)
    books_price: bool = False
    uses_window: bool = False
    takes_lead: bool = False


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)                  # = Wert der Spalte „Gerätetyp“
    category: str = Field("", max_length=60)
    description: str = Field("", max_length=500)
    steps: List[StepIn] = Field(min_length=1, max_length=60)


def _template_out(db, row) -> Dict[str, Any]:
    d = dict(row)
    d["steps"] = [dict(position=s["position"], name=s["name"], role=s["role"], duration=s["duration"], wait_days=s["wait_days"], pred_pos=s["pred_pos"],
                       books_price=bool(s["books_price"]), uses_window=bool(s["uses_window"]), takes_lead=bool(s["takes_lead"]))
                  for s in db.execute("SELECT * FROM task_template_steps WHERE template_id=? ORDER BY position", (row["id"],))]
    return d


def _validate_template(body: TemplateIn) -> None:
    for i, s in enumerate(body.steps, 1):
        if s.pred_pos is not None and not (1 <= s.pred_pos < i):
            raise HTTPException(422, "Schritt %d: Der Vorgänger muss ein früherer Schritt sein (Nr. 1–%d)" % (i, i - 1))
    if sum(1 for s in body.steps if s.books_price) > 1 or sum(1 for s in body.steps if s.uses_window) > 1 or sum(1 for s in body.steps if s.takes_lead) > 1:
        raise HTTPException(422, "„Preis“, „Wartungsfenster“ und „Lieferzeit“ dürfen je nur bei einem Schritt gesetzt sein")


def _save_steps(db, tid: int, body: TemplateIn) -> None:
    db.execute("DELETE FROM task_template_steps WHERE template_id=?", (tid,))
    for i, s in enumerate(body.steps, 1):
        db.execute("INSERT INTO task_template_steps(template_id, position, name, role, duration, wait_days, pred_pos, books_price, uses_window, takes_lead) "
                   "VALUES (?,?,?,?,?,?,?,?,?,?)", (tid, i, s.name.strip(), s.role.strip(), s.duration, s.wait_days, s.pred_pos, int(s.books_price), int(s.uses_window), int(s.takes_lead)))


@router.get("/templates")
def list_templates(user=Depends(current_user), db=Depends(get_db, scope="function")):
    return [_template_out(db, r) for r in db.execute("SELECT * FROM task_templates ORDER BY category, name")]


@router.get("/templates/sample.xlsx")
def sample_xlsx(user=Depends(current_user), db=Depends(get_db, scope="function")):
    """Muster-Geräteliste, live aus den aktuellen Vorlagen erzeugt."""
    import device_sample
    from fastapi.responses import Response
    tpls = [_template_out(db, r) for r in db.execute("SELECT * FROM task_templates ORDER BY category, name")]
    return Response(device_sample.build(tpls), headers={"Content-Disposition": 'attachment; filename="geraeteliste-vorlage.xlsx"', "Cache-Control": "no-store"},
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@router.post("/templates", status_code=201)
def create_template(body: TemplateIn, user=Depends(require_editor), db=Depends(get_db, scope="function")):
    _validate_template(body)
    if db.execute("SELECT 1 FROM task_templates WHERE lower(name)=lower(?)", (body.name.strip(),)).fetchone():
        raise HTTPException(409, "Es gibt bereits eine Vorlage „%s“" % body.name.strip())
    tid = db.execute("INSERT INTO task_templates(name, category, description, created_by) VALUES (?,?,?,?)",
                     (body.name.strip(), body.category.strip(), body.description.strip(), user["username"])).lastrowid
    _save_steps(db, tid, body)
    import audit
    audit.log(db, user, "template.create", body.name)
    return _template_out(db, db.execute("SELECT * FROM task_templates WHERE id=?", (tid,)).fetchone())


@router.put("/templates/{tid}")
def update_template(tid: int, body: TemplateIn, user=Depends(require_editor), db=Depends(get_db, scope="function")):
    _validate_template(body)
    if not db.execute("SELECT 1 FROM task_templates WHERE id=?", (tid,)).fetchone():
        raise HTTPException(404, "Vorlage nicht gefunden")
    if db.execute("SELECT 1 FROM task_templates WHERE lower(name)=lower(?) AND id<>?", (body.name.strip(), tid)).fetchone():
        raise HTTPException(409, "Es gibt bereits eine Vorlage „%s“" % body.name.strip())
    db.execute("UPDATE task_templates SET name=?, category=?, description=?, updated_at=datetime('now') WHERE id=?",
               (body.name.strip(), body.category.strip(), body.description.strip(), tid))
    _save_steps(db, tid, body)
    import audit
    audit.log(db, user, "template.update", body.name)
    return _template_out(db, db.execute("SELECT * FROM task_templates WHERE id=?", (tid,)).fetchone())


@router.delete("/templates/{tid}")
def delete_template(tid: int, user=Depends(require_editor), db=Depends(get_db, scope="function")):
    row = db.execute("SELECT name FROM task_templates WHERE id=?", (tid,)).fetchone()
    if not row:
        raise HTTPException(404, "Vorlage nicht gefunden")
    db.execute("DELETE FROM task_templates WHERE id=?", (tid,))
    import audit
    audit.log(db, user, "template.delete", row["name"])
    return {"ok": True}


# ── Rollenzuordnung je Projekt ───────────────────────────────────────────────
class RoleMapIn(BaseModel):
    role: str = Field(min_length=1, max_length=60)
    resource_id: Optional[int] = None                         # None/0 = keine feste Zuordnung (Pool)


@router.get("/projects/{pid}/role-map")
def get_role_map(pid: int, user=Depends(access.proj("view")), db=Depends(get_db, scope="function")):
    roles = sorted({r["role"] for r in db.execute("SELECT DISTINCT role FROM task_template_steps WHERE role<>''")})
    cur = {r["role"]: r["resource_id"] for r in db.execute("SELECT role, resource_id FROM project_role_map WHERE project_id=?", (pid,))}
    return {"roles": roles, "map": cur}


@router.put("/projects/{pid}/role-map")
def put_role_map(pid: int, items: List[RoleMapIn], user=Depends(access.proj("edit")), db=Depends(get_db, scope="function")):
    _save_role_map(db, pid, {i.role: i.resource_id for i in items})
    return get_role_map(pid, user, db)


def _save_role_map(db, pid: int, mp: Dict[str, Optional[int]]) -> None:
    for role, rid in mp.items():
        if rid:
            ok = db.execute("SELECT 1 FROM resources WHERE id=? AND project_id=?", (rid, pid)).fetchone()
            if not ok:
                raise HTTPException(422, "Ressource %s gehört nicht zum Projekt" % rid)
            db.execute("INSERT INTO project_role_map(project_id, role, resource_id) VALUES (?,?,?) ON CONFLICT(project_id, role) DO UPDATE SET resource_id=excluded.resource_id",
                       (pid, role, rid))
        else:
            db.execute("DELETE FROM project_role_map WHERE project_id=? AND role=?", (pid, role))


# ── Engine ──────────────────────────────────────────────────────────────────
def _txt(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()[:10]
    return str(v).strip()


_LOC_IN_TEXT = re.compile(r"(?<![A-Za-z])LOC[\s_-]?(\d+)", re.I)
_PRIO = {"businesscritical": "Business Critical", "nonbusinesscritical": "Non Business Critical", "lowpriority": "Low Priority",
         "geschäftskritisch": "Business Critical", "geschaeftskritisch": "Business Critical", "nichtgeschäftskritisch": "Non Business Critical",
         "nichtgeschaeftskritisch": "Non Business Critical", "niedrig": "Low Priority"}


def _loc(v: str) -> str:
    """Location-Code aus einer Spalte (``LOC024`` → ``LOC024``; ``LOC024__DE.Musterwerk`` → ``LOC024``); sonst der bereinigte Text."""
    v = clean_text(v)
    m = _LOC_IN_TEXT.search(v)
    return ("LOC" + m.group(1)) if m else v.upper().replace(" ", "")


def _loc_from_text(v: str) -> str:
    m = _LOC_IN_TEXT.search(clean_text(v))
    return ("LOC" + m.group(1)) if m else ""


def _prio(v: str) -> str:
    """Priorität vereinheitlichen (Groß-/Kleinschreibung, Trennzeichen); Unbekanntes bleibt unverändert."""
    return _PRIO.get(re.sub(r"[\s_-]", "", v.lower()), v)


def _date(v: Any) -> Optional[dt.date]:
    if v in (None, ""):
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    return _parse_date(str(v))


def _new_task(db, pid: int, parent: Optional[int], name: str, **c: Any) -> int:
    pos = db.execute("SELECT COALESCE(MAX(position)+1, 0) FROM tasks WHERE project_id=? AND parent_id IS ?", (pid, parent)).fetchone()[0]
    cols = {"duration": 1, "percent": 0, "constraint_type": "ASAP", "constraint_date": None, "notes": "", "pool": 0, "deadline": None,
            "ext_key": None, "attrs": None, "tpl_step": None, "tpl_id": None}
    cols.update(c)
    keys = list(cols)
    return db.execute("INSERT INTO tasks(project_id, parent_id, position, name, %s) VALUES (?,?,?,?,%s)" % (",".join(keys), ",".join("?" * len(keys))),
                      [pid, parent, pos, name] + [cols[k] for k in keys]).lastrowid


def _notes(attrs: Dict[str, str]) -> str:
    lines = [NOTE_MARK] + ["%s: %s" % (ATTR_LABEL[k], v) for k, v in attrs.items() if v and k not in ("hostname", "standort", "typ")]
    return "\n".join(lines)


def _people(db, pid: int) -> Dict[str, int]:
    rows = db.execute("SELECT u.id, u.username FROM users u WHERE u.id=(SELECT owner_id FROM projects WHERE id=?) "
                      "UNION SELECT u.id, u.username FROM project_members m JOIN users u ON u.id=m.user_id WHERE m.project_id=? AND m.role='editor'", (pid, pid))
    return {r["username"].lower(): r["id"] for r in rows}


def _resource_of_user(db, pid: int, uid: int, uname: str) -> int:
    r = db.execute("SELECT id FROM resources WHERE project_id=? AND user_id=? ORDER BY id LIMIT 1", (pid, uid)).fetchone()
    if r:
        return r["id"]
    return db.execute("INSERT INTO resources(project_id, name, user_id) VALUES (?,?,?)", (pid, uname, uid)).lastrowid


def build_devices(db, pid: int, user, rows: List[Dict[str, Any]], *, parent_id: Optional[int] = None, role_map: Optional[Dict[str, int]] = None,
                  create_missing: bool = False, cost_edit: bool = False) -> Dict[str, Any]:
    """Legt für jede Zeile Standort → Gerät → Schritte an (oder aktualisiert vorhandene Geräte). Rückgabe: Bericht mit Zeilenstatus/Fehlern."""
    role_map = role_map or {}
    templates = {r["name"].lower(): r for r in db.execute("SELECT * FROM task_templates")}
    steps_of = {tid: [dict(s) for s in db.execute("SELECT * FROM task_template_steps WHERE template_id=? ORDER BY position", (tid,))] for tid in {t["id"] for t in templates.values()}}
    people = _people(db, pid)
    ccs = {r["code"]: r["id"] for r in db.execute("SELECT id, code FROM cost_centers WHERE project_id=?", (pid,))}
    cts = {r["code"]: r["id"] for r in db.execute("SELECT id, code FROM cost_types WHERE project_id=?", (pid,))}
    ccn = {_norm_code(k): v for k, v in ccs.items()}
    ctn = {_norm_code(k): v for k, v in cts.items()}
    sites: Dict[str, int] = {}
    seen: Dict[str, int] = {}
    res = {"rows": len(rows), "new": 0, "updated": 0, "steps": 0, "sites_new": 0, "errors": [], "items": [], "warnings": [], "new_cost_centers": [], "new_cost_types": []}
    price_skipped = False
    dup: Dict[str, Dict[str, int]] = {"IP-Adresse": {}, "Seriennummer": {}}
    dup_warned: set = set()
    for r in rows:
        n = r.get("_row", 0)
        host, site, typ = clean_text(_txt(r.get("hostname"))), clean_text(_txt(r.get("standort"))), clean_text(_txt(r.get("typ")))
        loc = _loc(_txt(r.get("loc"))) if _txt(r.get("loc")) else _loc_from_text(site)          # Location-Code (z. B. LOC024) – auch aus „LOC024__DE.Musterwerk“
        try:
            if not host or not (site or loc) or not typ:
                raise ValueError("Hostname, Standort (oder Location-Code) und Gerätetyp sind Pflicht")
            site = site or loc
            if " " in host:
                raise ValueError("Hostname enthält Leerzeichen")
            key = host.lower()
            if key in seen:
                raise ValueError("Hostname %s kommt in Zeile %d bereits vor" % (host, seen[key]))
            tpl = templates.get(typ.lower())
            if not tpl:
                raise ValueError("Keine Vorlage für Gerätetyp „%s“ (Vorhanden: %s)" % (typ, ", ".join(sorted(t["name"] for t in templates.values())) or "–"))
            von, bis = _date(r.get("fenster_von")), _date(r.get("fenster_bis"))
            if von and bis and von > bis:
                raise ValueError("Wartungsfenster: „von“ liegt nach „bis“")
            lead = None
            if _txt(r.get("lieferzeit")):
                lead = int(float(_txt(r.get("lieferzeit")).replace(",", ".")))
                if lead < 0 or lead > 365:
                    raise ValueError("Lieferzeit außerhalb 0–365 Tage")
            price = None
            if _txt(r.get("preis")):
                price = float(r["preis"]) if isinstance(r["preis"], (int, float)) else budget.parse_amount(_txt(r["preis"]))
            cc_code, ct_code = _txt(r.get("kostenstelle")), _txt(r.get("kostenart"))
            cc_id = ct_id = None
            if price and cost_edit:
                if cc_code:
                    cc_id = ccs.get(cc_code) or ccn.get(_norm_code(cc_code))
                    if cc_id is None:
                        if not create_missing:
                            raise ValueError("Kostenstelle %s unbekannt" % cc_code)
                        cc_id = ccs[cc_code] = ccn[_norm_code(cc_code)] = db.execute("INSERT INTO cost_centers(project_id, code, name) VALUES (?,?,'')", (pid, cc_code)).lastrowid
                        res["new_cost_centers"].append(cc_code)
                if ct_code:
                    ct_id = cts.get(ct_code) or ctn.get(_norm_code(ct_code))
                    if ct_id is None:
                        if not create_missing:
                            raise ValueError("Kostenart %s unbekannt" % ct_code)
                        ct_id = cts[ct_code] = ctn[_norm_code(ct_code)] = db.execute("INSERT INTO cost_types(project_id, code, name) VALUES (?,?,'')", (pid, ct_code)).lastrowid
                        res["new_cost_types"].append(ct_code)
            elif price and not cost_edit:
                price_skipped = True
            who = _txt(r.get("verantwortlich"))
            who_rid = None
            if who:
                uid = people.get(who.lower())
                if not uid:
                    raise ValueError("Verantwortlich „%s“ ist weder Verantwortlicher noch Bearbeiter dieses Projekts" % who)
                who_rid = _resource_of_user(db, pid, uid, who)
            seen[key] = n
            attrs = {k: clean_text(_txt(r.get(k))) for k in FIELD_KEYS if _txt(r.get(k))}
            if attrs.get("prio"):
                attrs["prio"] = _prio(attrs["prio"])
            if loc:
                attrs["loc"] = loc
            for fld, what in (("ip", "IP-Adresse"), ("seriennummer", "Seriennummer"), ("alt_seriennummer", "Seriennummer")):   # Dubletten sind meist Erfassungsfehler -> nur warnen
                v = attrs.get(fld, "").lower()
                if v:
                    if v in dup[what] and dup[what][v] != n and (what, v) not in dup_warned:
                        res["warnings"].append("%s %s kommt in Zeile %d und %d vor" % (what, attrs[fld], dup[what][v], n))
                        dup_warned.add((what, v))
                    dup[what].setdefault(v, n)
            if von:
                attrs["fenster_von"] = von.isoformat()
            if bis:
                attrs["fenster_bis"] = bis.isoformat()
            attrs["hostname"], attrs["standort"], attrs["typ"] = host, site, tpl["name"]
            existing = db.execute("SELECT id, notes FROM tasks WHERE project_id=? AND ext_key=?", (pid, key)).fetchone()
            steps = steps_of[tpl["id"]]
            if existing:                                                         # Nachimport: Stammdaten + Fenster aktualisieren, Status bleibt
                db.execute("UPDATE tasks SET attrs=?, notes=? WHERE id=?", (json.dumps(attrs, ensure_ascii=False),
                           _notes(attrs) if (existing["notes"] or "").startswith(NOTE_MARK) or not existing["notes"] else existing["notes"], existing["id"]))
                win = next((s for s in steps if s["uses_window"]), None)
                if win and (von or bis):
                    st = db.execute("SELECT id FROM tasks WHERE parent_id=? AND tpl_step=?", (existing["id"], win["position"])).fetchone()
                    if st:
                        db.execute("UPDATE tasks SET constraint_type=?, constraint_date=?, deadline=? WHERE id=?",
                                   ("SNET" if von else "ASAP", von.isoformat() if von else None, bis.isoformat() if bis else None, st["id"]))
                res["updated"] += 1
                res["items"].append({"row": n, "hostname": host, "standort": site, "loc": loc, "typ": tpl["name"], "action": "aktualisiert", "steps": 0})
                continue
            label = site if (not loc or site.upper().startswith(loc)) else "%s – %s" % (loc, site)       # Phase: „LOC024 – Musterwerk“
            skey = (loc or site).lower()                                                                  # gleicher Code = gleicher Standort, egal wie der Text geschrieben ist
            if skey not in sites:
                # vorhandene Phase wiederverwenden: gleicher Name, gleicher Code ("LOC024 – …") oder – ohne Code in dieser Zeile – derselbe Ortsname hinter einem Code
                sid = db.execute("SELECT id, name FROM tasks WHERE project_id=? AND parent_id IS ? AND (lower(name)=lower(?) OR lower(name)=lower(?) "
                                 "OR (?<>'' AND lower(name) LIKE lower(?)) OR (?='' AND lower(name) LIKE lower(?))) ORDER BY id LIMIT 1",
                                 (pid, parent_id, label, site, loc, loc + " %", loc, "% – " + site)).fetchone()
                if sid:
                    sites[skey] = sid["id"]
                    if loc and sid["name"] != label and sid["name"].lower() == site.lower():           # früher ohne Code angelegt -> Code ergänzen
                        db.execute("UPDATE tasks SET name=? WHERE id=?", (label, sid["id"]))
                else:
                    sites[skey] = _new_task(db, pid, parent_id, label)
                    res["sites_new"] += 1
            dev = _new_task(db, pid, sites[skey], host, ext_key=key, attrs=json.dumps(attrs, ensure_ascii=False), notes=_notes(attrs), tpl_id=tpl["id"])
            ids: Dict[int, int] = {}
            for s in steps:
                rid = (role_map.get(s["role"]) or None) or who_rid
                c: Dict[str, Any] = {"duration": s["duration"], "tpl_step": s["position"], "tpl_id": tpl["id"], "pool": 0 if rid else 1}
                if s["uses_window"] and (von or bis):
                    if von:
                        c.update(constraint_type="SNET", constraint_date=von.isoformat())
                    if bis:
                        c["deadline"] = bis.isoformat()
                tid = ids[s["position"]] = _new_task(db, pid, dev, s["name"], **c)
                if rid:
                    db.execute("INSERT OR REPLACE INTO assignments(task_id, resource_id, units) VALUES (?,?,100)", (tid, rid))
                if s["pred_pos"] and s["pred_pos"] in ids:
                    pred = next(x for x in steps if x["position"] == s["pred_pos"])
                    lag = lead if (pred["takes_lead"] and lead is not None) else pred["wait_days"]
                    db.execute("INSERT INTO deps(project_id, pred_id, succ_id, type, lag) VALUES (?,?,?, 'FS', ?)", (pid, ids[s["pred_pos"]], tid, lag))
                if s["books_price"] and price and cost_edit:
                    db.execute("INSERT INTO cost_items(project_id, task_id, cost_type_id, cost_center_id, amount, description) VALUES (?,?,?,?,?,?)",
                               (pid, tid, ct_id, cc_id, price, ("Beschaffung %s" % _txt(r.get("modell")) if _txt(r.get("modell")) else "Beschaffung")[:300]))
            res["new"] += 1
            res["steps"] += len(steps)
            webhooks.emit(db, pid, "device.created", dev, user, extra={"steps": len(steps)})
            res["items"].append({"row": n, "hostname": host, "standort": site, "typ": tpl["name"], "action": "neu", "steps": len(steps)})
        except (ValueError, KeyError, TypeError) as e:
            res["errors"].append({"row": n, "hostname": host, "message": str(e) or "Zeile nicht lesbar"})
    if price_skipped:
        res["warnings"].append("Preise wurden ignoriert: Kosten dürfen nur Verantwortliche/Admins anlegen")
    res["error_count"] = len(res["errors"])
    return res


def _rows_from_table(table: List[List[Any]], mapping: Dict[str, int]) -> List[Dict[str, Any]]:
    out = []
    for n, row in enumerate(table[1:], start=2):
        d: Dict[str, Any] = {"_row": n}
        for k, idx in mapping.items():
            if k in FIELD_KEYS and isinstance(idx, int) and 0 <= idx < len(row):
                d[k] = row[idx]
        if any(_txt(d.get(k)) for k in FIELD_KEYS):
            out.append(d)
    return out


def _guard(db, pid: int, user, dry_run: bool, fn):
    """Trockenlauf = echte Logik in einem SAVEPOINT, der zurückgerollt wird."""
    db.execute("SAVEPOINT devimport")
    try:
        rep = fn()
        if dry_run or (rep["errors"]):
            db.execute("ROLLBACK TO devimport")
        db.execute("RELEASE devimport")
        return rep
    except Exception:
        db.execute("ROLLBACK TO devimport")
        db.execute("RELEASE devimport")
        raise


@router.post("/projects/{pid}/devices/parse")
async def parse_devices(pid: int, file: UploadFile = File(...), user=Depends(access.proj("edit")), db=Depends(get_db, scope="function")):
    stats: Dict[str, int] = {}
    sheet, table = read_table(await file.read(), file.filename or "", stats)
    if len(table) < 2:
        raise HTTPException(422, "Die Datei enthält keine Datenzeilen")
    return {"sheet": sheet, "cleaned": stats.get("cleaned", 0), "columns": [{"index": i, "name": _txt(h)} for i, h in enumerate(table[0])], "rows_total": len(table) - 1,
            "sample": [[_txt(c) for c in r] for r in table[1:6]], "mapping": suggest_mapping(table[0]),
            "fields": [{"key": k, "label": lbl, "required": req} for k, lbl, req, _a in FIELDS],
            "templates": [r["name"] for r in db.execute("SELECT name FROM task_templates ORDER BY name")]}


@router.post("/projects/{pid}/devices/import")
async def import_devices(pid: int, file: UploadFile = File(...), mapping: str = Form(...), dry_run: bool = Form(True), partial: bool = Form(False),
                         create_missing: bool = Form(False), parent_id: Optional[int] = Form(None), role_map: str = Form("{}"),
                         user=Depends(access.proj("edit")), db=Depends(get_db, scope="function")):
    try:
        mp = {k: int(v) for k, v in json.loads(mapping).items() if v is not None and v != ""}
        rm = {k: int(v) for k, v in json.loads(role_map or "{}").items() if v}
    except (ValueError, TypeError):
        raise HTTPException(422, "Zuordnung ungültig")
    for need in ("hostname", "typ"):
        if need not in mp:
            raise HTTPException(422, "Spalte fehlt: %s" % ATTR_LABEL[need])
    if "standort" not in mp and "loc" not in mp:
        raise HTTPException(422, "Spalte fehlt: Standort oder Location-Code")
    if parent_id and not db.execute("SELECT 1 FROM tasks WHERE id=? AND project_id=?", (parent_id, pid)).fetchone():
        raise HTTPException(422, "Zielvorgang gehört nicht zum Projekt")
    stats = {}
    sheet, table = read_table(await file.read(), file.filename or "", stats)
    rows = _rows_from_table(table, mp)
    if len(rows) > MAX_ROWS:
        raise HTTPException(422, "Zu viele Zeilen (max. %d Geräte je Import)" % MAX_ROWS)
    if not rows:
        raise HTTPException(422, "Keine Datenzeilen gefunden")
    cost_edit = access.cost_level(db, user, pid) == "edit"
    rep = _guard(db, pid, user, dry_run, lambda: build_devices(db, pid, user, rows, parent_id=parent_id, role_map=rm, create_missing=create_missing, cost_edit=cost_edit))
    if rep["errors"] and partial and not dry_run:                      # nur gültige Zeilen übernehmen
        bad = {e["row"] for e in rep["errors"]}
        good = [r for r in rows if r["_row"] not in bad]
        rep = _guard(db, pid, user, False, lambda: build_devices(db, pid, user, good, parent_id=parent_id, role_map=rm, create_missing=create_missing, cost_edit=cost_edit))
        rep["errors"] = [{"row": r, "hostname": "", "message": "übersprungen (Fehler in der Zeile)"} for r in sorted(bad)]
        rep["error_count"] = len(rep["errors"])
    if stats.get("cleaned"):
        rep["warnings"].append("%d Zellen enthielten unsichtbare Zeichen oder geschützte Leerzeichen und wurden bereinigt" % stats["cleaned"])
    rep.update(dry_run=dry_run, imported=0, sheet=sheet, items=rep["items"][:15] if dry_run else rep["items"][:15])
    if not dry_run and (not rep["errors"] or partial) and (rep["new"] or rep["updated"]):
        _save_role_map(db, pid, rm)
        svc.bump(db, pid)
        svc.log(db, pid, user, "Geräteliste importiert", "%s: %d neu, %d aktualisiert, %d Schritte" % (file.filename, rep["new"], rep["updated"], rep["steps"]))
        rep["imported"] = rep["new"] + rep["updated"]
    return rep


class DeviceIn(BaseModel):
    template_id: int
    hostname: str = Field(min_length=1, max_length=120)
    standort: str = Field("", max_length=120)
    parent_id: Optional[int] = None
    modell: str = ""
    fenster_von: Optional[dt.date] = None
    fenster_bis: Optional[dt.date] = None
    lieferzeit: Optional[int] = Field(None, ge=0, le=365)
    verantwortlich: str = ""


@router.post("/projects/{pid}/devices")
def add_device(pid: int, body: DeviceIn, user=Depends(access.proj("edit")), db=Depends(get_db, scope="function")):
    """Einzelnes Gerät aus einer Vorlage anlegen (ohne Excel)."""
    tpl = db.execute("SELECT name FROM task_templates WHERE id=?", (body.template_id,)).fetchone()
    if not tpl:
        raise HTTPException(404, "Vorlage nicht gefunden")
    if body.parent_id and not db.execute("SELECT 1 FROM tasks WHERE id=? AND project_id=?", (body.parent_id, pid)).fetchone():
        raise HTTPException(422, "Zielvorgang gehört nicht zum Projekt")
    row = {"_row": 1, "hostname": body.hostname.strip(), "standort": body.standort.strip() or "Ohne Standort", "typ": tpl["name"], "modell": body.modell,
           "fenster_von": body.fenster_von, "fenster_bis": body.fenster_bis, "lieferzeit": body.lieferzeit, "verantwortlich": body.verantwortlich}
    rm = {r["role"]: r["resource_id"] for r in db.execute("SELECT role, resource_id FROM project_role_map WHERE project_id=?", (pid,))}
    rep = _guard(db, pid, user, False, lambda: build_devices(db, pid, user, [row], parent_id=body.parent_id, role_map=rm))
    if rep["errors"]:
        raise HTTPException(422, rep["errors"][0]["message"])
    svc.bump(db, pid)
    svc.log(db, pid, user, "Gerät aus Vorlage angelegt", "%s (%s)" % (body.hostname, tpl["name"]))
    return svc.load_project(db, pid, user)
