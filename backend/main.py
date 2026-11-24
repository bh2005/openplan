import logging
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

import acme_client
import apidocs
import apitokens
import backup
import reminders
import refs
import integrations
import webhooks
import reports
from api import router
from comments_api import router as comments_router
from devices import router as devices_router
from dashboard import router as dashboard_router
from envadmin import router as envadmin_router
from feiertage import router as holidays_router
from leveling import router as leveling_router
from overview import router as overview_router
from user_absences import org_router as all_absences_router, router as user_absences_router
from files_api import router as files_router
from finance_api import router as finance_router
from config import FRONTEND_DIST
from database import init_db

logging.basicConfig(level=logging.INFO)
VERSION = (FRONTEND_DIST.parent.parent / "VERSION")


_init_lock = threading.Lock()
_inited = False


@asynccontextmanager
async def lifespan(_app):
    with _init_lock:                      # mehrere Listener (HTTP + TLS) teilen sich einen Prozess
        global _inited
        if not _inited:
            init_db()
            _inited = True
    acme_client.start_background()
    reports.start_background()
    backup.start_background()
    reminders.start_background()
    webhooks.start_background()
    yield


app = FastAPI(title="OpenPlan", version="0.14.0", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)   # Dokumentation: apidocs.py (lokal, API_DOCS)

# HTTP -> HTTPS: nur wenn FORCE_HTTPS=1 UND der HTTPS-Listener tatsächlich läuft (Marker data/tls/serving). So sperrt man sich nie aus,
# solange noch kein Zertifikat existiert. Ausgenommen: ACME-HTTP-01 und der Health-Check (Docker/Monitoring).
FORCE_HTTPS = os.environ.get("FORCE_HTTPS", "").lower() in ("1", "true", "yes")
PUBLIC_HTTPS_PORT = os.environ.get("PUBLIC_HTTPS_PORT", "443")
HTTP_EXEMPT = ("/.well-known/acme-challenge/", "/health")


def _host(h: str) -> str:
    """Host-Header ohne Port (IPv6-Literale bleiben in Klammern)."""
    if h.startswith("["):
        return h.split("]")[0] + "]"
    return h.rsplit(":", 1)[0] if ":" in h else h


@app.middleware("http")
async def https_redirect(request, call_next):
    if (FORCE_HTTPS and request.url.scheme == "http" and not request.url.path.startswith(HTTP_EXEMPT)
            and acme_client.TLS_DIR.joinpath("serving").exists()):
        host = _host(request.headers.get("host") or "")
        if host:
            port = "" if PUBLIC_HTTPS_PORT == "443" else ":" + PUBLIC_HTTPS_PORT
            return RedirectResponse("https://%s%s%s%s" % (host, port, request.url.path, "?" + request.url.query if request.url.query else ""), status_code=308)
    return await call_next(request)

app.include_router(router)
app.include_router(finance_router)
app.include_router(files_router)
app.include_router(comments_router)
app.include_router(devices_router)
app.include_router(holidays_router)
app.include_router(envadmin_router)
app.include_router(dashboard_router)
app.include_router(leveling_router)
app.include_router(overview_router)
app.include_router(user_absences_router)
app.include_router(all_absences_router)
app.include_router(apitokens.router)
app.include_router(refs.router)
app.include_router(webhooks.router)
app.include_router(integrations.router)
app.include_router(apidocs.router)


@app.get("/.well-known/acme-challenge/{token}", include_in_schema=False)
def acme_challenge(token: str):
    """HTTP-01-Validierung der CA (öffentlich, nur aktive Tokens)."""
    from fastapi.responses import PlainTextResponse
    ka = acme_client.CHALLENGES.get(token)
    if not ka:
        raise HTTPException(404)
    return PlainTextResponse(ka)


@app.get("/health")
def health():
    return {"status": "ok"}


# PWA/SPA: statische Dateien aus dem Frontend-Build, Fallback auf index.html
@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith("api/"):
        raise HTTPException(404)
    root = FRONTEND_DIST.resolve()
    f = (root / path).resolve()
    if path and f.is_file() and root in f.parents:
        return FileResponse(f)
    index = root / "index.html"
    if index.is_file():
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    raise HTTPException(404, "Frontend nicht gebaut")
