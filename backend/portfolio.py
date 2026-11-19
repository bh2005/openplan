"""Übergreifende Reports: Portfolio (Vorgesetzte, mehrere Projekte) und Kostenstellen (Kostenstellenverantwortliche).

Abos (``report_subscriptions``) legt ein Administrator an; Empfänger bekommen den Report per Glocke/E-Mail und können ihn unter
``/reports`` ansehen. Kostenstellenverantwortliche sind je Kostenstellen-Code hinterlegt (``cost_center_owners``) und sehen
nur die Summen ihrer Kostenstelle je Projekt – keine Vorgänge, keine anderen Kostenstellen.
"""
from __future__ import annotations

import datetime as dt
import html
import logging
from typing import Any, Dict, List, Optional

import ampel
import finance_api
import mailer
import notify
import reports
from i18n import norm, tr

log = logging.getLogger("openplan.portfolio")
RAG = {"red": "#dc2626", "yellow": "#d97706", "green": "#16a34a", "done": "#94a3b8"}
RAG_LABEL = {"red": "kritisch", "yellow": "Achtung", "green": "im Plan", "done": "abgeschlossen"}


def _norm(code: str) -> str:
    return (code or "").strip().lstrip("0").upper()


def _eur(v: Optional[float]) -> str:
    return "–" if v is None else ("{:,.0f} €".format(v)).replace(",", ".")


def _days(a: Optional[str], b: Optional[str]) -> Optional[int]:
    if not a or not b:
        return None
    return (dt.date.fromisoformat(a) - dt.date.fromisoformat(b)).days


def project_ids(db, sub) -> List[int]:
    ids = [int(x) for x in (sub["project_ids"] or "").split(",") if x.strip()]
    existing = {r["id"] for r in db.execute("SELECT id FROM projects")}
    return [i for i in ids if i in existing] if ids else sorted(existing)


def _budget(db, pid: int) -> Dict[str, Any]:
    return finance_api.get_budget(pid, None, user=reports.SYSTEM, db=db)


def project_line(db, pid: int, costs: bool, today: dt.date) -> Dict[str, Any]:
    rep = reports.build(db, pid, today)
    base_fin = db.execute("SELECT MAX(baseline_finish) AS bf FROM tasks WHERE project_id=?", (pid,)).fetchone()["bf"]
    delta = _days(rep["finish"], base_fin)
    k = rep["kpi"]
    line = {"pid": pid, "name": rep["project"], "owner": rep["owner"], "percent": k["percent"], "finish": rep["finish"],
            "delta_days": delta, "overdue": len(rep["overdue"]), "blocked": k["blocked"], "critical": k["critical"], "total": k["total"],
            "done": k["done"], "cost": None}
    a = ampel.rag(k["total"], k["done"], line["overdue"], line["blocked"], k["deadline_missed"])          # gleiche Regel wie das Dashboard
    rag = "done" if a["status"] == "empty" else a["status"]
    line["reasons"] = a["reasons"]
    if costs:
        b = _budget(db, pid)
        s = b["summary"]
        bud = s["budget"]
        if bud is None:                                   # nur Kostenstellen-Budgets gepflegt -> Summe als Gesamtbudget
            parts = [r["budget"] for r in b["by_cost_center"] if r["budget"] is not None]
            bud = sum(parts) if parts else None
        over = bool(bud is not None and s["ac"] > bud + 0.005)
        plan_over = bool(bud is not None and s["plan"] > bud + 0.005)
        line["cost"] = {"budget": bud, "plan": s["plan"], "ac": s["ac"], "eac": s["eac"], "cpi": s["cpi"], "spi": s["spi"], "over": over}
        line["cost"]["plan_over"] = plan_over                      # Budget steht neben der Ampel, beeinflusst sie nicht
    line["rag"] = rag
    return line


def build_portfolio(db, sub, today: Optional[dt.date] = None, lang: str = "de") -> Dict[str, Any]:
    today = today or dt.date.today()
    lines = [project_line(db, pid, bool(sub["include_costs"]), today) for pid in project_ids(db, sub)]
    order = {"red": 0, "yellow": 1, "green": 2, "done": 3}
    lines.sort(key=lambda r: (order[r["rag"]], r["name"].lower()))
    return {"kind": "portfolio", "title": sub["name"] or tr(lang, "Portfolio-Report"), "date": today.isoformat(), "costs": bool(sub["include_costs"]),
            "projects": lines, "counts": {k: sum(1 for r in lines if r["rag"] == k) for k in RAG}}


def build_costcenter(db, sub, today: Optional[dt.date] = None, lang: str = "de") -> Dict[str, Any]:
    today = today or dt.date.today()
    owned = [dict(r) for r in db.execute("SELECT code, name FROM cost_center_owners WHERE user_id=? ORDER BY code", (sub["user_id"],))]
    allowed = set(project_ids(db, sub))
    rows: List[Dict[str, Any]] = []
    for oc in owned:
        total = {"budget": 0.0, "has_budget": False, "plan": 0.0, "actual": 0.0}
        for p in db.execute("SELECT DISTINCT project_id FROM cost_centers WHERE UPPER(LTRIM(code,'0'))=?", (_norm(oc["code"]),)):
            pid = p["project_id"]
            if pid not in allowed:
                continue
            for cc in _budget(db, pid)["by_cost_center"]:
                if _norm(cc["code"]) != _norm(oc["code"]):
                    continue
                name = db.execute("SELECT name FROM projects WHERE id=?", (pid,)).fetchone()["name"]
                remaining = (cc["budget"] - cc["actual"]) if cc["budget"] is not None else None
                rows.append({"code": oc["code"], "cc_name": oc["name"] or cc["name"], "pid": pid, "project": name, "budget": cc["budget"],
                             "plan": cc["plan"], "actual": cc["actual"], "remaining": remaining,
                             "over": bool(cc["budget"] is not None and cc["actual"] > cc["budget"] + 0.005),
                             "plan_over": bool(cc["budget"] is not None and cc["plan"] > cc["budget"] + 0.005)})
                total["plan"] += cc["plan"]
                total["actual"] += cc["actual"]
                if cc["budget"] is not None:
                    total["budget"] += cc["budget"]
                    total["has_budget"] = True
        rows.append({"code": oc["code"], "cc_name": oc["name"], "total": True, "budget": total["budget"] if total["has_budget"] else None,
                     "plan": total["plan"], "actual": total["actual"],
                     "remaining": (total["budget"] - total["actual"]) if total["has_budget"] else None,
                     "over": bool(total["has_budget"] and total["actual"] > total["budget"] + 0.005),
                     "plan_over": bool(total["has_budget"] and total["plan"] > total["budget"] + 0.005)})
    return {"kind": "costcenter", "title": sub["name"] or tr(lang, "Kostenstellen-Report"), "date": today.isoformat(), "owned": owned, "rows": rows}


def build(db, sub, today: Optional[dt.date] = None, lang: str = "de") -> Dict[str, Any]:
    return build_portfolio(db, sub, today, lang) if sub["kind"] == "portfolio" else build_costcenter(db, sub, today, lang)


# ── Darstellung ─────────────────────────────────────────────────────────────
def _f(d: Optional[str]) -> str:
    return reports._fmt(d or "")


def reason_text(L: str, r: Dict[str, Any]) -> str:
    k = r["key"]
    if k == "deadline":
        return tr(L, "%d Frist(en) überschritten", r["n"])
    if k == "overdue_pct":
        return tr(L, "%d %% überfällig (%d von %d)", r["pct"], r["n"], r["total"])
    if k == "overdue":
        return tr(L, "%d überfällig", r["n"])
    return tr(L, "%d blockiert", r["n"])


def render_text(rep: Dict[str, Any], base: str, sub_id: int, lang: str = "de") -> str:
    L = lang
    out = ["%s (%s)" % (rep["title"], _f(rep["date"]))]
    if rep["kind"] == "portfolio":
        c = rep["counts"]
        out.append(tr(L, "%d Projekte: %d kritisch, %d Achtung, %d im Plan", len(rep["projects"]), c["red"], c["yellow"], c["green"])
                   + (tr(L, ", %d abgeschlossen", c["done"]) if c["done"] else ""))
        for r in rep["projects"]:
            cost = ""
            if r["cost"]:
                cost = tr(L, " · Ist %s von Budget %s", _eur(r["cost"]["ac"]), _eur(r["cost"]["budget"]))
            dd = tr(L, " (%+d T ggü. Basisplan)", r["delta_days"]) if r["delta_days"] else ""
            if r["reasons"]:
                cost += tr(L, " – Grund: %s", "; ".join(reason_text(L, x) for x in r["reasons"]))
            out.append(tr(L, "- [%s] %s: %d %% fertig, Ende %s%s, %d überfällig, %d blockiert%s\n  %s",
                          tr(L, RAG_LABEL[r["rag"]]), r["name"], r["percent"], _f(r["finish"]), dd, r["overdue"], r["blocked"], cost,
                          (base + notify.link_for(r["pid"])) if base else ""))
    else:
        if not rep["owned"]:
            out.append(tr(L, "Dir sind keine Kostenstellen zugeordnet."))
        for r in rep["rows"]:
            if r.get("total"):
                out.append(tr(L, "= Kostenstelle %s %s gesamt: Budget %s, Plan %s, Ist %s, Rest %s%s", r["code"], r["cc_name"], _eur(r["budget"]), _eur(r["plan"]),
                              _eur(r["actual"]), _eur(r["remaining"]), tr(L, "  ⚠ Budget überschritten") if r["over"] else ""))
            else:
                out.append(tr(L, "- %s: Budget %s, Plan %s, Ist %s, Rest %s%s", r["project"], _eur(r["budget"]), _eur(r["plan"]), _eur(r["actual"]), _eur(r["remaining"]),
                              tr(L, "  ⚠ überschritten") if r["over"] else ""))
    if base:
        out.append(tr(L, "\nOnline ansehen: %s/reports/%d", base, sub_id))
    out.append(tr(L, "\n— OpenPlan (automatischer Report)"))
    return "\n".join(out)


def render_html(rep: Dict[str, Any], base: str, sub_id: int, lang: str = "de") -> str:
    L = lang
    e = html.escape
    th = "padding:4px 8px;text-align:left"
    td = "padding:4px 8px;border-top:1px solid #e5e7eb"
    num = td + ";text-align:right"
    head = "<h2 style=\"margin:0\">%s</h2><p style=\"color:#6b7280;margin:2px 0 10px\">%s</p>" % (e(rep["title"]), tr(L, "Stand %s", _f(rep["date"])))
    body = ""
    if rep["kind"] == "portfolio":
        c = rep["counts"]
        chips = "".join("<span style=\"display:inline-block;margin-right:8px;padding:2px 10px;border-radius:10px;color:#fff;background:%s\">%d %s</span>" % (RAG[k], c[k], tr(L, RAG_LABEL[k])) for k in RAG if c[k] or k != "done")
        rows = ""
        for r in rep["projects"]:
            href = e((base + notify.link_for(r["pid"])) if base else "#", quote=True)
            dd = ("%+d %s" % (r["delta_days"], tr(L, "T"))) if r["delta_days"] else "–"
            cost = ""
            if rep["costs"]:
                co = r["cost"] or {}
                cost = "<td style=\"%s\">%s</td><td style=\"%s\">%s</td><td style=\"%s\">%s</td>" % (
                    num, _eur(co.get("budget")), num, _eur(co.get("ac")), num, "–" if co.get("cpi") is None else "%.2f" % co["cpi"])
            rows += ("<tr><td style=\"%s\"><span style=\"display:inline-block;width:10px;height:10px;border-radius:50%%;background:%s\"></span></td>"
                     "<td style=\"%s\"><a href=\"%s\">%s</a><br><small style=\"color:#6b7280\">%s</small></td><td style=\"%s\">%d %%</td><td style=\"%s\">%s</td>"
                     "<td style=\"%s\">%s</td><td style=\"%s\">%d</td><td style=\"%s\">%d</td>%s</tr>" % (
                         td, RAG[r["rag"]], td, href, e(r["name"]), e(r["owner"] + ((" · " + "; ".join(reason_text(L, x) for x in r["reasons"])) if r["reasons"] else "")), num, r["percent"], num, _f(r["finish"]), num, dd, num, r["overdue"], num, r["blocked"], cost))
        cost_h = ("<th style=\"%s\">%s</th><th style=\"%s\">%s</th><th style=\"%s\">CPI</th>" % (th, tr(L, "Budget"), th, tr(L, "Ist"), th)) if rep["costs"] else ""
        body = ("<p>%s</p><table style=\"border-collapse:collapse;font-size:13px\"><tr style=\"background:#f3f4f6\"><th style=\"%s\"></th><th style=\"%s\">%s</th>"
                "<th style=\"%s\">%s</th><th style=\"%s\">%s</th><th style=\"%s\">%s</th><th style=\"%s\">%s</th><th style=\"%s\">%s</th>%s</tr>%s</table>"
                % (chips, th, th, tr(L, "Projekt"), th, tr(L, "Fertig"), th, tr(L, "Ende"), th, tr(L, "Δ Basisplan"), th, tr(L, "überfällig"), th, tr(L, "blockiert"), cost_h, rows))
    else:
        if not rep["owned"]:
            body = "<p>%s</p>" % tr(L, "Dir sind keine Kostenstellen zugeordnet.")
        rows = ""
        for r in rep["rows"]:
            warn = "color:#dc2626;font-weight:600" if r["over"] else ""
            if r.get("total"):
                rows += ("<tr style=\"background:#f3f4f6;font-weight:600\"><td style=\"%s\">%s</td><td style=\"%s\">%s</td><td style=\"%s\">%s</td>"
                         "<td style=\"%s;%s\">%s</td><td style=\"%s\">%s</td></tr>" % (td, tr(L, "Kostenstelle %s %s – gesamt", e(r["code"]), e(r["cc_name"])), num, _eur(r["budget"]), num, _eur(r["plan"]), num, warn, _eur(r["actual"]), num, _eur(r["remaining"])))
            else:
                href = e((base + notify.link_for(r["pid"])) if base else "#", quote=True)
                rows += ("<tr><td style=\"%s\">&nbsp;&nbsp;<a href=\"%s\">%s</a></td><td style=\"%s\">%s</td><td style=\"%s\">%s</td><td style=\"%s;%s\">%s</td><td style=\"%s\">%s</td></tr>" % (
                    td, href, e(r["project"]), num, _eur(r["budget"]), num, _eur(r["plan"]), num, warn, _eur(r["actual"]), num, _eur(r["remaining"])))
        if rows:
            body += ("<table style=\"border-collapse:collapse;font-size:13px\"><tr style=\"background:#f3f4f6\"><th style=\"%s\">%s</th><th style=\"%s\">%s</th>"
                     "<th style=\"%s\">%s</th><th style=\"%s\">%s</th><th style=\"%s\">%s</th></tr>%s</table>" % (
                         th, tr(L, "Kostenstelle / Projekt"), th, tr(L, "Budget"), th, tr(L, "Plan"), th, tr(L, "Ist"), th, tr(L, "Rest"), rows))
    btn = ("<p><a href=\"%s/reports/%d\" style=\"background:#2563eb;color:#fff;padding:8px 14px;border-radius:6px;text-decoration:none\">%s</a></p>" % (e(base, quote=True), sub_id, tr(L, "Online ansehen"))) if base else ""
    return "<div style=\"font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#1f2937\">%s%s%s<p style=\"color:#6b7280;font-size:12px\">%s</p></div>" % (head, body, btn, tr(L, "Automatischer Report von OpenPlan."))


# ── Versand / Zeitplan ──────────────────────────────────────────────────────
def send(db, sub_id: int, base: str = "", today: Optional[dt.date] = None) -> Dict[str, int]:
    sub = db.execute("SELECT * FROM report_subscriptions WHERE id=?", (sub_id,)).fetchone()
    u = db.execute("SELECT id, email, notify_email, lang FROM users WHERE id=?", (sub["user_id"],)).fetchone()
    L = norm(u["lang"] if u else None)
    rep = build(db, sub, today, L)
    base = mailer.base_url(db, base)
    if rep["kind"] == "portfolio":
        c = rep["counts"]
        title = tr(L, "%s: %d Projekte, %d kritisch, %d Achtung", rep["title"], len(rep["projects"]), c["red"], c["yellow"])
    else:
        over = sum(1 for r in rep["rows"] if r.get("total") and r["over"])
        title = tr(L, "%s: %d Kostenstelle(n), %d über Budget", rep["title"], len(rep["owned"]), over)
    db.execute("INSERT INTO notifications(user_id, project_id, task_id, kind, title, body, link) VALUES (?,?,?,?,?,?,?)",
               (sub["user_id"], None, None, "report", title[:200], tr(L, "Stand %s", _f(rep["date"])), "/reports/%d" % sub_id))
    mails = []
    if mailer.configured(db) and u["email"] and u["notify_email"]:
        mails.append({"to": u["email"], "subject": title, "text": render_text(rep, base, sub_id, L), "html": render_html(rep, base, sub_id, L)})
    mailer.dispatch(db, mails)
    db.execute("UPDATE report_subscriptions SET last_sent=? WHERE id=?", ((today or dt.date.today()).isoformat(), sub_id))
    return {"notified": 1, "mails": len(mails)}


def due(db, now: Optional[dt.datetime] = None) -> List[int]:
    now = now or dt.datetime.now()
    out = []
    for r in db.execute("SELECT id, weekday, hour, last_sent FROM report_subscriptions WHERE enabled=1"):
        day_ok = now.weekday() < 5 if r["weekday"] == -1 else now.weekday() == r["weekday"]
        if day_ok and now.hour >= r["hour"] and r["last_sent"] != now.date().isoformat():
            out.append(r["id"])
    return out


def run_due(now: Optional[dt.datetime] = None) -> int:
    from database import connect
    db = connect()
    n = 0
    try:
        for sid in due(db, now):
            try:
                send(db, sid, today=(now or dt.datetime.now()).date())
                db.commit()
                n += 1
            except Exception:
                db.rollback()
                log.exception("Übergreifender Report %d fehlgeschlagen", sid)
    finally:
        db.close()
    return n
