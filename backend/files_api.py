"""Dokumente (Lieferscheine, Stundenzettel, Excel-Tabellen …) an Vorgängen.

Sicherheit: Dateien liegen unter ``DATA_DIR/files/<projekt>/<uuid>`` (nie unter dem Webroot, der Original-
Dateiname landet nur in der DB); Auslieferung immer als Download (``attachment``) mit ``nosniff`` und
restriktiver CSP; Vorschau nur für PDF/Bilder. Größenlimit wird beim Streamen erzwungen.
"""
from __future__ import annotations

import os
import re
import shutil
import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import access
import service as svc
from auth import current_user
from config import FILES_DIR, MAX_UPLOAD_MB
from database import get_db

router = APIRouter(prefix="/api")
MAX_BYTES = MAX_UPLOAD_MB * 1024 * 1024
MAX_FILES_PER_REQUEST = 20
# ausführbare/skriptfähige Formate sind als Projektdokument unerwünscht
BLOCKED_EXT = {".exe", ".dll", ".bat", ".cmd", ".com", ".scr", ".msi", ".ps1", ".vbs", ".vbe", ".js", ".jse", ".jar",
               ".sh", ".lnk", ".hta", ".html", ".htm", ".svg", ".xhtml"}
INLINE_OK = {"application/pdf", "image/png", "image/jpeg", "image/gif", "image/webp"}
_CHUNK = 1024 * 1024


def clean_name(name: Optional[str]) -> str:
    n = (name or "datei").replace("\\", "/").split("/")[-1]           # Pfadanteile entfernen
    n = re.sub(r"[\x00-\x1f\x7f]", "", n).strip().strip(".")
    return (n or "datei")[:200]


def _dir(pid: int) -> str:
    return os.path.join(str(FILES_DIR), str(pid))


def _row(r) -> Dict[str, Any]:
    return {k: r[k] for k in ("id", "task_id", "filename", "size", "mime", "comment", "uploaded_by", "uploaded_at", "kind", "url")}


def remove_task_files(db, task_id: int) -> None:
    """Löscht die Dateien eines Vorgangs samt aller Teilvorgänge von der Platte (DB-Zeilen: CASCADE)."""
    rows = db.execute(
        "WITH RECURSIVE sub(id) AS (SELECT ? UNION ALL SELECT t.id FROM tasks t JOIN sub ON t.parent_id=sub.id) "
        "SELECT project_id, stored_name FROM task_files WHERE kind='file' AND task_id IN (SELECT id FROM sub)", (task_id,)).fetchall()
    for r in rows:
        try:
            os.remove(os.path.join(_dir(r["project_id"]), r["stored_name"]))
        except OSError:
            pass


def remove_project_files(pid: int) -> None:
    shutil.rmtree(_dir(pid), ignore_errors=True)


@router.get("/tasks/{tid}/files")
def list_files(tid: int, user=Depends(access.task("view")), db=Depends(get_db, scope="function")):
    return [_row(r) for r in db.execute("SELECT * FROM task_files WHERE task_id=? ORDER BY uploaded_at DESC, id DESC", (tid,))]


@router.post("/tasks/{tid}/files", status_code=201)
async def upload_files(tid: int, files: List[UploadFile] = File(...), comment: str = Form(""),
                       user=Depends(access.task_own()), db=Depends(get_db, scope="function")):
    t = svc.project_of_task(db, tid)
    pid = t["project_id"]
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(422, "Höchstens %d Dateien pro Upload" % MAX_FILES_PER_REQUEST)
    os.makedirs(_dir(pid), exist_ok=True)
    saved: List[str] = []
    try:
        for f in files:
            name = clean_name(f.filename)
            if os.path.splitext(name)[1].lower() in BLOCKED_EXT:
                raise HTTPException(415, "Dateityp nicht erlaubt: %s" % name)
            stored = uuid.uuid4().hex
            path = os.path.join(_dir(pid), stored)
            size = 0
            with open(path, "wb") as out:
                saved.append(path)
                while True:
                    chunk = await f.read(_CHUNK)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise HTTPException(413, "%s: Datei größer als %d MB" % (name, MAX_UPLOAD_MB))
                    out.write(chunk)
            if size == 0:
                raise HTTPException(422, "%s ist leer" % name)
            db.execute("INSERT INTO task_files(project_id, task_id, filename, stored_name, size, mime, comment, uploaded_by) "
                       "VALUES (?,?,?,?,?,?,?,?)", (pid, tid, name, stored, size, (f.content_type or "application/octet-stream")[:100],
                                                    comment.strip()[:300], user["username"]))
    except Exception:
        for p in saved:       # alles oder nichts: bei Fehler keine Datei-Leichen
            try:
                os.remove(p)
            except OSError:
                pass
        raise
    svc.bump(db, pid)
    svc.log(db, pid, user, "Dokument hochgeladen", ", ".join(clean_name(f.filename) for f in files), tid)
    return [_row(r) for r in db.execute("SELECT * FROM task_files WHERE task_id=? ORDER BY uploaded_at DESC, id DESC", (tid,))]


def _file_or_404(db, user, fid: int, need: str):
    r = db.execute("SELECT * FROM task_files WHERE id=?", (fid,)).fetchone()
    if not r:
        raise HTTPException(404, "Dokument nicht gefunden")
    access.check(db, user, r["project_id"], need)
    return r


class LinkIn(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    title: str = Field("", max_length=200)
    comment: str = Field("", max_length=300)


def _clean_url(raw: str) -> str:
    u = raw.strip()
    if re.search(r"[\s\x00-\x1f\x7f<>\"']", u):
        raise HTTPException(422, "Link enthält ungültige Zeichen")
    p = urlsplit(u)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise HTTPException(422, "Nur vollständige http(s)-Links sind erlaubt (z. B. https://…sharepoint.com/…)")
    return u


@router.post("/tasks/{tid}/links", status_code=201)
def add_link(tid: int, body: LinkIn, user=Depends(access.task_own()), db=Depends(get_db, scope="function")):
    """Verweis auf ein Dokument an anderer Stelle (OneDrive/SharePoint …) – es wird nichts hochgeladen."""
    t = svc.project_of_task(db, tid)
    url = _clean_url(body.url)
    p = urlsplit(url)
    title = body.title.strip() or (os.path.basename(p.path.rstrip("/")) or p.netloc)[:200]
    db.execute("INSERT INTO task_files(project_id, task_id, filename, stored_name, size, mime, comment, uploaded_by, kind, url) "
               "VALUES (?,?,?,'',0,'text/uri-list',?,?, 'link', ?)", (t["project_id"], tid, clean_name(title), body.comment.strip(), user["username"], url))
    svc.bump(db, t["project_id"])
    svc.log(db, t["project_id"], user, "Link angehängt", "%s (%s)" % (title, p.netloc), tid)
    return [_row(r) for r in db.execute("SELECT * FROM task_files WHERE task_id=? ORDER BY uploaded_at DESC, id DESC", (tid,))]


@router.get("/files/{fid}/download")
def download(fid: int, inline: bool = False, user=Depends(current_user), db=Depends(get_db, scope="function")):
    r = _file_or_404(db, user, fid, "view")
    if r["kind"] == "link":
        raise HTTPException(400, "Das ist ein Link – bitte direkt öffnen: %s" % r["url"])
    path = os.path.join(_dir(r["project_id"]), r["stored_name"])
    if not os.path.isfile(path):
        raise HTTPException(410, "Datei fehlt im Speicher")
    show = inline and r["mime"] in INLINE_OK
    return FileResponse(path, media_type=r["mime"] if show else "application/octet-stream", filename=r["filename"],
                        content_disposition_type="inline" if show else "attachment",
                        headers={"X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'none'; sandbox",
                                 "Cache-Control": "private, no-store"})


@router.delete("/files/{fid}")
def delete_file(fid: int, user=Depends(current_user), db=Depends(get_db, scope="function")):
    r = _file_or_404(db, user, fid, "work")
    if access.level_of(db, user, r["project_id"]) < 3 and r["uploaded_by"] != user["username"]:      # Mitarbeiter: nur eigene Uploads
        raise HTTPException(403, "Keine Berechtigung (benötigt: Bearbeiter)")
    db.execute("DELETE FROM task_files WHERE id=?", (fid,))
    if r["kind"] == "file":
        try:
            os.remove(os.path.join(_dir(r["project_id"]), r["stored_name"]))
        except OSError:
            pass
    svc.bump(db, r["project_id"])
    svc.log(db, r["project_id"], user, "Dokument gelöscht", r["filename"], r["task_id"])
    return {"ok": True}
