import { test, expect, adminToken, api, createProject, createUser, loginUi, ADMIN, PW, uniq } from '../helpers/api'

test('Überlastung auflösen: Vorschlag prüfen, übernehmen', async ({ page }) => {
  const admin = await adminToken()
  const { pid } = await createProject(admin, 'E2E Leveling ' + uniq())
  const rid = (await api('POST', `/projects/${pid}/resources`, admin, { name: 'Anna', max_units: 100 })).resources[0].id
  const mk = async (name: string, duration: number, assign = true) => {
    const id = (await api('POST', `/projects/${pid}/tasks`, admin, { name, duration, constraint_type: 'SNET', constraint_date: '2099-03-02' })).tasks.find((x: any) => x.name === name).id as number
    if (assign) await api('PUT', `/tasks/${id}/assignments`, admin, [{ resource_id: rid, units: 100 }])
    return id
  }
  await mk('Alpha', 2); await mk('Beta', 2); await mk('Lang', 10, false)

  await loginUi(page, ADMIN.username, ADMIN.password, `/project/${pid}`)
  await page.locator('.tabs button', { hasText: 'Team' }).first().click()
  await page.getByRole('button', { name: /Überlastung auflösen/ }).click()
  await expect(page.locator('.lv table.mt tbody tr')).toHaveCount(1)
  await page.getByRole('button', { name: /1 Verschiebungen übernehmen/ }).click()
  await expect(page.locator('.lv')).toHaveCount(0)
  await expect(page.getByRole('button', { name: /Überlastung auflösen/ })).toHaveCount(0)   // keine Überlast mehr
  await api('DELETE', `/projects/${pid}`, admin)
})

test('Meine Abwesenheiten: gilt im Projekt der verknüpften Ressource, Krank maskiert', async ({ page }) => {
  const admin = await adminToken()
  const s = uniq(), name = 'ma' + s
  const u = await createUser(admin, name)
  const { pid } = await createProject(admin, 'E2E MyAbs ' + s)
  await api('POST', `/projects/${pid}/resources`, admin, { name: 'Ma', user_id: u })

  await loginUi(page, name, PW, '/absences')
  await page.locator('input[type=date]').first().fill('2099-03-02')
  await page.locator('input[type=date]').nth(1).fill('2099-03-03')
  await page.locator('select').first().selectOption('sick')
  await page.locator('input[maxlength="200"]').fill('Arzt')
  await page.getByRole('button', { name: 'Hinzufügen' }).click()
  await expect(page.locator('ul li', { hasText: 'Arzt' })).toBeVisible()

  const d = await api('GET', `/projects/${pid}`, admin)
  expect(d.absences).toHaveLength(1)
  expect(d.absences[0]).toMatchObject({ source: 'user', kind: 'other', note: '' })      // für andere maskiert
  page.once('dialog', dlg => dlg.accept())
  await page.locator('ul li', { hasText: 'Arzt' }).getByRole('button', { name: 'Löschen' }).click()
  await expect(page.locator('ul li', { hasText: 'Arzt' })).toHaveCount(0)
  expect((await api('GET', `/projects/${pid}`, admin)).absences).toHaveLength(0)
  await api('DELETE', `/projects/${pid}`, admin)
})
