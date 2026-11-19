import { defineConfig } from '@playwright/test'

// Standard: Dev-Stack (docker compose -f docker-compose.dev.yml up -d) → http://localhost:5173, Login admin / openplan-dev-1.
// Anderes Ziel:   E2E_BASE_URL=http://localhost:8083 E2E_ADMIN_PASSWORD=… npm test
// Browser:        PW_CHANNEL=msedge (Standard, vorinstalliert) | chrome | chromium (dann einmalig `npx playwright install chromium`)
const channel = process.env.PW_CHANNEL ?? 'msedge'

export default defineConfig({
  testDir: './tests',
  timeout: 45_000,
  expect: { timeout: 8_000 },
  fullyParallel: false,
  workers: 1,                        // Tests legen eigene Daten an, teilen sich aber die Instanz
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    channel: channel === 'chromium' ? undefined : channel,
    headless: !process.env.HEADED,
    locale: 'de-DE',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
})
