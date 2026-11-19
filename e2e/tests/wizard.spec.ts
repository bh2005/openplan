import { test, expect, PW, api, adminToken, createUser, uniq } from '../helpers/api'

test('Assistent „Neues Projekt“: Projektart, Grunddaten, Team, Bericht, Anlegen', async ({ page }) => {
  const admin = await adminToken()
  const s = uniq()
  const ownerName = 'wo' + s, memberName = 'wm' + s
  await createUser(admin, ownerName)
  await createUser(admin, memberName)

  await page.goto('/login')
  await page.locator('input[autocomplete=username]').fill(ownerName)
  await page.locator('input[type=password]').fill(PW)
  await page.locator('button.primary').click()
  await page.waitForURL(/\/$/)

  await page.getByRole('button', { name: '+ Neues Projekt' }).click()
  await expect(page.locator('.wiz')).toBeVisible()
  await page.locator('.kind', { hasText: 'Server-Migration' }).click()
  await page.getByRole('button', { name: 'Weiter' }).click()

  // Schritt 2: Pflichtangaben werden geprüft
  await page.getByRole('button', { name: 'Weiter' }).click()
  await expect(page.locator('.toast')).toContainText('Projektnamen')
  const name = 'E2E Assistent ' + s
  await page.locator('.wiz input').first().fill(name)
  await page.getByRole('button', { name: 'Weiter' }).click()

  // Schritt 3: Mitglied per Suche
  await page.getByPlaceholder(/Mitglied hinzufügen/).fill('wm' + s)
  await page.locator('.hits button', { hasText: memberName }).click()
  await expect(page.locator('.mrow', { hasText: memberName })).toBeVisible()
  await page.getByRole('button', { name: 'Weiter' }).click()

  // Schritt 4: Bericht
  await page.getByLabel(/Projektreport automatisch/).check()
  await page.getByRole('button', { name: 'Weiter' }).click()

  // Schritt 5: Zusammenfassung → anlegen
  await expect(page.locator('.sum')).toContainText(name)
  await expect(page.locator('.sum')).toContainText(memberName)
  await page.getByRole('button', { name: 'Projekt anlegen', exact: true }).click()
  await page.waitForURL(/\/project\/\d+/)
  const pid = Number(page.url().split('/').pop())
  const d = await api('GET', `/projects/${pid}`, admin)
  expect(d.project.name).toBe(name)
  expect(d.project.report_enabled).toBe(1)
  expect(d.members.map((m: any) => m.username)).toContain(memberName)
  expect(d.tasks.length).toBeGreaterThan(40)
  await expect(page.locator('h2', { hasText: name })).toBeVisible()
  await api('DELETE', `/projects/${pid}`, admin)
})
