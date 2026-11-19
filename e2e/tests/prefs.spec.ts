import { test, expect, ADMIN } from '../helpers/api'

test.describe('Sprache und Darstellung', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.locator('input[autocomplete=username]').fill(ADMIN.username)
    await page.locator('input[type=password]').fill(ADMIN.password)
    await page.locator('button.primary').click()
    await page.waitForURL(/\/$/)
  })

  test.afterEach(async ({ page }) => {          // Standard wiederherstellen (Deutsch, automatisch)
    await page.evaluate(async () => {
      const token = localStorage.getItem('openplan.token') ?? ''
      await fetch('/api/auth/profile', { method: 'PUT', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, body: JSON.stringify({ lang: 'de', theme: 'auto' }) })
    })
  })

  test('Sprache umschalten, bleibt nach Neuladen erhalten', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'Abmelden' })).toBeVisible()          // Standard: Deutsch
    await page.locator('button.lng').click()
    await expect(page.getByRole('button', { name: 'Log out' })).toBeVisible()
    await page.reload()
    await expect(page.getByRole('button', { name: 'Log out' })).toBeVisible()
    await page.goto('/admin')
    await expect(page.locator('.tabs button', { hasText: 'Release notes' })).toBeVisible()
  })

  test('Dunkel/Hell erzwingen', async ({ page }) => {
    const theme = () => page.evaluate(() => document.documentElement.getAttribute('data-theme'))
    const btn = page.locator('button.pref:not(.lng)')
    await btn.click(); expect(await theme()).toBe('light')
    await btn.click(); expect(await theme()).toBe('dark')
    await expect(page.locator('body')).toHaveCSS('background-color', 'rgb(15, 20, 25)')
    await page.reload(); expect(await theme()).toBe('dark')
    await btn.click(); expect(await theme()).toBeNull()                                  // zurück auf automatisch
  })
})
