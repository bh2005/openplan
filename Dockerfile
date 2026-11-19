# ── Stage 1: Frontend ────────────────────────────────────────────────────────
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
# Optionale interne CA (TLS-Inspection-Proxy), siehe certs/README.md
COPY certs/ /certs/
RUN cat /certs/*.crt > /certs/bundle.pem 2>/dev/null || true
ENV NODE_EXTRA_CA_CERTS=/certs/bundle.pem
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Backend (Runtime) ───────────────────────────────────────────────
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
COPY certs/ /tmp/certs/
RUN cp /tmp/certs/*.crt /usr/local/share/ca-certificates/ 2>/dev/null; update-ca-certificates; rm -rf /tmp/certs
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    PIP_CERT=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ ./backend/
COPY VERSION ./
COPY --from=frontend /app/frontend/dist ./frontend/dist

RUN useradd -r -u 10001 openplan && mkdir -p /app/data && chown openplan /app/data
USER openplan
ENV DATA_DIR=/app/data FRONTEND_DIST=/app/frontend/dist PYTHONUNBUFFERED=1
WORKDIR /app/backend
EXPOSE 8080
# HTTP :8080 (+ optional HTTPS auf TLS_PORT mit dem ACME-Zertifikat)
CMD ["python", "serve.py"]
