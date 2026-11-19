import { test, expect, loginUi, ADMIN } from '../helpers/api'

// Auf dem Dev-Stack ist ENV_FILE nicht gesetzt -> Bereich meldet „Nicht aktiviert“; gegen Prod (:8083) wird gespeichert und neu gestartet.
test('Server-Umgebung: Tab, Maskierung, Speichern, Neustart', async ({ page, request }) => {
  await loginUi(page, ADMIN.username, ADMIN.password, '/admin')
  await page.locator('.tabs button', { hasText: 'Server-Umgebung' }).click()
  await page.locator('.env .off, .env table').first().waitFor()
  const off = page.locator('.env .off')
  if (await off.count()) {
    await expect(off).toContainText('ENV_FILE')
    return
  }
  const pw = page.locator('.env input[type=password]').first()                    // ADMIN_PASSWORD
  await expect(pw).toHaveValue('')                                              // Geheimnis wird nie angezeigt
  await page.getByRole('button', { name: '+ Variable' }).click()
  const row = page.locator('.env tbody tr').last()
  const name = 'E2E_TEST_' + Math.random().toString(36).slice(2, 7).toUpperCase()
  await row.locator('input').first().fill(name)
  await row.locator('input').nth(1).fill('wert mit $dollar')
  await page.locator('.env').getByRole('button', { name: 'Speichern', exact: true }).click()
  await expect(page.locator('.env .pend')).toBeVisible()
  page.once('dialog', d => d.accept())
  await page.getByRole('button', { name: 'Container neu starten', exact: true }).first().click()
  await expect(page.locator('.overlay')).toBeVisible()
  await page.waitForURL(/\/admin/, { timeout: 120000 })
  await page.waitForLoadState('load')
  await page.locator('.tabs button', { hasText: 'Server-Umgebung' }).click()
  const last = page.locator('.env tbody tr').last()                                // neue Variable steht am Dateiende
  await expect(last.locator('input').first()).toHaveValue(name)
  await expect(last.locator('input').nth(1)).toHaveValue('wert mit $dollar')
  await expect(page.locator('.env .pend')).toHaveCount(0)                        // nach dem Neustart wieder deckungsgleich
  // aufräumen: Variable entfernen und speichern (kein erneuter Neustart nötig)
  await last.locator('button.danger').click()
  await page.locator('.env').getByRole('button', { name: 'Speichern', exact: true }).click()
  await expect(page.locator('.env .pend')).toBeVisible()
  page.once('dialog', d => d.accept())
  await page.getByRole('button', { name: 'Container neu starten', exact: true }).first().click()   // wieder sauberer Stand
  await page.waitForURL(/\/admin/, { timeout: 120000 })
  void request
})
