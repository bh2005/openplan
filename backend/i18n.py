"""Mehrsprachigkeit für vom Server erzeugte Texte (Benachrichtigungen, E-Mails, Reports).

Der deutsche Text (Standardsprache) ist zugleich der Schlüssel – wie im Frontend (``frontend/src/lib/i18n.ts``).
``tr("en", "Fällig %s: %s", a, b)`` liefert den englischen Text, ``tr("de", …)`` bzw. ein fehlender Eintrag den deutschen.
Die Sprache stammt aus dem Benutzerprofil des Empfängers (``users.lang``, NULL = Deutsch).
"""
from __future__ import annotations

from typing import Any, Callable, Optional, Union

LANGS = ("de", "en")

EN = {
    # Benachrichtigungen / E-Mail-Rahmen
    "Öffnen: %s": "Open: %s",
    "— OpenPlan (automatische Nachricht)": "— OpenPlan (automatic message)",
    "In OpenPlan öffnen": "Open in OpenPlan",
    "Automatische Nachricht von OpenPlan.": "Automatic message from OpenPlan.",
    "Arbeitspaket": "Work package",
    "Vorgang": "Task",
    "Projekt: %s\n%s: %s\nZugeteilt von: %s": "Project: %s\n%s: %s\nAssigned by: %s",
    "Projekt: %s\n%s: %s\nGeändert von: %s": "Project: %s\n%s: %s\nChanged by: %s",
    "%s zugeteilt: %s": "%s assigned: %s",
    "Zuteilung entfernt: %s": "Assignment removed: %s",
    "%s hat dich erwähnt: %s": "%s mentioned you: %s",
    "Neuer Kommentar von %s: %s": "New comment from %s: %s",
    "Projekt: %s\nVorgang: %s\n\n%s": "Project: %s\nTask: %s\n\n%s",
    # Erinnerungen
    "Projekt: %s\nVorgang: %s %s\n%s: %s\nStatus: %s, %d %% fertig": "Project: %s\nTask: %s %s\n%s: %s\nStatus: %s, %d %% complete",
    "Frist": "Deadline",
    "Ende": "End",
    "heute": "today",
    "morgen": "tomorrow",
    "in %d Tagen": "in %d days",
    "Fällig %s: %s": "Due %s: %s",
    "Überfällig seit %d Tag: %s": "Overdue for %d day: %s",
    "Überfällig seit %d Tagen: %s": "Overdue for %d days: %s",
    "Eskalation: seit %d Tagen überfällig – %s": "Escalation: overdue for %d days – %s",
    "\nBearbeiter: ": "\nAssignee: ",
    "niemand zugeordnet": "nobody assigned",
    "Blockiert seit %d Tagen: %s": "Blocked for %d days: %s",
    "\nGrund: ": "\nReason: ",
    "offen": "open",
    "in Arbeit": "in progress",
    "blockiert": "blocked",
    "erledigt": "done",
    # Projektreport
    "Projektreport: %s (%s)": "Project report: %s (%s)",
    "Fortschritt %d %% · %d von %d erledigt · %d in Arbeit · %d blockiert · %d überfällig · geplantes Ende %s":
        "Progress %d %% · %d of %d done · %d in progress · %d blocked · %d overdue · planned end %s",
    "Deine offenen Vorgänge": "Your open tasks",
    "Überfällig": "Overdue",
    "Blockiert": "Blocked",
    "Anstehend (14 Tage)": "Upcoming (14 days)",
    "Offen im Pool": "Open in pool",
    "Offen im Pool (zur Selbstübernahme)": "Open in pool (for self-service)",
    "- %s %s [%s, bis %s%s]%s\n%s": "- %s %s [%s, until %s%s]%s\n%s",
    "\nProjekt öffnen: %s": "\nOpen project: %s",
    "\n— OpenPlan (automatischer Report)": "\n— OpenPlan (automatic report)",
    "PSP": "WBS",
    "Status": "Status",
    "Bearbeiter": "Assignee",
    "… und %d weitere": "… and %d more",
    "Fortschritt": "Progress",
    "überfällig": "overdue",
    "Projekt öffnen": "Open project",
    "Projektreport: %s": "Project report: %s",
    "Stand %s · geplantes Ende %s · Verantwortlich: %s": "As of %s · planned end %s · Owner: %s",
    "Automatischer Report von OpenPlan.": "Automatic report from OpenPlan.",
    "abgeschlossen": "completed",
    ", %d abgeschlossen": ", %d completed",
    " – Grund: %s": " – reason: %s",
    "%d Frist(en) überschritten": "%d deadline(s) exceeded",
    "%d %% überfällig (%d von %d)": "%d %% overdue (%d of %d)",
    "%d überfällig": "%d overdue",
    "%d blockiert": "%d blocked",
    "Projektreport %s: %d %% fertig, %d überfällig, %d blockiert": "Project report %s: %d %% complete, %d overdue, %d blocked",
    "Stand %s": "As of %s",
    # Portfolio / Kostenstellen
    "kritisch": "critical",
    "Achtung": "attention",
    "im Plan": "on track",
    "Kostenstellen-Report": "Cost centre report",
    "Portfolio-Report": "Portfolio report",
    "%d Projekte: %d kritisch, %d Achtung, %d im Plan": "%d projects: %d critical, %d attention, %d on track",
    " · Ist %s von Budget %s": " · Actual %s of budget %s",
    " (%+d T ggü. Basisplan)": " (%+d d vs. baseline)",
    "- [%s] %s: %d %% fertig, Ende %s%s, %d überfällig, %d blockiert%s\n  %s": "- [%s] %s: %d %% complete, end %s%s, %d overdue, %d blocked%s\n  %s",
    "Dir sind keine Kostenstellen zugeordnet.": "No cost centres are assigned to you.",
    "= Kostenstelle %s %s gesamt: Budget %s, Plan %s, Ist %s, Rest %s%s": "= Cost centre %s %s total: budget %s, plan %s, actual %s, remainder %s%s",
    "  ⚠ Budget überschritten": "  ⚠ budget exceeded",
    "- %s: Budget %s, Plan %s, Ist %s, Rest %s%s": "- %s: budget %s, plan %s, actual %s, remainder %s%s",
    "  ⚠ überschritten": "  ⚠ exceeded",
    "\nOnline ansehen: %s/reports/%d": "\nView online: %s/reports/%d",
    "Budget": "Budget",
    "Ist": "Actual",
    "Projekt": "Project",
    "Fertig": "Done",
    "Δ Basisplan": "Δ baseline",
    "Kostenstelle %s %s – gesamt": "Cost centre %s %s – total",
    "Kostenstelle / Projekt": "Cost centre / project",
    "Plan": "Plan",
    "T": "d",
    "Rest": "Remainder",
    "Online ansehen": "View online",
    "%s: %d Projekte, %d kritisch, %d Achtung": "%s: %d projects, %d critical, %d attention",
    "%s: %d Kostenstelle(n), %d über Budget": "%s: %d cost centre(s), %d over budget",
    # Test-Mail
    "OpenPlan: Testnachricht": "OpenPlan: test message",
    "Wenn du diese Nachricht liest, funktioniert der Mailversand von OpenPlan.\n\nGesendet von %s.":
        "If you are reading this message, OpenPlan's email sending works.\n\nSent by %s.",
}

Msg = Union[str, Callable[[str], str]]


def norm(lang: Optional[str]) -> str:
    return "en" if lang == "en" else "de"


def tr(lang: Optional[str], s: str, *args: Any) -> str:
    out = EN.get(s, s) if norm(lang) == "en" else s
    return out % args if args else out


def render(msg: Msg, lang: Optional[str]) -> str:
    """Nachricht in der Empfängersprache: fester Text oder ``lambda L: tr(L, …)``."""
    return msg(norm(lang)) if callable(msg) else msg


def user_lang(db, user_id: Optional[int]) -> str:
    if not user_id:
        return "de"
    r = db.execute("SELECT lang FROM users WHERE id=?", (user_id,)).fetchone()
    return norm(r["lang"] if r else None)
