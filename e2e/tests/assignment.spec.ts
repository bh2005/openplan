import { test, expect, adminToken, api, addTask, createProject, createUser, newSession, PW, uniq } from '../helpers/api'

test.describe('Zuteilung → Benachrichtigung → Link', () => {
  test('Glocke zeigt die Zuteilung, Klick öffnet den Vorgang', async ({ browser }) => {
    const admin = await adminToken()
    const anna = 'e2e_anna_' + uniq()
    const id = await createUser(admin, anna, { email: anna + '@corp.test' })
    const { pid, res } = await createProject(admin, 'E2E Zuteilung ' + uniq(), [{ id, name: anna }])
    const tid = await addTask(admin, pid, 'Firewall-Regeln prüfen')
    await api('PUT', `/tasks/${tid}/assignments`, admin, [{ resource_id: res[anna], units: 100 }])

    const { context, page } = await newSession(browser, anna)
    await expect(page.locator('.bell .cnt')).toHaveText('1')
    await page.locator('.bellbtn').click()
    await expect(page.locator('.item').first()).toContainText('Vorgang zugeteilt: Firewall-Regeln prüfen')
    await page.locator('.item').first().click()
    await expect(page).toHaveURL(new RegExp(`/project/${pid}`))
    await expect(page.locator('.modal input').first()).toHaveValue('Firewall-Regeln prüfen')
    await page.goto('/')
    await expect(page.locator('.bell .cnt')).toHaveCount(0)             // gelesen
    await context.close()
  })

  test('Link aus der E-Mail öffnet nach dem Login direkt den Vorgang', async ({ browser }) => {
    const admin = await adminToken()
    const ben = 'e2e_ben_' + uniq()
    const id = await createUser(admin, ben)
    const { pid } = await createProject(admin, 'E2E Deep-Link ' + uniq(), [{ id, name: ben }])
    const tid = await addTask(admin, pid, 'Direkt-Link-Vorgang')
    const { context, page } = await newSession(browser, ben, PW, `/project/${pid}?task=${tid}`)
    await expect(page.locator('.modal input').first()).toHaveValue('Direkt-Link-Vorgang')
    await context.close()
  })

  test('Teamplaner: Split-Layout, Scroll-Synchronisation und Umplanen per Ziehen', async ({ page }) => {
    const admin = await adminToken()
    const a = 'e2e_ta_' + uniq(), b = 'e2e_tb_' + uniq()
    const ia = await createUser(admin, a), ib = await createUser(admin, b)
    const { pid, res } = await createProject(admin, 'E2E Team ' + uniq(), [{ id: ia, name: a }, { id: ib, name: b }])
    for (let i = 0; i < 12; i++) {
      const t = await addTask(admin, pid, 'Aufgabe ' + (i + 1))
      await api('PUT', `/tasks/${t}/assignments`, admin, [{ resource_id: res[a], units: 50 }])
    }
    await page.goto('/login')
    await page.locator('input[autocomplete=username]').fill('admin')
    await page.locator('input[type=password]').fill(process.env.E2E_ADMIN_PASSWORD ?? 'openplan-dev-1')
    await page.locator('button.primary').click()
    await page.waitForURL(/\/$/)
    await page.goto(`/project/${pid}`)
    await page.setViewportSize({ width: 1200, height: 460 })              // niedrig, damit die Zeilen scrollen müssen
    await page.locator('.tabs button', { hasText: 'Team' }).click()
    await expect(page.locator('.tp .lpane')).toBeVisible()
    const sync = await page.evaluate(async () => {
      const r = document.querySelector('.tp .rpane') as HTMLElement
      r.scrollTop = 90
      await new Promise(res => setTimeout(res, 200))
      return { l: (document.querySelector('.tp .lpane') as HTMLElement).scrollTop, r: r.scrollTop }
    })
    expect(sync.r).toBeGreaterThan(0)
    expect(sync.l).toBe(sync.r)                                         // links und rechts scrollen vertikal gemeinsam
    // Balken von A auf die Zeile von B ziehen -> Ressource wechselt
    await page.evaluate(() => { (document.querySelector('.tp .rpane') as HTMLElement).scrollTop = 0 })
    const bar = page.locator('.tp rect.tb').first()
    const box = (await bar.boundingBox())!
    const svg = (await page.locator('.tp .tsvg').boundingBox())!
    const rows = await page.locator('.tp .lrow').evaluateAll(els => els.map(e => e.className))
    const target = rows.findIndex((c, i) => c.includes('res') && i > 0)
    await page.mouse.move(box.x + 10, box.y + 9)
    await page.mouse.down()
    await page.mouse.move(box.x + 10, svg.y + target * 28 + 14, { steps: 8 })
    await page.mouse.up()
    await expect.poll(async () => {
      const d = await api('GET', `/projects/${pid}`, await adminToken())
      return d.assignments.filter((x: any) => x.resource_id === res[b]).length
    }).toBe(1)
  })
})
