"""Datensicherung: konsistente Sicherung von SQLite-DB (Backup-API, auch im laufenden Betrieb) und Dateien als ``.tar.gz``.

Enthalten: ``openplan.db``, ``files/`` (Dokumente), ``ldap_ca.pem`` und ``manifest.json``.
Bewusst NICHT enthalten: ``jwt_secret``, ``tls/`` (private Schlüssel) – diese Geheimnisse gehören nicht in Sicherungsdateien.
Einstellungen (Zeitplan, Aufbewahrung) in ``app_settings``/``backup``. Wiederherstellung offline per CLI:
``python backup.py verify <datei>`` und ``python backup.py restore <datei> --yes`` (Container vorher stoppen).
"""
from __future__ import annotations

import datetime as dt
import io
import json
import logging
import os
import re
import shutil
import sqlite3
import sys
import tarfile
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import config

log = logging.getLogger("openplan.backup")
BACKUP_DIR = Path(os.environ.get("BACKUP_DIR") or (config.DATA_DIR / "backups"))
NAME_RE = re.compile(r"^openplan-backup-\d{8}-\d{6}\.tar\.gz$")
DEFAULTS = {"enabled": False, "hour": 2, "keep": 14}
_lock = threading.Lock()


def settings(db) -> Dict[str, Any]:
    r = db.execute("SELECT value FROM app_settings WHERE key='backup'").fetchone()
    return {**DEFAULTS, **(json.loads(r["value"]) if r else {})}


def save_settings(db, patch: Dict[str, Any]) -> Dict[str, Any]:
    s = settings(db)
    for k in DEFAULTS:
        if patch.get(k) is not None:
            s[k] = patch[k]
    if not (0 <= int(s["hour"]) <= 23) or not (1 <= int(s["keep"]) <= 365):
        raise ValueError("Uhrzeit 0–23, Aufbewahrung 1–365 Sicherungen")
    db.execute("INSERT INTO app_settings(key, value) VALUES ('backup', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps(s),))
    return s


def list_backups() -> List[Dict[str, Any]]:
    if not BACKUP_DIR.is_dir():
        return []
    out = []
    for p in BACKUP_DIR.iterdir():
        if NAME_RE.match(p.name) and p.is_file():
            st = p.stat()
            out.append({"name": p.name, "size": st.st_size, "created": dt.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")})
    return sorted(out, key=lambda x: x["name"], reverse=True)


def path_of(name: str) -> Path:
    if not NAME_RE.match(name):
        raise FileNotFoundError("Ungültiger Name")
    p = BACKUP_DIR / name
    if not p.is_file():
        raise FileNotFoundError(name)
    return p


def create(note: str = "manuell", db_path: Optional[Path] = None, files_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Sicherung erstellen. Die DB wird über die SQLite-Backup-API kopiert (konsistent bei laufenden Schreibzugriffen)."""
    db_path, files_dir = db_path or config.DB_PATH, files_dir or config.FILES_DIR
    with _lock:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        name = "openplan-backup-%s.tar.gz" % stamp
        n = 1
        while (BACKUP_DIR / name).exists():           # zwei Sicherungen in derselben Sekunde
            n += 1
            name = "openplan-backup-%s.tar.gz" % (dt.datetime.now() + dt.timedelta(seconds=n)).strftime("%Y%m%d-%H%M%S")
        final = BACKUP_DIR / name
        tmp = BACKUP_DIR / (name + ".part")
        with tempfile.TemporaryDirectory() as td:
            snap = Path(td) / "openplan.db"
            src = sqlite3.connect(str(db_path), timeout=30)
            dst = sqlite3.connect(str(snap))
            try:
                src.backup(dst)
                counts = {t: dst.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in ("users", "projects", "tasks")}
            finally:
                dst.close()
                src.close()
            nfiles = 0
            with tarfile.open(tmp, "w:gz") as tar:
                tar.add(snap, arcname="openplan.db")
                if files_dir.is_dir():
                    for f in sorted(files_dir.rglob("*")):
                        if f.is_file():
                            tar.add(f, arcname="files/" + f.relative_to(files_dir).as_posix())
                            nfiles += 1
                ca = config.DATA_DIR / "ldap_ca.pem"
                if ca.is_file():
                    tar.add(ca, arcname="ldap_ca.pem")
                man = json.dumps({"created": dt.datetime.now().isoformat(timespec="seconds"), "note": note, "counts": counts, "files": nfiles,
                                  "app": "openplan"}, indent=1).encode()
                ti = tarfile.TarInfo("manifest.json")
                ti.size, ti.mtime = len(man), time.time()
                tar.addfile(ti, io.BytesIO(man))
        try:
            tmp.chmod(0o600)
        except OSError:
            pass
        tmp.replace(final)
        log.info("Sicherung %s erstellt (%d Bytes, %s)", name, final.stat().st_size, note)
        return {"name": name, "size": final.stat().st_size, "counts": counts, "files": nfiles}


def prune(keep: int) -> int:
    old = list_backups()[keep:]
    for b in old:
        (BACKUP_DIR / b["name"]).unlink(missing_ok=True)
    return len(old)


def _safe_members(tar: tarfile.TarFile) -> List[tarfile.TarInfo]:
    ok = []
    for m in tar.getmembers():
        parts = Path(m.name).parts
        if m.name.startswith("/") or ".." in parts or not (m.isfile() or m.isdir()):
            raise ValueError("Unzulässiger Eintrag im Archiv: %s" % m.name)
        if m.name not in ("openplan.db", "manifest.json", "ldap_ca.pem") and not m.name.startswith("files"):
            raise ValueError("Unerwarteter Eintrag im Archiv: %s" % m.name)
        ok.append(m)
    return ok


def verify(path: Path) -> Dict[str, Any]:
    """Archiv prüfen: Aufbau, DB-Integrität (``PRAGMA integrity_check``), Inhaltszahlen."""
    try:
        with tarfile.open(path, "r:gz") as tar, tempfile.TemporaryDirectory() as td:
            members = _safe_members(tar)
            names = {m.name for m in members}
            if "openplan.db" not in names:
                return {"ok": False, "message": "openplan.db fehlt im Archiv"}
            with tar.extractfile("openplan.db") as f:
                (Path(td) / "openplan.db").write_bytes(f.read())
            man = {}
            if "manifest.json" in names:
                with tar.extractfile("manifest.json") as f:
                    man = json.loads(f.read())
            conn = sqlite3.connect(str(Path(td) / "openplan.db"))
            try:
                res = conn.execute("PRAGMA integrity_check").fetchone()[0]
                counts = {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in ("users", "projects", "tasks")}
            finally:
                conn.close()
            nfiles = sum(1 for m in members if m.isfile() and m.name.startswith("files/"))
            return {"ok": res == "ok", "message": "Datenbank in Ordnung" if res == "ok" else "Integritätsprüfung: " + res,
                    "counts": counts, "files": nfiles, "created": man.get("created", "")}
    except (tarfile.TarError, OSError, ValueError, sqlite3.DatabaseError, EOFError) as e:
        return {"ok": False, "message": "Archiv fehlerhaft: %s" % e}


def restore(path: Path, target: Optional[Path] = None) -> str:
    """Offline wiederherstellen (Dienst vorher stoppen!). Die bisherigen Daten bleiben als ``*.before-restore-<ts>`` erhalten."""
    target = target or config.DATA_DIR
    v = verify(path)
    if not v["ok"]:
        raise RuntimeError("Sicherung ist nicht in Ordnung: " + v["message"])
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    with tarfile.open(path, "r:gz") as tar, tempfile.TemporaryDirectory(dir=str(target)) as td:
        members = _safe_members(tar)
        tar.extractall(td, members=members, filter="data")
        db = target / "openplan.db"
        if db.exists():
            shutil.move(str(db), str(target / ("openplan.db.before-restore-" + ts)))
        for ext in ("-wal", "-shm"):
            (target / ("openplan.db" + ext)).unlink(missing_ok=True)
        shutil.copy2(Path(td) / "openplan.db", db)
        old_files = target / "files"
        if old_files.exists():
            shutil.move(str(old_files), str(target / ("files.before-restore-" + ts)))
        if (Path(td) / "files").is_dir():
            shutil.copytree(Path(td) / "files", old_files)
        else:
            old_files.mkdir(exist_ok=True)
        if (Path(td) / "ldap_ca.pem").is_file():
            shutil.copy2(Path(td) / "ldap_ca.pem", target / "ldap_ca.pem")
    return "Wiederhergestellt: %d Benutzer, %d Projekte, %d Vorgänge, %d Dateien" % (
        v["counts"]["users"], v["counts"]["projects"], v["counts"]["tasks"], v["files"])


# ── Zeitplan ────────────────────────────────────────────────────────────────
def run_scheduled(now: Optional[dt.datetime] = None) -> Optional[Dict[str, Any]]:
    from database import connect
    now = now or dt.datetime.now()
    db = connect()
    try:
        s = settings(db)
        if not s["enabled"] or now.hour < int(s["hour"]):
            return None
        today = now.strftime("%Y%m%d")
        if any(b["name"].startswith("openplan-backup-" + today) for b in list_backups()):
            return None
        res = create("automatisch")
        res["pruned"] = prune(int(s["keep"]))
        import audit
        audit.log(db, "system", "backup.auto", "%s (%d Bytes)" % (res["name"], res["size"]))
        db.commit()
        return res
    finally:
        db.close()


_started = False


def start_background(interval: float = 900.0) -> None:
    global _started
    if _started:
        return
    _started = True

    def loop():
        time.sleep(120)
        while True:
            try:
                run_scheduled()
            except Exception:
                log.exception("Automatische Sicherung fehlgeschlagen")
            time.sleep(interval)

    threading.Thread(target=loop, daemon=True, name="backup").start()


if __name__ == "__main__":
    usage = "Aufruf: python backup.py create | list | verify <datei> | restore <datei> --yes"
    a = sys.argv[1:]
    if not a:
        sys.exit(usage)
    if a[0] == "create":
        print(create("cli"))
    elif a[0] == "list":
        for b in list_backups():
            print("%s  %10d  %s" % (b["created"], b["size"], b["name"]))
    elif a[0] == "verify" and len(a) > 1:
        r = verify(Path(a[1]))
        print(r)
        sys.exit(0 if r["ok"] else 1)
    elif a[0] == "restore" and len(a) > 1:
        if "--yes" not in a:
            sys.exit("Das überschreibt die Daten in %s (Sicherung der alten Daten bleibt erhalten). Dienst stoppen und mit --yes bestätigen." % config.DATA_DIR)
        print(restore(Path(a[1])))
    else:
        sys.exit(usage)
