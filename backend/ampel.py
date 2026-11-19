"""Die Projekt-Ampel – eine Regel für Dashboard und Portfolio-Report (Vorgabe der Geschäftsführung).

  rot    = mindestens ein Vorgang plant sein Ende nach der gesetzten Frist, ODER mehr als ``OVERDUE_PCT`` % der Vorgänge sind
           überfällig, ODER irgendetwas ist blockiert
  gelb   = nicht rot, aber mindestens ein Vorgang überfällig
  grün   = sonst;  „done“ = alle Vorgänge erledigt;  „empty“ = noch keine Vorgänge
Das Budget fließt nicht in die Ampel ein (wird getrennt ausgewiesen).
"""
from __future__ import annotations

from typing import Any, Dict, List

OVERDUE_PCT = 10


def rag(total: int, done: int, overdue: int, blocked: int, deadline_missed: int) -> Dict[str, Any]:
    if not total:
        return {"status": "empty", "reasons": []}
    if done == total:
        return {"status": "done", "reasons": []}
    reasons: List[Dict[str, Any]] = []
    red = False
    if deadline_missed:
        red = True
        reasons.append({"key": "deadline", "n": deadline_missed})
    pct = overdue * 100.0 / total
    if pct > OVERDUE_PCT:
        red = True
        reasons.append({"key": "overdue_pct", "n": overdue, "total": total, "pct": round(pct)})
    elif overdue:
        reasons.append({"key": "overdue", "n": overdue})
    if blocked:
        red = True
        reasons.append({"key": "blocked", "n": blocked})
    return {"status": "red" if red else ("yellow" if overdue else "green"), "reasons": reasons}
