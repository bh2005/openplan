"""Budget, Plan-/Ist-Kosten, Kostenstellen/-arten (alles in EUR)."""
from __future__ import annotations

import csv
import io
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

import access
import budget
import cpm
import service as svc
from auth import current_user
from database import get_db
from schemas import (ActualIn, BudgetLineIn, CostItemIn, CostSettingsIn, MasterImportIn, MasterIn)

router = APIRouter(prefix="/api")
MASTER = {"cost-centers": "cost_centers", "cost-types": "cost_types"}
LABEL = {"cost_centers": "Kostenstelle", "cost_types": "Kostenart"}
CURRENCY = "EUR"


# ── Hilfen ──────────────────────────────────────────────────────────────────
def _need_edit(db, user, pid: Optional[int]) -> int:
    if pid is None:
        raise HTTPException(404, "Eintrag nicht gefunden")
    access.check(db, user, pid, "view")
    if access.cost_level(db, user, pid) != "edit":
        raise HTTPException(403, "Keine Berechtigung für Kosten/Budget")
    return pid


def _pid_of(db, table: str, rid: int) -> Optional[int]:
    row = db.execute("SELECT project_id FROM %s WHERE id=?" % table, (rid,)).fetchone()
    return row["project_id"] if row else None


def _ref_ok(db, table: str, pid: int, rid: Optional[int], what: str) -> None:
    if rid is None:
        return
    r = db.execute("SELECT project_id FROM %s WHERE id=?" % table, (rid,)).fetchone()
    if not r or r["project_id"] != pid:
        raise HTTPException(422, "%s gehört nicht zum Projekt" % what)


def finance_state(db, pid: int, user) -> Dict[str, Any]:
    q = lambda sql: [dict(r) for r in db.execute(sql, (pid,))]  # noqa: E731
    return {
        "currency": CURRENCY,
        "access": access.cost_level(db, user, pid),
        "members_see_costs": bool(svc.get_project_row(db, pid)["members_see_costs"]),
        "cost_centers": q("SELECT id, code, name FROM cost_centers WHERE project_id=? ORDER BY code"),
        "cost_types": q("SELECT id, code, name FROM cost_types WHERE project_id=? ORDER BY code"),
        "budget_lines": q("SELECT id, cost_center_id, cost_type_id, amount FROM budget_lines WHERE project_id=?"),
        "cost_items": q("SELECT id, task_id, cost_type_id, cost_center_id, amount, description FROM cost_items "
                        "WHERE project_id=? ORDER BY id"),
    }


def raw_resources(db, pid: int) -> Dict[int, Dict[str, Any]]:
    return {r["id"]: dict(r) for r in db.execute("SELECT * FROM resources WHERE project_id=?", (pid,))}


def plan_by_task(db, pid: int, data: Dict[str, Any]) -> Dict[int, float]:
    items = [dict(r) for r in db.execute("SELECT * FROM cost_items WHERE project_id=?", (pid,))]
    lines = budget.plan_lines(data["tasks"], data["assignments"], raw_resources(db, pid), items,
                              budget.Fx(CURRENCY, {}))
    out: Dict[int, float] = {}
    for ln in lines:
        out[ln["task_id"]] = out.get(ln["task_id"], 0.0) + ln["amount"]
    return out


# ── Übersicht ───────────────────────────────────────────────────────────────
@router.get("/projects/{pid}/finance")
def get_finance(pid: int, user=Depends(access.costs("view")), db=Depends(get_db, scope="function")):
    return finance_state(db, pid, user)


@router.put("/projects/{pid}/finance/settings")
def put_settings(pid: int, body: CostSettingsIn, user=Depends(access.costs("edit")), db=Depends(get_db, scope="function")):
    db.execute("UPDATE projects SET members_see_costs=? WHERE id=?", (1 if body.members_see_costs else 0, pid))
    svc.bump(db, pid)
    svc.log(db, pid, user, "Kosten-Sichtbarkeit geändert", "Mitglieder sehen Kosten: %s" % body.members_see_costs)
    return finance_state(db, pid, user)


@router.get("/projects/{pid}/budget")
def get_budget(pid: int, status: Optional[date] = None, user=Depends(access.costs("view")), db=Depends(get_db, scope="function")):
    data = svc.load_project(db, pid, user)
    proj = svc.get_project_row(db, pid)
    cal = cpm.Calendar(date.fromisoformat(proj["start_date"]), svc.parse_days(proj["work_days"]),
                       svc.parse_holidays(proj["holidays"]))
    items = [dict(r) for r in db.execute("SELECT * FROM cost_items WHERE project_id=?", (pid,))]
    lines = budget.plan_lines(data["tasks"], data["assignments"], raw_resources(db, pid), items,
                              budget.Fx(CURRENCY, {}))
    tasks = data["tasks"]
    bc = {r["id"]: r["baseline_cost"] for r in db.execute("SELECT id, baseline_cost FROM tasks WHERE project_id=?", (pid,))}
    for t in tasks:  # baseline_cost kommt nur aus der DB (nicht Teil der Projekt-API)
        t["baseline_cost"] = bc.get(t["id"])
    acts = [dict(r, amount_base=r["amount"]) for r in db.execute("SELECT * FROM actuals WHERE project_id=?", (pid,))]
    fin = finance_state(db, pid, user)
    res = budget.compute(tasks, lines, acts, fin["budget_lines"], fin["cost_centers"], fin["cost_types"],
                         cal.is_working, status or date.today())
    res["currency"] = CURRENCY
    res["has_baseline"] = any(t.get("baseline_cost") is not None for t in tasks)
    return res


@router.get("/projects/{pid}/budget/export")
def export_budget(pid: int, what: str = "matrix", user=Depends(access.costs("view")), db=Depends(get_db, scope="function")):
    fin = finance_state(db, pid, user)
    cc = {c["id"]: c for c in fin["cost_centers"]}
    ct = {c["id"]: c for c in fin["cost_types"]}
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    if what == "actuals":
        w.writerow(["Buchungsdatum", "Kostenstelle", "Kostenart", "Betrag", "Währung", "Belegnummer", "Text", "Vorgang-ID", "Quelle"])
        for r in db.execute("SELECT * FROM actuals WHERE project_id=? ORDER BY booking_date, id", (pid,)):
            w.writerow([r["booking_date"], cc.get(r["cost_center_id"], {}).get("code", ""),
                        ct.get(r["cost_type_id"], {}).get("code", ""), _de(r["amount"]), CURRENCY,
                        r["reference"], r["description"], r["task_id"] or "", r["source"]])
        name = "ist-kosten"
    else:
        data = get_budget(pid, None, user, db)
        w.writerow(["Kostenstelle", "Kostenart", "Budget", "Plan", "Ist", "Plan-Ist", "Währung"])
        for m in data["matrix"]:
            w.writerow([_lbl(cc, m["cost_center_id"]), _lbl(ct, m["cost_type_id"]),
                        "" if m["budget"] is None else _de(m["budget"]), _de(m["plan"]), _de(m["actual"]),
                        _de(m["plan"] - m["actual"]), CURRENCY])
        name = "plan-ist-abgleich"
    return Response(buf.getvalue().encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="%s.csv"' % name})


def _de(v: float) -> str:
    return ("%.2f" % v).replace(".", ",")


def _lbl(master: Dict[int, Dict[str, Any]], i: Optional[int]) -> str:
    m = master.get(i)
    return ("%s %s" % (m["code"], m["name"])).strip() if m else "nicht zugeordnet"


# ── Stammdaten: Kostenstellen / Kostenarten ─────────────────────────────────
def _register(kind: str, table: str) -> None:
    @router.post("/projects/{pid}/%s" % kind, status_code=201, name="create_" + table)
    def create(pid: int, body: MasterIn, user=Depends(access.costs("edit")), db=Depends(get_db, scope="function")):
        code = body.code.strip()
        if db.execute("SELECT 1 FROM %s WHERE project_id=? AND code=?" % table, (pid, code)).fetchone():
            raise HTTPException(409, "%s %s existiert bereits" % (LABEL[table], code))
        db.execute("INSERT INTO %s(project_id, code, name) VALUES (?,?,?)" % table, (pid, code, body.name.strip()))
        svc.bump(db, pid)
        return finance_state(db, pid, user)

    @router.put("/%s/{rid}" % kind, name="update_" + table)
    def update(rid: int, body: MasterIn, user=Depends(current_user), db=Depends(get_db, scope="function")):
        pid = _need_edit(db, user, _pid_of(db, table, rid))
        code = body.code.strip()
        if db.execute("SELECT 1 FROM %s WHERE project_id=? AND code=? AND id<>?" % table, (pid, code, rid)).fetchone():
            raise HTTPException(409, "%s %s existiert bereits" % (LABEL[table], code))
        db.execute("UPDATE %s SET code=?, name=? WHERE id=?" % table, (code, body.name.strip(), rid))
        svc.bump(db, pid)
        return finance_state(db, pid, user)

    @router.delete("/%s/{rid}" % kind, name="delete_" + table)
    def delete(rid: int, user=Depends(current_user), db=Depends(get_db, scope="function")):
        pid = _need_edit(db, user, _pid_of(db, table, rid))
        col = "cost_center_id" if table == "cost_centers" else "cost_type_id"
        for t in ("resources", "cost_items", "budget_lines", "actuals"):
            n = db.execute("SELECT COUNT(*) FROM %s WHERE %s=?" % (t, col), (rid,)).fetchone()[0]
            if n:
                raise HTTPException(409, "Wird noch verwendet (%s: %d Einträge)" % (t, n))
        db.execute("DELETE FROM %s WHERE id=?" % table, (rid,))
        svc.bump(db, pid)
        return finance_state(db, pid, user)

    @router.post("/projects/{pid}/%s/import" % kind, name="import_" + table)
    def import_master(pid: int, body: MasterImportIn, user=Depends(access.costs("edit")), db=Depends(get_db, scope="function")):
        """Zeilen 'Code;Name' (auch Tab) – vorhandene Codes werden aktualisiert (z. B. SAP-Stammdatenexport)."""
        n_new = n_upd = 0
        for i, line in enumerate(body.text.splitlines()):
            parts = [p.strip() for p in line.replace("\t", ";").split(";")]
            if not parts or not parts[0]:
                continue
            if i == 0 and parts[0].lower() in ("code", "kostenstelle", "kostenart", "nummer"):
                continue
            code, name = parts[0][:40], (parts[1] if len(parts) > 1 else "")[:200]
            ex = db.execute("SELECT id FROM %s WHERE project_id=? AND code=?" % table, (pid, code)).fetchone()
            if ex:
                db.execute("UPDATE %s SET name=? WHERE id=?" % table, (name, ex["id"]))
                n_upd += 1
            else:
                db.execute("INSERT INTO %s(project_id, code, name) VALUES (?,?,?)" % table, (pid, code, name))
                n_new += 1
        svc.bump(db, pid)
        svc.log(db, pid, user, "%s-Import" % LABEL[table], "%d neu, %d aktualisiert" % (n_new, n_upd))
        return finance_state(db, pid, user)


for _k, _t in MASTER.items():
    _register(_k, _t)


# ── Plankosten (feste Kosten je Vorgang) ────────────────────────────────────
def _check_item_refs(db, pid, body) -> None:
    _ref_ok(db, "cost_types", pid, body.cost_type_id, "Kostenart")
    _ref_ok(db, "cost_centers", pid, body.cost_center_id, "Kostenstelle")


@router.post("/tasks/{tid}/cost-items", status_code=201)
def add_item(tid: int, body: CostItemIn, user=Depends(current_user), db=Depends(get_db, scope="function")):
    pid = _need_edit(db, user, _pid_of(db, "tasks", tid))
    _check_item_refs(db, pid, body)
    db.execute("INSERT INTO cost_items(project_id, task_id, cost_type_id, cost_center_id, amount, description) "
               "VALUES (?,?,?,?,?,?)", (pid, tid, body.cost_type_id, body.cost_center_id, body.amount, body.description))
    svc.bump(db, pid)
    return finance_state(db, pid, user)


@router.put("/cost-items/{iid}")
def update_item(iid: int, body: CostItemIn, user=Depends(current_user), db=Depends(get_db, scope="function")):
    pid = _need_edit(db, user, _pid_of(db, "cost_items", iid))
    _check_item_refs(db, pid, body)
    db.execute("UPDATE cost_items SET cost_type_id=?, cost_center_id=?, amount=?, description=? WHERE id=?",
               (body.cost_type_id, body.cost_center_id, body.amount, body.description, iid))
    svc.bump(db, pid)
    return finance_state(db, pid, user)


@router.delete("/cost-items/{iid}")
def delete_item(iid: int, user=Depends(current_user), db=Depends(get_db, scope="function")):
    pid = _need_edit(db, user, _pid_of(db, "cost_items", iid))
    db.execute("DELETE FROM cost_items WHERE id=?", (iid,))
    svc.bump(db, pid)
    return finance_state(db, pid, user)


# ── Budget ──────────────────────────────────────────────────────────────────
@router.put("/projects/{pid}/budget-lines")
def put_budget_lines(pid: int, lines: List[BudgetLineIn], user=Depends(access.costs("edit")), db=Depends(get_db, scope="function")):
    seen = set()
    for ln in lines:
        _ref_ok(db, "cost_centers", pid, ln.cost_center_id, "Kostenstelle")
        _ref_ok(db, "cost_types", pid, ln.cost_type_id, "Kostenart")
        k = (ln.cost_center_id, ln.cost_type_id)
        if k in seen:
            raise HTTPException(422, "Budgetzeile doppelt (gleiche Kostenstelle/Kostenart)")
        seen.add(k)
    db.execute("DELETE FROM budget_lines WHERE project_id=?", (pid,))
    for ln in lines:
        db.execute("INSERT INTO budget_lines(project_id, cost_center_id, cost_type_id, amount) VALUES (?,?,?,?)",
                   (pid, ln.cost_center_id, ln.cost_type_id, ln.amount))
    svc.bump(db, pid)
    svc.log(db, pid, user, "Budget geändert", "%d Zeilen" % len(lines))
    return finance_state(db, pid, user)


# ── Ist-Kosten ──────────────────────────────────────────────────────────────
def _actual_refs(db, pid, body) -> None:
    _ref_ok(db, "cost_types", pid, body.cost_type_id, "Kostenart")
    _ref_ok(db, "cost_centers", pid, body.cost_center_id, "Kostenstelle")
    _ref_ok(db, "tasks", pid, body.task_id, "Vorgang")


@router.get("/projects/{pid}/actuals")
def list_actuals(pid: int, limit: int = 200, offset: int = 0, q: str = "",
                 user=Depends(access.costs("view")), db=Depends(get_db, scope="function")):
    where, args = "project_id=?", [pid]
    if q.strip():
        where += " AND (reference LIKE ? OR description LIKE ?)"
        args += ["%" + q.strip() + "%"] * 2
    total = db.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM actuals WHERE " + where, args).fetchone()
    rows = db.execute("SELECT * FROM actuals WHERE %s ORDER BY booking_date DESC, id DESC LIMIT ? OFFSET ?" % where,
                      args + [min(max(limit, 1), 1000), max(offset, 0)]).fetchall()
    return {"total": total[0], "sum": total[1], "items": [dict(r) for r in rows]}


@router.post("/projects/{pid}/actuals", status_code=201)
def add_actual(pid: int, body: ActualIn, user=Depends(access.costs("edit")), db=Depends(get_db, scope="function")):
    _actual_refs(db, pid, body)
    db.execute("INSERT INTO actuals(project_id, task_id, booking_date, cost_type_id, cost_center_id, amount, reference, "
               "description, source, created_by) VALUES (?,?,?,?,?,?,?,?, 'manual', ?)",
               (pid, body.task_id, body.booking_date.isoformat(), body.cost_type_id, body.cost_center_id, body.amount,
                body.reference, body.description, user["username"]))
    svc.bump(db, pid)
    svc.log(db, pid, user, "Ist-Kosten gebucht", "%s EUR %s" % (_de(body.amount), body.description), body.task_id)
    return {"ok": True}


@router.put("/actuals/{aid}")
def update_actual(aid: int, body: ActualIn, user=Depends(current_user), db=Depends(get_db, scope="function")):
    pid = _need_edit(db, user, _pid_of(db, "actuals", aid))
    _actual_refs(db, pid, body)
    db.execute("UPDATE actuals SET task_id=?, booking_date=?, cost_type_id=?, cost_center_id=?, amount=?, reference=?, "
               "description=? WHERE id=?", (body.task_id, body.booking_date.isoformat(), body.cost_type_id,
                                            body.cost_center_id, body.amount, body.reference, body.description, aid))
    svc.bump(db, pid)
    return {"ok": True}


@router.delete("/actuals/{aid}")
def delete_actual(aid: int, user=Depends(current_user), db=Depends(get_db, scope="function")):
    pid = _need_edit(db, user, _pid_of(db, "actuals", aid))
    db.execute("DELETE FROM actuals WHERE id=?", (aid,))
    svc.bump(db, pid)
    return {"ok": True}


# ── CSV-Import (SAP-Abgleich) ───────────────────────────────────────────────
ALIASES = {
    "date": {"buchungsdatum", "datum", "date", "belegdatum", "buchungs-datum", "budat", "bldat", "bookingdate"},
    "amount": {"betrag", "amount", "wert", "betrageur", "betrag(eur)", "betraginhauswährung", "betraginhauswaehrung"},
    "cc": {"kostenstelle", "costcenter", "cost center", "kostl", "kst", "kostenstellenr"},
    "ct": {"kostenart", "costelement", "cost element", "kstar", "kostenartnr"},
    "ref": {"belegnummer", "belegnr", "beleg", "reference", "referenz", "belnr", "belegnr."},
    "text": {"text", "beschreibung", "buchungstext", "description", "bezeichnung", "sgtxt"},
    "task": {"vorgang", "psp", "psp-nr", "pspnr", "task", "wbs"},
    "cur": {"währung", "waehrung", "currency", "waers", "whrg"},
}


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def _parse_date(s: str) -> date:
    s = s.strip()
    if "-" in s[:5]:
        return date.fromisoformat(s[:10])
    d, m, y = s.split(".")
    return date(int(y) + 2000 if len(y) == 2 else int(y), int(m), int(d))


def _norm_code(c: str) -> str:
    return c.strip().lstrip("0") or "0"


@router.post("/projects/{pid}/actuals/import")
async def import_actuals(pid: int, file: UploadFile = File(...), dry_run: bool = Form(True),
                         create_missing: bool = Form(False), partial: bool = Form(False),
                         user=Depends(access.costs("edit")), db=Depends(get_db, scope="function")):
    raw = await file.read()
    if len(raw) > 20 * 1024 * 1024:
        raise HTTPException(413, "Datei zu groß (max. 20 MB)")
    text = _decode(raw)
    head = text.splitlines()[0] if text.strip() else ""
    delim = max(";\t,", key=lambda d: head.count(d))
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    if len(rows) < 2:
        raise HTTPException(422, "Datei enthält keine Datenzeilen")
    cols: Dict[str, int] = {}
    for i, h in enumerate(rows[0]):
        k = h.strip().lower().replace(" ", "") if h else ""
        for field, names in ALIASES.items():
            if field not in cols and (k in {n.replace(" ", "") for n in names}):
                cols[field] = i
    for need in ("date", "amount"):
        if need not in cols:
            raise HTTPException(422, "Spalte fehlt: %s (erkannt: %s)" % (
                {"date": "Buchungsdatum", "amount": "Betrag"}[need], ", ".join(r.strip() for r in rows[0])))

    ccs = {r["code"]: r["id"] for r in db.execute("SELECT id, code FROM cost_centers WHERE project_id=?", (pid,))}
    cts = {r["code"]: r["id"] for r in db.execute("SELECT id, code FROM cost_types WHERE project_id=?", (pid,))}
    ccn = {_norm_code(k): v for k, v in ccs.items()}
    ctn = {_norm_code(k): v for k, v in cts.items()}
    wbs: Dict[str, int] = {}
    if "task" in cols:
        wbs = {t["wbs"]: t["id"] for t in svc.load_project(db, pid, user)["tasks"]}
    existing = {(r["reference"], r["cost_center_id"], r["cost_type_id"], round(r["amount"], 2), r["booking_date"])
                for r in db.execute("SELECT * FROM actuals WHERE project_id=? AND reference<>''", (pid,))}

    def cell(r: List[str], f: str) -> str:
        return r[cols[f]].strip() if f in cols and cols[f] < len(r) else ""

    parsed, errors, dups = [], [], 0
    new_cc: Dict[str, str] = {}
    new_ct: Dict[str, str] = {}
    seen = set()
    for n, r in enumerate(rows[1:], start=2):
        if not any(x.strip() for x in r):
            continue
        try:
            cur = cell(r, "cur").upper()
            if cur and cur != CURRENCY:
                raise ValueError("Währung %s nicht unterstützt (nur EUR)" % cur)
            d = _parse_date(cell(r, "date"))
            amt = budget.parse_amount(cell(r, "amount"))
            cc_code, ct_code = cell(r, "cc"), cell(r, "ct")
            cc_id = ct_id = None
            if cc_code:
                cc_id = ccs.get(cc_code) or ccn.get(_norm_code(cc_code))
                if cc_id is None:
                    if not create_missing:
                        raise ValueError("Kostenstelle %s unbekannt" % cc_code)
                    new_cc[cc_code] = cc_code
            if ct_code:
                ct_id = cts.get(ct_code) or ctn.get(_norm_code(ct_code))
                if ct_id is None:
                    if not create_missing:
                        raise ValueError("Kostenart %s unbekannt" % ct_code)
                    new_ct[ct_code] = ct_code
            tcode = cell(r, "task")
            task_id = None
            if tcode:
                task_id = wbs.get(tcode)
                if task_id is None:
                    raise ValueError("Vorgang (PSP-Nr.) %s unbekannt" % tcode)
            ref = cell(r, "ref")[:80]
            key = (ref, cc_id if cc_id else cc_code or None, ct_id if ct_id else ct_code or None, round(amt, 2), d.isoformat())
            if ref and (key in existing or key in seen):
                dups += 1
                continue
            seen.add(key)
            parsed.append({"row": n, "booking_date": d.isoformat(), "amount": amt, "cc_code": cc_code, "ct_code": ct_code,
                           "cc_id": cc_id, "ct_id": ct_id, "task_id": task_id, "reference": ref,
                           "description": cell(r, "text")[:300]})
        except (ValueError, KeyError, IndexError) as e:
            errors.append({"row": n, "message": str(e) or "Zeile nicht lesbar"})

    report = {"dry_run": dry_run, "rows": len(rows) - 1, "valid": len(parsed), "duplicates": dups, "errors": errors[:200],
              "error_count": len(errors), "sum": round(sum(p["amount"] for p in parsed), 2),
              "new_cost_centers": sorted(new_cc), "new_cost_types": sorted(new_ct), "preview": parsed[:15],
              "imported": 0, "columns": sorted(cols)}
    if dry_run or (errors and not partial) or not parsed:
        return report
    for code in new_cc:
        ccs[code] = db.execute("INSERT INTO cost_centers(project_id, code, name) VALUES (?,?,'')", (pid, code)).lastrowid
    for code in new_ct:
        cts[code] = db.execute("INSERT INTO cost_types(project_id, code, name) VALUES (?,?,'')", (pid, code)).lastrowid
    for p in parsed:
        cc_id = p["cc_id"] or (ccs.get(p["cc_code"]) if p["cc_code"] else None)
        ct_id = p["ct_id"] or (cts.get(p["ct_code"]) if p["ct_code"] else None)
        db.execute("INSERT INTO actuals(project_id, task_id, booking_date, cost_type_id, cost_center_id, amount, reference, "
                   "description, source, created_by) VALUES (?,?,?,?,?,?,?,?, 'import', ?)",
                   (pid, p["task_id"], p["booking_date"], ct_id, cc_id, p["amount"], p["reference"], p["description"],
                    user["username"]))
    report["imported"] = len(parsed)
    svc.bump(db, pid)
    svc.log(db, pid, user, "Ist-Kosten-Import", "%s: %d Buchungen, Summe %s EUR" % (file.filename, len(parsed), _de(report["sum"])))
    return report
