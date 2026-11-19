import { test, expect, adminToken, api, createProject, loginUi, uniq, ADMIN } from '../helpers/api'

test('Feiertage: Bundesland wählen, laden, speichern; eigene Tage bleiben', async ({ page }) => {
  const admin = await adminToken()
  const { pid } = await createProject(admin, 'E2E Feiertage ' + uniq())
  await loginUi(page, ADMIN.username, ADMIN.password, `/project/${pid}`)
  await page.getByRole('button', { name: 'Einstellungen' }).click()
  const hol = page.locator('label', { hasText: 'Feiertage / freie Tage' }).locator('textarea')
  await hol.fill('24.12.2026')                                            // eigener freier Tag
  await expect(page.getByRole('button', { name: 'Feiertage laden' })).toBeDisabled()      // ohne Bundesland
  await page.locator('.hl select').selectOption('nw')
  await page.getByRole('button', { name: 'Feiertage laden' }).click()
  await expect(hol).toHaveValue(/24\.12\.2026/)
  await expect(hol).toHaveValue(/04\.06\.2026/)                           // Fronleichnam (NRW)
  await expect(hol).toHaveValue(/01\.11\.2026/)                           // Allerheiligen (NRW)
  await page.getByRole('button', { name: 'Speichern', exact: true }).click()
  await expect(page.locator('.modal')).toHaveCount(0)
  const p = (await api('GET', `/projects/${pid}`, admin)).project
  expect(p.holiday_state).toBe('nw')
  expect(p.holidays).toEqual(expect.arrayContaining(['2026-12-24', '2026-06-04', '2026-12-25']))
  await api('DELETE', `/projects/${pid}`, admin)
})
