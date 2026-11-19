"""Startskript: Klartext-Port (Standard 8080) plus optionaler TLS-Port mit dem per ACME ausgestellten Zertifikat.

* ``HTTP_PORT`` (Standard 8080): immer aktiv – Healthcheck, ACME-HTTP-01 und Betrieb hinter einem Reverse-Proxy.
* ``TLS_PORT`` (z. B. 8443): startet zusätzlich einen HTTPS-Listener, sobald ``DATA_DIR/tls/fullchain.pem`` und ``privkey.pem``
  existieren. Wird das Zertifikat erneuert, lädt der Listener es innerhalb einer Minute ohne Neustart des Containers neu.
"""
from __future__ import annotations

import contextlib
import logging
import os
import threading

import uvicorn

import acme_client
from main import app

log = logging.getLogger("openplan.serve")


class _ThreadServer(uvicorn.Server):
    @contextlib.contextmanager
    def capture_signals(self):          # Signale (SIGTERM) behandelt allein der Hauptserver
        yield


def _stamp():
    try:
        return (acme_client.CERT_FILE.stat().st_mtime_ns, acme_client.KEY_FILE.stat().st_mtime_ns)
    except OSError:
        return None


def tls_manager(host: str, port: int, stop: threading.Event) -> None:
    marker = acme_client.TLS_DIR / "serving"
    marker.unlink(missing_ok=True)
    server, thread, loaded = None, None, None
    while not stop.is_set():
        stamp = _stamp()
        if stamp != loaded or (thread is not None and not thread.is_alive()):
            if server is not None:
                server.should_exit = True
                thread.join(15)
                marker.unlink(missing_ok=True)
                server = thread = None
            loaded = stamp
            if stamp:
                try:
                    cfg = uvicorn.Config(app, host=host, port=port, ssl_certfile=str(acme_client.CERT_FILE),
                                         ssl_keyfile=str(acme_client.KEY_FILE), log_level="info")
                    server = _ThreadServer(cfg)
                    thread = threading.Thread(target=server.run, daemon=True, name="tls-server")
                    thread.start()
                    marker.write_text(str(port))
                    log.info("TLS-Listener auf Port %d mit aktuellem Zertifikat gestartet", port)
                except Exception:           # defektes Zertifikat o. Ä.: weiter prüfen, nicht abstürzen
                    log.exception("TLS-Listener konnte nicht gestartet werden")
                    server = thread = None
        stop.wait(float(os.environ.get("TLS_CHECK_SECONDS", "30")))
    if server is not None:
        server.should_exit = True
        thread.join(10)
    marker.unlink(missing_ok=True)


def main() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    stop = threading.Event()
    tls_port = int(os.environ.get("TLS_PORT", "0") or 0)
    if tls_port:
        threading.Thread(target=tls_manager, args=(host, tls_port, stop), daemon=True, name="tls-manager").start()
    try:
        uvicorn.run(app, host=host, port=int(os.environ.get("HTTP_PORT", "8080")), log_level="info")
    finally:
        stop.set()


if __name__ == "__main__":
    main()
