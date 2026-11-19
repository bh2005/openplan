import { test, expect, api, adminToken, createUser, loginUi, ADMIN, uniq } from '../helpers/api'

test('Organigramm: Funktion + „Berichtet an“, Extern gestrichelt, viele Blätter als Liste, Export, eigene Seite', async ({ page }) => {
  const admin = await adminToken()
  const s = uniq()
  const uid = await createUser(admin, 'org' + s)
  await api('POST', '/users', admin, { username: 'orgdn' + s, display_name: 'Müller, Anna', password: 'e2e-passwort-1', role: 'editor' })
  const pid = (await api('POST', '/projects', admin, { name: 'E2E Org ' + s + ' – Netzwerk-Rollout Cisco nach Extreme mit sehr langem Projektnamen', start_date: '2026-10-12' })).project.id as number
  const mk = async (body: Record<string, unknown>) => {
    const d = await api('POST', `/projects/${pid}/resources`, admin, body)
    return Math.max(...d.resources.map((r: any) => r.id)) as number
  }
  const lead = await mk({ name: 'Teilprojektleiter Süd', funktion: 'Teilprojektleiter', user_id: uid })
  const tech = await mk({ name: 'Netzwerk-Lead', funktion: 'Netzwerk-Lead', reports_to: lead })
  const ext = await mk({ name: 'Externer Dienstleister', funktion: 'Berater' })
  const techs: number[] = []
  for (let i = 1; i <= 8; i++) techs.push(await mk({ name: 'Techniker ' + i, funktion: 'Netzwerktechniker', reports_to: tech }))

  await loginUi(page, ADMIN.username, ADMIN.password, `/project/${pid}`)
  await page.getByRole('button', { name: 'Organigramm', exact: true }).click()
  const svg = page.locator('.sheet svg')
  await expect(svg).toBeVisible()
  await expect(svg.locator('text[font-size="18"]')).not.toHaveCount(1)                       // langer Titel wird umgebrochen statt abgeschnitten
  await expect(svg.locator('text', { hasText: 'Teilprojektleiter Süd' })).toBeVisible()
  await expect(svg.locator('text', { hasText: 'Techniker 8' })).toBeVisible()                  // Liste unter dem Netzwerk-Lead
  await expect(svg.locator('rect[stroke-dasharray]')).toHaveCount(10)                         // alle ohne Benutzerkonto gestrichelt, der verknüpfte Teilprojektleiter nicht
  await page.screenshot({ path: 'org.tmp.png', fullPage: true })

  // Umhängen per Ziehen: Techniker 1 → Externer Dienstleister; Zirkel (Teilprojektleiter unter Techniker) wird nicht angeboten
  const box = async (id: number) => (await page.locator(`g[data-key="r${id}"]`).boundingBox())!
  const from = await box(techs[0]), to = await box(ext)
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2)
  await page.mouse.down()
  await page.mouse.move(to.x + to.width / 2, to.y + to.height / 2, { steps: 8 })
  await expect(page.locator('g.drop-ok')).toHaveCount(1)
  await page.mouse.up()
  await expect.poll(async () => (await api('GET', `/projects/${pid}`, admin)).resources.find((r: any) => r.id === techs[0]).reports_to).toBe(ext)
  const lb = await box(lead), tb = await box(techs[1])
  await page.mouse.move(lb.x + lb.width / 2, lb.y + lb.height / 2)
  await page.mouse.down()
  await page.mouse.move(tb.x + tb.width / 2, tb.y + tb.height / 2, { steps: 8 })
  await expect(page.locator('g.drop-ok')).toHaveCount(0)
  await page.mouse.up()

  // Export als PNG
  await expect(page.getByLabel('PDF-Seitenformat')).toHaveValue('auto')
  const dl = page.waitForEvent('download')
  await page.getByRole('button', { name: 'PNG' }).click()
  expect((await dl).suggestedFilename()).toMatch(/\.png$/)

  // Spalte „Berichtet an“ im Tab Ressourcen: Zirkel wird abgewiesen
  await page.getByRole('button', { name: 'Ressourcen', exact: true }).click()
  await expect(page.locator('.tbl tbody tr', { hasText: 'Netzwerk-Lead' }).first()).toContainText('Teilprojektleiter Süd')
  const res = await api('PUT', `/resources/${lead}`, admin, { name: 'Teilprojektleiter Süd', max_units: 100, reports_to: tech }).catch(e => String(e))
  expect(String(res)).toContain('422')

  // Eigene Seite für Vorgesetzte
  await page.goto(`/org?p=${pid}`)
  await expect(page.locator('.sheet svg text', { hasText: 'Netzwerk-Lead' }).first()).toBeVisible()
})
