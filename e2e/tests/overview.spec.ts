import { test, expect, adminToken, api, createProject, createUser, loginUi, ADMIN, uniq } from '../helpers/api'

test('Wer arbeitet woran: Person mit Projekt, Filter und Projektkarte', async ({ page }) => {
  const admin = await adminToken()
  const s = uniq(), name = 'ov' + s
  const u = await createUser(admin, name)
  const { pid } = await createProject(admin, 'E2E Übersicht ' + s)
  const rid = (await api('POST', `/projects/${pid}/resources`, admin, { name: 'R' + s, user_id: u })).resources[0].id
  const t = await api('POST', `/projects/${pid}/tasks`, admin, { name: 'Arbeit', duration: 3 })
  await api('PUT', `/tasks/${t.tasks.find((x: any) => x.name === 'Arbeit').id}/assignments`, admin, [{ resource_id: rid, units: 50 }])

  await loginUi(page, ADMIN.username, ADMIN.password, '/overview')
  await page.getByPlaceholder(/Person oder Projekt/).fill(name)
  const row = page.locator('table.pt tbody tr', { hasText: name })
  await expect(row).toHaveCount(1)
  await expect(row.locator('a.chip', { hasText: 'E2E Übersicht ' + s })).toBeVisible()
  await page.getByRole('button', { name: 'Projekte', exact: true }).click()
  await page.getByPlaceholder(/Person oder Projekt/).fill('E2E Übersicht ' + s)
  const card = page.locator('.card', { hasText: 'E2E Übersicht ' + s })
  await expect(card).toHaveCount(1)
  await expect(card.locator('li', { hasText: name })).toBeVisible()
  await row.count()
  await api('DELETE', `/projects/${pid}`, admin)
})
