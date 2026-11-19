import { test, expect, ADMIN, adminToken, createProject, createUser, api, uniq, loginUi } from '../helpers/api'

test.describe('Suchen & Filtern', () => {
  test('Projektliste: Suche, Filter nach Verantwortlichem, Zurücksetzen', async ({ page }) => {
    const admin = await adminToken()
    const key = 'Zebra' + uniq()
    const p1 = (await createProject(admin, `${key} Alpha`)).pid
    const p2 = (await createProject(admin, `${key} Beta`)).pid
    await api('PATCH', `/projects/${p2}`, admin, { description: 'Rollout für Köln' })
    await createProject(admin, 'Ganz anderes Projekt ' + uniq())

    await loginUi(page, ADMIN.username, ADMIN.password)
    await expect(page.locator('.fcount')).toContainText(' von ')
    const all = Number((await page.locator('.fcount').textContent())!.match(/von (\d+)/)![1])      // Gesamtzahl laut Zähler
    const q = page.getByLabel('Projekte suchen')

    await q.fill(key)                                                      // beide Treffer
    await expect(page.locator('.card')).toHaveCount(2)
    await expect(page.locator('.fcount')).toContainText(`2 von ${all}`)
    await q.fill(`${key} beta`)                                            // mehrere Wörter, Groß-/Kleinschreibung egal
    await expect(page.locator('.card')).toHaveCount(1)
    await expect(page.locator('.card h3')).toHaveText(`${key} Beta`)
    await q.fill(`${key} koeln`.replace('koeln', 'köln'))                  // Treffer in der Beschreibung
    await expect(page.locator('.card h3')).toHaveText(`${key} Beta`)
    await q.fill('gibt-es-nicht-' + uniq())
    await expect(page.locator('.card')).toHaveCount(0)
    await expect(page.getByText(/Keine Projekte passen/)).toBeVisible()
    await page.getByRole('button', { name: 'Filter zurücksetzen' }).click()
    await expect(page.locator('.card')).toHaveCount(all)

    await page.locator('.filters select').nth(1).selectOption(ADMIN.username)        // Verantwortlicher
    await expect(page.locator('.card').first()).toBeVisible()
    await page.locator('.filters select').nth(2).selectOption('name')               // Sortierung A–Z
    const names = await page.locator('.card h3').allTextContents()
    expect(names).toEqual([...names].sort((a, b) => a.localeCompare(b, 'de', { numeric: true })))
    void p1
  })

  test('Projektliste: „Meine“ trennt eigene von fremden Projekten', async ({ page, browser }) => {
    const admin = await adminToken()
    const owner = 'e2e_own_' + uniq()
    const oid = await createUser(admin, owner)
    const pid = (await createProject(admin, 'Fremdprojekt ' + uniq())).pid
    await api('PUT', `/projects/${pid}/members`, admin, [{ user_id: oid, role: 'editor' }])
    const mine = 'Meins ' + uniq()
    const ctx = await browser.newContext(); const p = await ctx.newPage()
    await loginUi(p, owner, 'e2e-passwort-1')
    await p.getByRole('button', { name: '+ Neues Projekt' }).click()
    await p.getByRole('button', { name: 'Schnell anlegen' }).click()                         // Schnellweg ohne Assistent
    await p.locator('.modal input').first().fill(mine)
    await p.getByRole('button', { name: 'Anlegen', exact: true }).click()
    await p.waitForURL(/\/project\//)
    await p.goto('/')
    await expect(p.locator('.card')).toHaveCount(2)
    await p.locator('.filters select').first().selectOption('mine')
    await expect(p.locator('.card')).toHaveCount(1)
    await expect(p.locator('.card h3')).toHaveText(mine)
    await p.locator('.filters select').first().selectOption('other')
    await expect(p.locator('.card h3')).toContainText('Fremdprojekt')
    await ctx.close()
    void page
  })

  test('Benutzerliste: Suche nach Name/E-Mail, Filter nach Rolle', async ({ page }) => {
    const admin = await adminToken()
    const key = 'suche' + uniq()
    await createUser(admin, `e2e_${key}_a`, { role: 'viewer', email: `${key}.a@corp.test` })
    await createUser(admin, `e2e_${key}_b`, { role: 'editor', email: `${key}.b@corp.test` })
    await loginUi(page, ADMIN.username, ADMIN.password)
    await expect(page.getByRole('button', { name: 'Abmelden' })).toBeVisible()
    await page.goto('/admin')
    const q = page.getByLabel('Benutzer suchen')
    await q.fill(key)
    await expect(page.locator('.adm table tbody tr')).toHaveCount(2)
    await q.fill(`${key}.b@corp`)                                          // E-Mail-Suche
    await expect(page.locator('.adm table tbody tr')).toHaveCount(1)
    await expect(page.locator('.adm table tbody tr')).toContainText(`e2e_${key}_b`)
    await q.fill(key)
    await page.locator('.ufilter select').first().selectOption('viewer')     // Rolle
    await expect(page.locator('.adm table tbody tr')).toHaveCount(1)
    await expect(page.locator('.adm table tbody tr')).toContainText(`e2e_${key}_a`)
    await page.locator('.ufilter select').first().selectOption('admin')
    await expect(page.getByText('Keine Benutzer gefunden.')).toBeVisible()
    await page.getByRole('button', { name: 'Zurücksetzen' }).click()
    await expect(page.locator('.adm table tbody tr').first()).toBeVisible()
  })
})
