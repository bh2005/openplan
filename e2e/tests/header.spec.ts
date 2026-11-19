import { test, expect, api, adminToken, createUser, loginUi, ADMIN, PW, uniq } from '../helpers/api'

test('Kopfleiste: Untermenü „Übersicht“ öffnet Dashboard, Wer arbeitet woran, Organigramm', async ({ page }) => {
  await loginUi(page, ADMIN.username, ADMIN.password)
  const menu = page.locator('.ddmenu')
  await expect(menu).toHaveCount(0)
  await page.getByRole('button', { name: /Übersicht/ }).click()
  await expect(menu.getByRole('menuitem')).toHaveText(['Dashboard', 'Wer arbeitet woran', 'Organigramm'])
  await menu.getByRole('menuitem', { name: 'Organigramm' }).click()
  await expect(page).toHaveURL(/\/org/)
  await expect(menu).toHaveCount(0)                                                          // schließt nach Auswahl
  await page.getByRole('button', { name: /Übersicht/ }).click()
  await page.keyboard.press('Escape')
  await expect(menu).toHaveCount(0)
})

test('Sitzung beenden: Benutzer wird abgemeldet; Passwortwechsel beendet andere Sitzungen', async ({ browser }) => {
  const admin = await adminToken()
  const name = 'ses' + uniq()
  const id = await createUser(admin, name)
  const ctx = await browser.newContext()
  const page = await ctx.newPage()
  await loginUi(page, name, PW)
  await expect(page.locator('.who')).toContainText(name)
  await api('POST', `/users/${id}/logout`, admin)
  await page.reload()
  await expect(page).toHaveURL(/\/login/)
  await loginUi(page, name, PW)                                                              // Neuanmeldung klappt
  await expect(page.locator('.who')).toContainText(name)
  await api('PUT', `/users/${id}/password`, admin, { new_password: 'anderes-passwort-9' })
  await page.reload()
  await expect(page).toHaveURL(/\/login/)
})

test('Organigramm auf dem Handy: kein seitliches Überlaufen der Seite', async ({ browser }) => {
  const admin = await adminToken()
  const pid = (await api('POST', '/projects', admin, { name: 'E2E Org Handy ' + uniq() + ' mit einem ziemlich langen Namen', start_date: '2026-10-12' })).project.id as number
  const first = (await api('POST', `/projects/${pid}/resources`, admin, { name: 'Lead', funktion: 'Projektleiter' })).resources[0].id
  for (let i = 1; i <= 4; i++) await api('POST', `/projects/${pid}/resources`, admin, { name: 'Mitarbeiter ' + i, funktion: 'Technik', reports_to: first })
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true })
  const page = await ctx.newPage()
  await loginUi(page, ADMIN.username, ADMIN.password, `/org?p=${pid}`)
  await expect(page.locator('.sheet svg')).toBeVisible()
  const right = (sel: string) => page.locator(sel).first().evaluate(el => Math.round(el.getBoundingClientRect().right))
  for (const sel of ['.hd select', '.bar', '.sheet']) expect(await right(sel), sel).toBeLessThanOrEqual(390)   // nichts ragt über den Bildschirm (main schneidet sonst unbemerkt ab)
  await expect(page.getByRole('button', { name: 'PNG' })).toBeVisible()
  await expect(page.getByLabel('PDF-Seitenformat')).toBeVisible()
  await expect(page.getByText(/Ziehen:/)).toHaveCount(1)
  await page.screenshot({ path: 'org-mobile.tmp.png', fullPage: true })
})
