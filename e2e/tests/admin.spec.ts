import { test, expect, ADMIN, uniq } from '../helpers/api'

test.describe('Verwaltung', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.locator('input[autocomplete=username]').fill(ADMIN.username)
    await page.locator('input[type=password]').fill(ADMIN.password)
    await page.locator('button.primary').click()
    await page.waitForURL(/\/$/)
    await page.goto('/admin')
  })

  const open = (page: import('@playwright/test').Page, name: string) => page.locator('.tabs button', { hasText: name }).click()

  test('alle Bereiche lassen sich öffnen', async ({ page }) => {
    for (const [tabName, marker] of [['Anmeldung', '.ldap'], ['Benachrichtigung', '.mail'], ['Erinnerungen', '.rem'], ['Reports', '.rep'],
                                     ['Server-Zertifikat', '.tls'], ['Backup', '.bk'], ['Audit-Log', '.aud'], ['Release Notes', '.cl']] as const) {
      await open(page, tabName)
      await expect(page.locator(marker), tabName).toBeVisible()
    }
  })

  test('Datensicherung: erstellen, prüfen, löschen – und im Audit-Log sichtbar', async ({ page }) => {
    await open(page, 'Backup')
    const before = await page.locator('.bk .tbl tbody tr').count().catch(() => 0)
    await page.getByRole('button', { name: 'Jetzt sichern' }).click()
    await expect(page.locator('.bk .tbl tbody tr code').first()).toContainText('openplan-backup-')
    await page.getByRole('button', { name: 'Prüfen' }).first().click()
    await expect(page.locator('.bk .ok').first()).toContainText('Datenbank in Ordnung')
    page.once('dialog', d => d.accept())
    await page.locator('.bk .tbl .danger').first().click()
    await expect.poll(() => page.locator('.bk .tbl tbody tr').count()).toBeLessThanOrEqual(before + 1)
    await open(page, 'Audit-Log')
    await page.locator('.aud input').first().fill('backup')
    await expect(page.locator('.aud tbody')).toContainText('backup.create')
    await expect(page.locator('.aud tbody')).toContainText('backup.delete')
  })

  test('Audit-Log zeigt Anmeldungen inkl. fehlgeschlagener', async ({ page, request }) => {
    const who = 'e2e_nobody_' + uniq()
    await request.post('/api/auth/login', { data: { username: who, password: 'x' } })
    await open(page, 'Audit-Log')
    await page.locator('.aud input').first().fill(who)
    await expect(page.locator('.aud tbody')).toContainText('login.fail')
    await expect(page.locator('.aud tbody tr.bad').first()).toBeVisible()
  })

  test('Erinnerungen: speichern und sofort prüfen', async ({ page }) => {
    await open(page, 'Erinnerungen')
    await page.locator('.rem input[type=number]').nth(1).fill('3')
    await page.locator('.rem').getByRole('button', { name: 'Speichern' }).click()
    await expect(page.getByText('Gespeichert')).toBeVisible()
    await page.getByRole('button', { name: 'Jetzt prüfen' }).click()
    await expect(page.locator('.rem .okmsg')).toContainText('Neue Meldungen')
  })
})
