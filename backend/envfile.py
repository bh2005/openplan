"""Lesen/Schreiben der ``.env``-Datei des Containers (Verwaltung → Server-Umgebung).

Compose liest ``.env`` nur beim *Erstellen* des Containers. Damit Änderungen aus der Oberfläche schon nach einem
einfachen Neustart wirken, bindet die Compose-Datei dieselbe Datei als ``ENV_FILE`` (``/app/.env``) ein und ``config.py``
lädt sie beim Start in ``os.environ`` (die Datei hat Vorrang). Diese Datei darf **keine** Importe aus dem Projekt haben
(sie wird von ``config.py`` ganz am Anfang geladen).

Die Datei wird zeilenweise bearbeitet: Kommentare und Leerzeilen bleiben, nur Variablenzeilen werden geändert. Werte werden
so geschrieben, dass Docker Compose (``$``-Ersetzung!) und der Lader hier dasselbe lesen.
"""
from __future__ import annotations

import hashlib
import os
import re
import signal
import threading
import time
from typing import Dict, List, Optional, Tuple

KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
LINE_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")
SECRET_RE = re.compile(r"(PASSWORD|PASSWD|SECRET|TOKEN|PASSPHRASE|PRIVATE|_KEY$)", re.I)
SAFE_RE = re.compile(r"^[A-Za-z0-9_@%+=:,./~-]+$")
DQ_RE = re.compile(r'^"((?:[^"\\]|\\.)*)"\s*(?:#.*)?$')
SQ_RE = re.compile(r"^'([^']*)'\s*(?:#.*)?$")
ESC_RE = re.compile(r'\\(["\\$])')
RESERVED = {"ENV_FILE"}                    # würde sich selbst aussperren
LOADED_HASH: Optional[str] = None          # Stand der Datei beim Start (für „Neustart nötig“)


def current_path() -> str:
    return os.environ.get("ENV_FILE", "")


def is_secret(key: str) -> bool:
    return bool(SECRET_RE.search(key))


def unquote(v: str) -> str:
    v = v.strip()
    m = DQ_RE.match(v)
    if m:
        return ESC_RE.sub(lambda x: x.group(1), m.group(1))
    m = SQ_RE.match(v)
    if m:
        return m.group(1)
    return re.split(r"\s+#", v, maxsplit=1)[0].strip()


def quote(v: str) -> str:
    if any(c in v for c in "\r\n\0"):
        raise ValueError("Zeilenumbrüche sind in Werten nicht erlaubt")
    if v == "" or SAFE_RE.match(v):
        return v
    if "'" not in v:
        return "'%s'" % v                 # Einfache Anführungszeichen: weder $-Ersetzung noch Escapes
    return '"%s"' % v.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$")


def _is_var(line: str):
    m = LINE_RE.match(line)
    return m if m and not line.lstrip().startswith("#") else None


def parse(text: str) -> List[Tuple[str, str]]:
    """Variablen in Dateireihenfolge; bei doppelten Schlüsseln gilt der letzte (wie bei Compose)."""
    seen: Dict[str, str] = {}
    for line in text.splitlines():
        m = _is_var(line)
        if m:
            seen[m.group(1)] = unquote(m.group(2))
    return list(seen.items())


def digest(items: List[Tuple[str, str]]) -> str:
    return hashlib.sha256("\n".join("%s=%s" % kv for kv in sorted(items)).encode()).hexdigest()


def read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_in_place(path: str, text: str) -> None:
    """Gleicher Inode (die Datei ist als einzelne Datei in den Container eingebunden – kein Umbenennen)."""
    with open(path, "r+", encoding="utf-8", newline="\n") as f:
        f.seek(0)
        f.write(text)
        f.truncate()


def load_into_environ(path: str) -> None:
    """Variablen aus der Datei in ``os.environ`` übernehmen (Datei hat Vorrang). Fehler führen nie zum Abbruch."""
    global LOADED_HASH
    try:
        items = parse(read(path))
    except (OSError, UnicodeDecodeError):
        return
    for k, v in items:
        if k not in RESERVED:
            os.environ[k] = v
    LOADED_HASH = digest(items)


def apply(text: str, desired: Dict[str, Optional[str]]) -> str:
    """Neue Dateifassung: Kommentare bleiben, Zeilen nicht gewünschter Schlüssel entfallen, ``None`` = Wert unverändert."""
    out: List[str] = []
    done = set()
    for line in text.splitlines():
        m = _is_var(line)
        if not m:
            out.append(line)
            continue
        key = m.group(1)
        if key not in desired or key in done:
            continue
        done.add(key)
        out.append(line if desired[key] is None else "%s=%s" % (key, quote(desired[key])))
    for key, val in desired.items():
        if key not in done:
            if val is None:
                raise ValueError("Für den neuen Schlüssel %s fehlt ein Wert" % key)
            out.append("%s=%s" % (key, quote(val)))
    return "\n".join(out).rstrip("\n") + "\n"


def schedule_restart(delay: float = 1.5) -> None:
    """Prozess nach kurzer Verzögerung sauber beenden (SIGTERM) – Docker (``restart: unless-stopped``) startet ihn neu."""
    def go():
        time.sleep(delay)
        os.kill(os.getpid(), signal.SIGTERM)
    threading.Thread(target=go, daemon=True, name="self-restart").start()
