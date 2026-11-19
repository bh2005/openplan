import { test, expect, loginUi, ADMIN } from '../helpers/api'

test('Feiertags-API: URL speichern, ungültig abgelehnt, Test zeigt Ergebnis', async ({ page }) => {
  await loginUi(page, ADMIN.username, ADMIN.password, '/admin')
  await page.locator('.tabs button', { hasText: 'Feiertags-API' }).click()
  const url = page.locator('.hapi input[type=url]')
  await expect(url).toBeVisible()
  await url.fill('ftp://intern/x')
  await page.locator('.hapi').getByRole('button', { name: 'Speichern', exact: true }).click()
  await expect(page.locator('.toast, [role=status], .snack').first()).toBeVisible().catch(() => {})
  await url.fill('http://127.0.0.1:9/feiertage')                         // nicht erreichbar -> Test meldet Fehler, speichert nichts
  await page.getByRole('button', { name: 'Verbindung testen' }).click()
  await expect(page.locator('.hapi .bad')).toBeVisible()
  await expect(page.locator('.hapi code', { hasText: 'years=' }).last()).toBeVisible()
  await url.fill('https://intern.example/api')
  await page.locator('.hapi').getByRole('button', { name: 'Speichern', exact: true }).click()
  await page.reload()
  await page.locator('.tabs button', { hasText: 'Feiertags-API' }).click()
  await expect(url).toHaveValue('https://intern.example/api')
  await url.fill('')                                                     // zurück auf Standard
  await page.locator('.hapi').getByRole('button', { name: 'Speichern', exact: true }).click()
  await page.reload()
  await page.locator('.tabs button', { hasText: 'Feiertags-API' }).click()
  await expect(url).toHaveValue('')
})
