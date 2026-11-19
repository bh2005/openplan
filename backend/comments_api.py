"""Kommentare an Vorgängen mit @-Erwähnung. Erwähnte Projektbeteiligte und die Bearbeiter des Vorgangs werden benachrichtigt."""
from __future__ import annotations

import re
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

import access
import mailer
import notify
from i18n import tr
import service as svc
from auth import current_user
from database import get_db

router = APIRouter(prefix="/api")
MENTION = re.compile(r"(?<![\w@])@([A-Za-z0-9][A-Za-z0-9._\-]*)")


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


def people(db, pid: int) -> List[Dict[str, Any]]:
    """Projektbeteiligte (Verantwortlicher + Mitglieder), die man erwähnen kann."""
    rows = db.execute("SELECT u.id, u.username FROM users u WHERE u.id=(SELECT owner_id FROM projects WHERE id=?) "
                      "UNION SELECT u.id, u.username FROM project_members m JOIN users u ON u.id=m.user_id WHERE m.project_id=?", (pid, pid))
    return [dict(r) for r in rows]


def mentioned(body: str, ppl: List[Dict[str, Any]]) -> List[int]:
    by = {p["username"].lower(): p["id"] for p in ppl}
    out = []
    for m in MENTION.findall(body):
        uid = by.get(m.lower()) or by.get(m.lower().rstrip("._-"))
        if uid and uid not in out:
            out.append(uid)
    return out


def _out(db, tid: int, user) -> Dict[str, Any]:
    pid = db.execute("SELECT project_id FROM tasks WHERE id=?", (tid,)).fetchone()["project_id"]
    lvl = access.level_of(db, user, pid)
    items = []
    for r in db.execute("SELECT c.id, c.user_id, c.username, COALESCE(u.display_name, '') AS display_name, c.body, c.created_at "
                         "FROM comments c LEFT JOIN users u ON u.id=c.user_id WHERE c.task_id=? ORDER BY c.id", (tid,)):
        d = dict(r)
        d["can_delete"] = bool(lvl >= 4 or (d["user_id"] == user["id"] and lvl >= 2))
        items.append(d)
    return {"items": items, "people": [p["username"] for p in people(db, pid)]}


@router.get("/tasks/{tid}/comments")
def list_comments(tid: int, user=Depends(access.task("view")), db=Depends(get_db, scope="function")):
    return _out(db, tid, user)


@router.post("/tasks/{tid}/comments", status_code=201)
def add_comment(tid: int, body: CommentIn, request: Request, user=Depends(access.task_own()), db=Depends(get_db, scope="function")):
    t = svc.project_of_task(db, tid)
    pid = t["project_id"]
    text = body.body.strip()
    if not text:
        raise HTTPException(422, "Kommentar ist leer")
    db.execute("INSERT INTO comments(project_id, task_id, user_id, username, body) VALUES (?,?,?,?,?)", (pid, tid, user["id"], user["username"], text))
    svc.bump(db, pid)
    svc.log(db, pid, user, "Kommentar", "%s: %s" % (t["name"], text[:120]), tid)
    ppl = people(db, pid)
    mention_ids = [i for i in mentioned(text, ppl) if i != user["id"]]
    assignees = [r["user_id"] for r in db.execute(
        "SELECT DISTINCT r.user_id FROM assignments a JOIN resources r ON r.id=a.resource_id WHERE a.task_id=? AND r.user_id IS NOT NULL", (tid,))]
    others = [i for i in assignees if i != user["id"] and i not in mention_ids]
    proj = db.execute("SELECT name FROM projects WHERE id=?", (pid,)).fetchone()["name"]
    base = str(request.base_url)
    who, tname, snippet = user.get("display_name") or user["username"], t["name"], text[:500]
    ctx = lambda L: tr(L, "Projekt: %s\nVorgang: %s\n\n%s", proj, tname, snippet)  # noqa: E731
    mails = notify.create(db, mention_ids, pid, tid, "mention", lambda L: tr(L, "%s hat dich erwähnt: %s", who, tname), ctx, base)
    mails += notify.create(db, others, pid, tid, "comment", lambda L: tr(L, "Neuer Kommentar von %s: %s", who, tname), ctx, base)
    mailer.dispatch(db, mails)
    return _out(db, tid, user)


@router.delete("/comments/{cid}")
def delete_comment(cid: int, user=Depends(current_user), db=Depends(get_db, scope="function")):
    c = db.execute("SELECT * FROM comments WHERE id=?", (cid,)).fetchone()
    if not c:
        raise HTTPException(404, "Kommentar nicht gefunden")
    access.check(db, user, c["project_id"], "view")
    lvl = access.level_of(db, user, c["project_id"])
    if not (lvl >= 4 or (c["user_id"] == user["id"] and lvl >= 2)):
        raise HTTPException(403, "Nur der Autor oder der Verantwortliche kann den Kommentar löschen")
    db.execute("DELETE FROM comments WHERE id=?", (cid,))
    svc.bump(db, c["project_id"])
    return _out(db, c["task_id"], user)
