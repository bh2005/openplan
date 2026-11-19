# OpenPlan – Browser-Tests (Playwright)

Ende-zu-Ende-Tests gegen eine **laufende** Instanz. Sie legen ihre Testdaten selbst über die API an (eindeutige Namen `e2e_…`) und prüfen
dann an der Oberfläche: Anmeldung, Zuteilung → Glocke → Link, Teamplaner (Layout, Scroll-Sync, Umplanen per Ziehen), Undo/Redo + Live-Update,
Arbeitspakete, Kommentare mit @-Erwähnung, Kalender auf dem Handy, Verwaltung (Backup, Audit-Log, Erinnerungen).

```bash
docker compose -f docker-compose.dev.yml up -d      # Dev-Stack: http://localhost:5173 (admin / openplan-dev-1)
cd e2e
npm install
npm test                                            # alle Tests, Edge ohne Browser-Download
npm run test:headed                                 # mit sichtbarem Browser (oder HEADED=1)
npx playwright test -g "Kommentar"                  # einzelne Tests
npm run report                                      # HTML-Bericht (e2e/playwright-report)
```

| Variable | Bedeutung | Standard |
|---|---|---|
| `E2E_BASE_URL` | Ziel (z. B. Prod-Test `http://localhost:8083`) | `http://localhost:5173` |
| `E2E_ADMIN_USER` / `E2E_ADMIN_PASSWORD` | Admin-Zugang für das Anlegen der Testdaten | `admin` / `openplan-dev-1` |
| `PW_CHANNEL` | `msedge` · `chrome` · `chromium` (dann einmalig `npx playwright install chromium`) | `msedge` |

Hinweise: Die Tests hinterlassen Benutzer/Projekte mit Präfix `e2e_`/`E2E …` – nur gegen Test- oder Dev-Instanzen laufen lassen.
`workers: 1`, weil sich alle Tests eine Instanz teilen.
