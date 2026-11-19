import { test, expect, ADMIN, adminToken, api, addTask, createProject, createUser, newSession, tab, uniq } from '../helpers/api'

async function asAdmin(page: import('@playwright/test').Page, target: string) {
  await page.goto('/login')
  await page.locator('input[autocomplete=username]').fill(ADMIN.username)
  await page.locator('input[type=password]').fill(ADMIN.password)
  await page.locator('button.primary').click()
  await page.waitForURL(/\/$/)
  await page.goto(target)
}

test.describe('Planung', () => {
  test('Vorgang anlegen, Rückgängig/Wiederholen per Tastatur, Live-Update in zweiter Sitzung', async ({ page, browser }) => {
    const admin = await adminToken()
    const { pid } = await createProject(admin, 'E2E Undo ' + uniq())
    await addTask(admin, pid, 'Erster')
    await asAdmin(page, `/project/${pid}`)
    const other = await browser.newContext()
    const p2 = await other.newPage()
    await asAdmin(p2, `/project/${pid}`)
    await expect(page.locator('.trow')).toHaveCount(1)

    await page.getByRole('button', { name: '+ Vorgang' }).click()
    await expect(page.locator('.trow')).toHaveCount(2)
    await expect(p2.locator('.trow')).toHaveCount(2, { timeout: 6000 })          // SSE statt 8-s-Polling
    await expect(page.locator('button[title^="Rückgängig"]')).toBeEnabled()

    await page.locator('body').click({ position: { x: 5, y: 5 } })
    await page.keyboard.press('Control+z')
    await expect(page.locator('.trow')).toHaveCount(1)
    await expect(p2.locator('.trow')).toHaveCount(1, { timeout: 6000 })
    await page.keyboard.press('Control+y')
    await expect(page.locator('.trow')).toHaveCount(2)
    await other.close()
  })

  test('Arbeitspaket: im Pool anlegen, Mitglied übernimmt und gibt zurück', async ({ page, browser }) => {
    const admin = await adminToken()
    const mem = 'e2e_pk_' + uniq()
    const id = await createUser(admin, mem)
    const { pid } = await createProject(admin, 'E2E Pakete ' + uniq(), [{ id, name: mem }])
    await asAdmin(page, `/project/${pid}`)
    await tab(page, 'Pakete').click()
    await page.locator('.pk .new input').first().fill('Switch-Konfiguration')
    await page.getByRole('button', { name: 'Anlegen' }).click()
    await expect(page.locator('.pk table').first()).toContainText('Switch-Konfiguration')

    const { context, page: mp } = await newSession(browser, mem, undefined, `/project/${pid}`)
    await tab(mp, 'Pakete').click()
    await expect(mp.locator('.pk table').first()).toContainText('Switch-Konfiguration')
    await mp.getByRole('button', { name: 'Übernehmen' }).click()
    await expect(mp.getByRole('heading', { name: /Von mir übernommen/ })).toContainText('1')
    mp.once('dialog', d => d.accept())                                  // Rückfrage bestätigen
    await mp.getByRole('button', { name: 'Zurückgeben' }).click()
    await expect(mp.getByRole('heading', { name: /Offen im Pool/ })).toContainText('1')
    await context.close()
  })

  test('Arbeitspaket mit Erledigungszeitraum: Anzeige, Fristwarnung, von > bis gesperrt', async ({ page }) => {
    const admin = await adminToken()
    const { pid } = await createProject(admin, 'E2E Zeitraum ' + uniq())
    await asAdmin(page, `/project/${pid}`)
    await tab(page, 'Pakete').click()
    const name = page.locator('.pk .new input').first()
    // 3 Arbeitstage ab Montag 02.11.2026 enden am 04.11. -> passt in den Zeitraum
    await name.fill('Im Zeitraum')
    await page.locator('.pk .new .dur').fill('3')
    await page.locator('.pk .new input[type=date]').nth(0).fill('2026-11-02')
    await page.locator('.pk .new input[type=date]').nth(1).fill('2026-11-04')
    await page.getByRole('button', { name: 'Anlegen', exact: true }).click()
    const row = page.locator('.pk table').first().locator('tbody tr', { hasText: 'Im Zeitraum' })
    await expect(row).toContainText('02.11.26 – 04.11.26')
    await expect(row).not.toContainText('⚠')
    // 10 Arbeitstage passen nicht -> Frist überschritten (⚠)
    await name.fill('Zu lang')
    await page.locator('.pk .new .dur').fill('10')
    await page.locator('.pk .new input[type=date]').nth(0).fill('2026-11-02')
    await page.locator('.pk .new input[type=date]').nth(1).fill('2026-11-04')
    await page.getByRole('button', { name: 'Anlegen', exact: true }).click()
    await expect(page.locator('.pk table').first().locator('tbody tr', { hasText: 'Zu lang' })).toContainText('⚠')
    // von nach bis: Hinweis, Button gesperrt
    await name.fill('Falsch herum')
    await page.locator('.pk .new input[type=date]').nth(0).fill('2026-11-10')
    await page.locator('.pk .new input[type=date]').nth(1).fill('2026-11-03')
    await expect(page.getByText('„von“ liegt nach „bis“')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Anlegen', exact: true })).toBeDisabled()
    // im Gantt trägt der zu lange Vorgang das Warnzeichen
    await tab(page, 'Gantt').click()
    await expect(page.locator('.trow', { hasText: 'Zu lang' }).locator('.dlmiss')).toBeVisible()
    await expect(page.locator('.trow', { hasText: 'Im Zeitraum' }).locator('.dlmiss')).toHaveCount(0)
  })

  test('Kommentar mit @-Erwähnung: Vorschlag, Benachrichtigung, Hervorhebung', async ({ page, browser }) => {
    const admin = await adminToken()
    const anna = 'e2e_cm_' + uniq()
    const id = await createUser(admin, anna)
    const { pid } = await createProject(admin, 'E2E Kommentar ' + uniq(), [{ id, name: anna }])
    const tid = await addTask(admin, pid, 'Besprechungs-Vorgang')
    await asAdmin(page, `/project/${pid}?task=${tid}`)
    const box = page.locator('.cm textarea')
    await box.fill('Bitte prüfen @' + anna.slice(0, 7))
    await page.locator('.sug button', { hasText: '@' + anna }).click()
    await expect(box).toHaveValue(new RegExp('@' + anna + ' $'))
    await box.type('– danke!')
    await page.getByRole('button', { name: 'Kommentieren' }).click()
    await expect(page.locator('.cm .list li').first()).toContainText('danke')
    await expect(page.locator('.cm .men').first()).toHaveText('@' + anna)

    const { context, page: ap } = await newSession(browser, anna)
    await ap.locator('.bellbtn').click()
    await expect(ap.locator('.item').first()).toContainText('hat dich erwähnt: Besprechungs-Vorgang')
    await ap.locator('.item').first().click()
    await expect(ap.locator('.cm .list li').first()).toContainText('Bitte prüfen')
    await context.close()
  })

  test('Kalender auf dem Handy: kein seitliches Überlaufen, Liste zeigt Status', async ({ browser }) => {
    const admin = await adminToken()
    const { pid } = await createProject(admin, 'E2E Mobil ' + uniq())
    await addTask(admin, pid, 'Mobiler Vorgang')
    const ctx = await browser.newContext({ viewport: { width: 390, height: 780 }, isMobile: true, hasTouch: true })
    const page = await ctx.newPage()
    await asAdmin(page, `/project/${pid}`)
    await tab(page, 'Kalender').click()
    for (const v of ['Monat', 'Woche', 'Liste']) {
      await page.locator('.seg button', { hasText: v }).click()
      const w = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }))
      expect(w.sw, `Ansicht ${v}`).toBeLessThanOrEqual(w.cw)
    }
    await expect(page.locator('.dt')).toContainText('Mobiler Vorgang')
    await ctx.close()
  })
})
