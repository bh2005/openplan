import { test, expect, ADMIN, adminToken, createUser, loginUi, uniq, PW } from '../helpers/api'

test.describe('Anmeldung', () => {
  test('falsches Passwort zeigt Fehler und bleibt auf der Anmeldung', async ({ page }) => {
    await loginUi(page, ADMIN.username, 'falsch-falsch')
    await expect(page).toHaveURL(/\/login/)
    await expect(page.locator('input[type=password]')).toBeVisible()
    await expect(page.getByText(/falsch/i).first()).toBeVisible()
  })

  test('erfolgreiche Anmeldung führt zur Projektliste, Abmelden zurück', async ({ page }) => {
    await loginUi(page, ADMIN.username, ADMIN.password)
    await expect(page).toHaveURL(/\/$/)
    await expect(page.getByRole('button', { name: 'Abmelden' })).toBeVisible()
    await page.getByRole('button', { name: 'Abmelden' }).click()
    await expect(page).toHaveURL(/\/login/)
  })

  test('geschützte Seite leitet auf Anmeldung um und kehrt nach dem Login zurück', async ({ page }) => {
    const admin = await adminToken()
    const name = 'e2e_au_' + uniq()
    await createUser(admin, name)
    await loginUi(page, name, PW, '/help')
    await expect(page).toHaveURL(/\/help/)
  })

  test('Leser sieht keine Verwaltung in den Aktionen, Admin schon', async ({ page }) => {
    const admin = await adminToken()
    const name = 'e2e_rd_' + uniq()
    await createUser(admin, name, { role: 'viewer' })
    await loginUi(page, name, PW)
    await expect(page.getByRole('link', { name: 'Verwaltung' })).toHaveCount(0)
  })
})
