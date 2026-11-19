import { test, expect, adminToken, api, createProject, loginUi, ADMIN, uniq } from '../helpers/api'

test('Dashboard: Ampel, Filter, Risiken, Export', async ({ page }) => {
  const admin = await adminToken()
  const { pid } = await createProject(admin, 'E2E Dashboard ' + uniq())
  const t = await api('POST', `/projects/${pid}/tasks`, admin, { name: 'Klemmt', duration: 3 })
  const tid = t.tasks.find((x: any) => x.name === 'Klemmt').id
  await api('POST', `/projects/${pid}/tasks/status`, admin, { task_ids: [tid], status: 'blocked' })
  await page.setViewportSize({ width: 1400, height: 900 })
  await loginUi(page, ADMIN.username, ADMIN.password, '/dashboard')
  await expect(page.locator('.tiles .tile').first()).toBeVisible()
  const row = page.locator('table.pt tbody tr', { hasText: 'E2E Dashboard' }).first()
  await expect(row.locator('.dot.red')).toBeVisible()                           // blockiert -> rot
  await expect(row).toContainText('blockiert')
  await expect(page.locator('.rk li').first()).toBeVisible()
  await page.locator('.chips').getByRole('button', { name: /^Rot/ }).click()
  expect(await page.locator('table.pt tbody tr .dot:not(.red)').count()).toBe(0)
  await page.locator('.chips').getByRole('button', { name: 'Alle', exact: true }).click()
  const [png] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'PNG', exact: true }).click()])
  expect(png.suggestedFilename()).toMatch(/\.png$/)
  await page.screenshot({ path: 'dash.tmp.png', fullPage: false })
  await api('DELETE', `/projects/${pid}`, admin)
})
