import { test, expect, PW, api, adminToken, createUser, loginApi, uniq } from '../helpers/api'
import type { Page } from '@playwright/test'

async function login(page: Page, name: string) {
  await page.goto('/login')
  await page.locator('input[autocomplete=username]').fill(name)
  await page.locator('input[type=password]').fill(PW)
  await page.locator('button.primary').click()
  await page.waitForURL(/\/$/)
}

test('Person per Suche zuordnen → Mitarbeiter-Zugriff, eigene Vorgänge bearbeiten, Betrachter sieht alles', async ({ browser }) => {
  const admin = await adminToken()
  const s = uniq()
  const ownerName = 'own' + s, workerName = 'wrk' + s, viewName = 'vw' + s
  const ownerId = await createUser(admin, ownerName)
  await createUser(admin, workerName)
  const viewId = await createUser(admin, viewName, { role: 'viewer' })
  await api('PUT', `/users/${viewId}/see-all`, admin, { see_all: true })
  const ot = await loginApi(ownerName, PW)
  const pid = (await api('POST', '/projects', ot, { name: 'E2E Zugriff ' + s, start_date: '2026-10-12' })).project.id
  for (const n of ['Planung', 'Eigene Aufgabe']) await api('POST', `/projects/${pid}/tasks`, ot, { name: n, duration: 2 })

  // Verantwortlicher ordnet per Suche zu
  const o = await (await browser.newContext()).newPage()
  await login(o, ownerName)
  await o.goto(`/project/${pid}`)
  await o.locator('.trow', { hasText: 'Eigene Aufgabe' }).locator('.c').nth(1).click()          // Zeile markieren
  await o.getByRole('button', { name: 'Details' }).click()
  await o.getByPlaceholder(/Benutzer suchen/).fill(workerName.slice(0, 5))
  await o.getByRole('button', { name: '+ ' + workerName }).click()
  await o.getByRole('button', { name: 'Speichern', exact: true }).click()
  await expect(o.locator('.modal')).toHaveCount(0)

  // Mitarbeiter: sieht Projekt und Liste, darf Status setzen, aber nicht planen
  const w = await (await browser.newContext()).newPage()
  await login(w, workerName)
  await expect(w.locator('.card', { hasText: 'E2E Zugriff ' + s })).toBeVisible()
  await w.getByRole('link', { name: /Meine Aufgaben/ }).click()
  await expect(w.locator('.todo li', { hasText: 'Eigene Aufgabe' })).toBeVisible()
  await w.goto(`/project/${pid}`)
  await expect(w.locator('.rolechip')).toBeVisible()
  await expect(w.getByRole('button', { name: /\+ Vorgang/ })).toHaveCount(0)
  const own = w.locator('.trow', { hasText: 'Eigene Aufgabe' })
  await own.locator('select.stsel').selectOption('in_progress')
  await expect(own.locator('select.stsel')).toHaveValue('in_progress')
  await expect(w.locator('.trow', { hasText: 'Planung' }).locator('select.stsel')).toBeDisabled()          // fremder Vorgang gesperrt

  // Betrachter (alle Projekte) sieht das Projekt lesend
  const v = await (await browser.newContext()).newPage()
  await login(v, viewName)
  await expect(v.locator('.card', { hasText: 'E2E Zugriff ' + s })).toBeVisible()
  await api('DELETE', `/projects/${pid}`, admin)
})

test('Projekteinstellungen: Mitglied per Suche hinzufügen, Verantwortlicher per Suche wechseln', async ({ page }) => {
  const admin = await adminToken()
  const s = uniq()
  const ownerName = 'mo' + s, memberName = 'mm' + s, newOwner = 'mn' + s
  await createUser(admin, ownerName)
  await createUser(admin, memberName)
  await createUser(admin, newOwner)
  const ot = await loginApi(ownerName, PW)
  const pid = (await api('POST', '/projects', ot, { name: 'E2E Suche ' + s, start_date: '2026-10-12' })).project.id

  await login(page, ownerName)
  await page.goto(`/project/${pid}`)
  await page.getByRole('button', { name: 'Einstellungen' }).click()
  await page.getByPlaceholder(/Mitglied hinzufügen/).fill('mm' + s)
  await page.locator('.hits button', { hasText: memberName }).click()
  await expect(page.locator('.mrow', { hasText: memberName })).toBeVisible()
  await page.getByRole('button', { name: 'Speichern', exact: true }).click()
  await expect(page.locator('.modal')).toHaveCount(0)
  const d = await api('GET', `/projects/${pid}`, ot)
  expect(d.members.map((m: any) => m.username)).toContain(memberName)

  // Verantwortung per Suche übertragen
  await page.getByRole('button', { name: 'Einstellungen' }).click()
  await page.getByPlaceholder(/Anderen Verantwortlichen/).fill('mn' + s)
  await page.locator('.hits button', { hasText: newOwner }).click()
  await expect(page.locator('.curowner')).toContainText(newOwner)
  page.once('dialog', dlg => dlg.accept())
  await page.getByRole('button', { name: 'Speichern', exact: true }).click()
  await page.waitForURL(/\/$/)
  expect((await api('GET', `/projects/${pid}`, admin)).project.owner.username).toBe(newOwner)
  await api('DELETE', `/projects/${pid}`, admin)
})
