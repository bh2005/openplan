import { test, expect, adminToken, api, createProject, loginUi, ADMIN, uniq } from '../helpers/api'

test('Abwesenheit: anlegen, im Teamplaner als Konflikt, Jahresansicht, löschen', async ({ page }) => {
  const admin = await adminToken()
  const { pid } = await createProject(admin, 'E2E Abwesenheit ' + uniq())
  const d = await api('POST', `/projects/${pid}/resources`, admin, { name: 'Anna', max_units: 100 })
  const rid = d.resources[0].id
  const t = await api('POST', `/projects/${pid}/tasks`, admin, { name: 'Rollout', duration: 5, constraint_type: 'SNET', constraint_date: '2026-11-02' })
  const tid = t.tasks.find((x: any) => x.name === 'Rollout').id
  await api('PUT', `/tasks/${tid}/assignments`, admin, [{ resource_id: rid, units: 100 }])

  await loginUi(page, ADMIN.username, ADMIN.password, `/project/${pid}`)
  await page.locator('.tabs button', { hasText: 'Ressourcen' }).first().click()
  const row = page.locator('tr.new').last()
  await row.locator('input[type=date]').first().fill('2026-11-04')
  await row.locator('input[type=date]').nth(1).fill('2026-11-05')
  await row.locator('select').nth(1).selectOption('training')
  await row.getByRole('button', { name: 'Hinzufügen' }).click()
  await expect(page.locator('table.abs tbody tr:not(.new)', { hasText: 'Schulung' })).toBeVisible()
  expect((await api('GET', `/projects/${pid}`, admin)).absences).toHaveLength(1)

  await page.locator('.tabs button', { hasText: 'Team' }).first().click()
  await expect(page.locator('.lrow.res .num', { hasText: '⚠' })).toBeVisible()       // Einsatz während Abwesenheit
  await expect(page.locator('rect.abs')).toHaveCount(1)

  await page.locator('.tabs button', { hasText: 'Kalender' }).first().click()
  await page.getByRole('button', { name: 'Jahr', exact: true }).click()
  await expect(page.locator('.yearv .ym')).toHaveCount(12)

  await page.locator('.tabs button', { hasText: 'Ressourcen' }).first().click()
  page.once('dialog', dlg => dlg.accept())
  await page.locator('table.abs tbody tr:not(.new)', { hasText: 'Schulung' }).getByRole('button', { name: 'Löschen' }).click()
  await expect(page.locator('table.abs tbody tr:not(.new)', { hasText: 'Schulung' })).toHaveCount(0)
  await api('DELETE', `/projects/${pid}`, admin)
})
