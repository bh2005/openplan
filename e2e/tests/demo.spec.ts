import { test, expect, ADMIN, api, adminToken } from '../helpers/api'

test.describe('Beispielprojekte', () => {
  test('Menü legt Server-Migration und Release-Transition an (Deutsch und Englisch)', async ({ page }) => {
    const tok = await adminToken()
    await api('PUT', '/auth/profile', tok, { lang: 'de' })
    await page.goto('/login')
    await page.locator('input[autocomplete=username]').fill(ADMIN.username)
    await page.locator('input[type=password]').fill(ADMIN.password)
    await page.locator('button.primary').click()
    await page.waitForURL(/\/$/)

    await page.getByRole('button', { name: /Beispielprojekt anlegen/ }).click()
    await page.locator('.demo-item', { hasText: 'Server-Migration' }).click()
    await page.waitForURL(/\/project\/\d+/)
    await expect(page.locator('h2').first()).toContainText('Server-Migration')
    const pid1 = Number(page.url().split('/').pop())

    await api('PUT', '/auth/profile', tok, { lang: 'en' })
    await page.goto('/')
    await page.reload()
    await page.getByRole('button', { name: /Create sample project/ }).click()
    await page.locator('.demo-item', { hasText: 'Transition' }).click()
    await page.waitForURL(/\/project\/\d+/)
    await expect(page.locator('h2').first()).toContainText('Transition release change')
    const pid2 = Number(page.url().split('/').pop())

    await api('PUT', '/auth/profile', tok, { lang: 'de' })
    for (const id of [pid1, pid2]) await api('DELETE', `/projects/${id}`, tok)
  })
})
