import { test, expect, PW, api, adminToken, createUser, createProject, loginApi, uniq } from '../helpers/api'

test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true })

test('Smartphone: Menü, Aufgabenliste im Projekt, Erledigt-Haken, kein seitliches Überlaufen', async ({ page }) => {
  const admin = await adminToken()
  const name = 'mob' + uniq()
  const uid = await createUser(admin, name)
  const { pid } = await createProject(admin, 'E2E Mobil ' + uniq(), [{ id: uid, name }])
  const tok = await loginApi(name, PW)
  for (const n of ['Erste Aufgabe', 'Zweite Aufgabe']) await api('POST', `/projects/${pid}/tasks`, admin, { name: n, duration: 2 })

  await page.goto('/login')
  await page.locator('input[autocomplete=username]').fill(name)
  await page.locator('input[type=password]').fill(PW)
  await page.locator('button.primary').click()
  await page.waitForURL(/\/$/)
  const overflow = () => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(await overflow()).toBeLessThanOrEqual(1)                                         // Projektliste

  // Menü statt Linkleiste
  await expect(page.locator('header .lnk').first()).toBeHidden()
  await page.getByRole('button', { name: 'Menü' }).click()
  await expect(page.locator('.mmenu')).toBeVisible()
  await page.locator('.mmenu').getByRole('link', { name: /Meine Aufgaben/ }).click()
  await expect(page).toHaveURL(/\/todo/)
  await expect(page.locator('.mmenu')).toHaveCount(0)

  // Projekt: Karten-Liste, Werkzeuge einklappbar, Haken setzt erledigt
  await page.goto(`/project/${pid}`)
  await expect(page.locator('.mtl li')).toHaveCount(2)
  await expect(page.locator('.toolbar')).toBeHidden()
  await page.getByRole('button', { name: /Werkzeuge/ }).click()
  await expect(page.locator('.toolbar')).toBeVisible()
  await page.getByRole('button', { name: /Werkzeuge/ }).click()
  await page.locator('.mtl li', { hasText: 'Erste Aufgabe' }).locator('.chk').click()
  await expect(page.locator('.mtl li', { hasText: 'Erste Aufgabe' }).locator('.chk')).toHaveClass(/on/)
  await page.locator('.mtl li .main', { hasText: 'Zweite Aufgabe' }).click()
  await expect(page.locator('.modal')).toBeVisible()                                        // Details öffnen
  expect(await overflow()).toBeLessThanOrEqual(1)
  await page.getByRole('button', { name: 'Abbrechen' }).click()
  await page.getByRole('button', { name: 'Zeitachse' }).click()
  await expect(page.locator('.split')).toBeVisible()
  await api('DELETE', `/projects/${pid}`, admin)
})
