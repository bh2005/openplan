import { test, expect, ADMIN, PW, adminToken, api, addTask, createProject, createUser, newSession, tab, uniq } from '../helpers/api'

async function asAdmin(page: import('@playwright/test').Page, target: string) {
  await page.goto('/login')
  await page.locator('input[autocomplete=username]').fill(ADMIN.username)
  await page.locator('input[type=password]').fill(ADMIN.password)
  await page.locator('button.primary').click()
  await expect(page.getByRole('button', { name: 'Abmelden' })).toBeVisible()
  await page.goto(target)
}

const card = (page: import('@playwright/test').Page, id: number) => page.locator(`.card[data-task="${id}"]`)

test.describe('Board (Kanban)', () => {
  test('Spalten, Statusfeld, Ziehen nach „Blockiert“ mit Grund, wartende Vorgänger', async ({ page }) => {
    const admin = await adminToken()
    const { pid } = await createProject(admin, 'E2E Board ' + uniq())
    const a = await addTask(admin, pid, 'Alpha prüfen')
    const b = await addTask(admin, pid, 'Beta liefern')
    const c = await addTask(admin, pid, 'Gamma einbauen')
    await api('PUT', `/tasks/${c}/predecessors`, admin, [{ pred_id: a, type: 'FS', lag: 0 }])

    await asAdmin(page, `/project/${pid}`)
    await tab(page, 'Board').click()
    await expect(page.locator('.col.s-open .card')).toHaveCount(3)
    await expect(page.locator('.col.s-in_progress .card')).toHaveCount(0)
    await expect(card(page, c).locator('.wait')).toContainText('wartet auf 1')

    // Kritischer Pfad: A → C ist der längste Pfad; erledigte Vorgänge gelten nicht mehr als kritisch
    await expect(card(page, c)).toHaveClass(/crit/)

    // Statusfeld auf der Karte (Touch/Tastatur-Weg)
    await card(page, a).locator('select.st').selectOption('in_progress')
    await expect(page.locator('.col.s-in_progress').locator(`.card[data-task="${a}"]`)).toBeVisible()

    // Ziehen nach „Blockiert“ → Grund wird erfragt und steht auf der Karte
    page.once('dialog', d => d.accept('Wartet auf Lieferung'))
    await card(page, b).dragTo(page.locator('.col.s-blocked'))
    const blocked = page.locator('.col.s-blocked').locator(`.card[data-task="${b}"]`)
    await expect(blocked).toBeVisible()
    await expect(blocked.locator('.note')).toContainText('Wartet auf Lieferung')

    // Vorgänger nicht erledigt → Rückfrage; Abbrechen ändert nichts, Bestätigen setzt den Status
    page.once('dialog', d => d.dismiss())
    await card(page, c).locator('select.st').selectOption('done')
    await expect(page.locator('.col.s-open').locator(`.card[data-task="${c}"]`)).toBeVisible()
    page.once('dialog', d => d.accept())
    await card(page, c).locator('select.st').selectOption('done')
    await expect(page.locator('.col.s-done').locator(`.card[data-task="${c}"]`)).toBeVisible()
    await expect(card(page, c)).not.toHaveClass(/crit/)
    await expect(card(page, c).locator('.tag.crit')).toHaveCount(0)

    // Der Plan ist die Wahrheit: derselbe Status im Backend
    const plan = await api('GET', `/projects/${pid}`, admin)
    const st = (id: number) => plan.tasks.find((t: any) => t.id === id).status
    expect([st(a), st(b), st(c)]).toEqual(['in_progress', 'blocked', 'done'])
  })

  test('Suche, Filter und Bahnen', async ({ page }) => {
    const admin = await adminToken()
    const { pid } = await createProject(admin, 'E2E Board Filter ' + uniq())
    const a = await addTask(admin, pid, 'Router tauschen')
    await addTask(admin, pid, 'Switch konfigurieren')
    await api('POST', `/projects/${pid}/tasks/status`, admin, { task_ids: [a], status: 'done' })

    await asAdmin(page, `/project/${pid}`)
    await tab(page, 'Board').click()
    await expect(page.locator('.card')).toHaveCount(2)
    await page.getByPlaceholder('Suchen: Name, PSP, Person …').fill('switch')
    await expect(page.locator('.card')).toHaveCount(1)
    await page.getByPlaceholder('Suchen: Name, PSP, Person …').fill('')
    await page.getByLabel('Erledigte ausblenden').check()
    await expect(page.locator('.card')).toHaveCount(1)
    await page.getByLabel('Erledigte ausblenden').uncheck()

    await page.getByLabel('Bahnen').selectOption('person')
    await expect(page.locator('.gt', { hasText: 'Nicht zugeordnet' })).toBeVisible()
    await page.getByLabel('Bahnen').selectOption('none')
    await expect(page.locator('.gt')).toHaveCount(0)
  })

  test('Lange Spalten lassen sich scrollen (Mausrad)', async ({ page }) => {
    const admin = await adminToken()
    const { pid } = await createProject(admin, 'E2E Board Scroll ' + uniq())
    for (let i = 1; i <= 25; i++) await addTask(admin, pid, 'Aufgabe ' + i)
    await asAdmin(page, `/project/${pid}`)
    await tab(page, 'Board').click()
    await expect(page.locator('.col.s-open .card')).toHaveCount(25)
    const board = page.locator('.board')
    const m = await board.evaluate(el => ({ sh: el.scrollHeight, ch: el.clientHeight, top: el.scrollTop }))
    expect(m.sh, 'Inhalt höher als der sichtbare Bereich').toBeGreaterThan(m.ch)
    expect(m.top).toBe(0)
    await board.hover()
    await page.mouse.wheel(0, 600)
    await expect.poll(() => board.evaluate(el => el.scrollTop)).toBeGreaterThan(0)
    await board.evaluate(el => { el.scrollTop = el.scrollHeight })
    await expect(page.locator('.col.s-open .card').last()).toBeInViewport()
  })

  test('Betrachter sieht das Board, kann aber nichts verschieben', async ({ browser }) => {
    const admin = await adminToken()
    const name = 'e2e_view_' + uniq()
    const uid = await createUser(admin, name, { role: 'viewer' })
    const { pid } = await createProject(admin, 'E2E Board View ' + uniq())
    await api('PUT', `/projects/${pid}/members`, admin, [{ user_id: uid, role: 'viewer' }])
    await addTask(admin, pid, 'Nur ansehen')

    const { context, page } = await newSession(browser, name, PW, `/project/${pid}`)
    await tab(page, 'Board').click()
    await expect(page.locator('.col.s-open .card')).toHaveCount(1)
    await expect(page.locator('.card select.st')).toHaveCount(0)
    await expect(page.locator('.card[draggable="true"]')).toHaveCount(0)
    await context.close()
  })
})
