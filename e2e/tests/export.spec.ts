import { test, expect, adminToken, api, loginUi, ADMIN } from '../helpers/api'

test('Export: Gantt als PNG/SVG, Management-Sicht, Übersicht als PNG', async ({ page }) => {
  const admin = await adminToken()
  const demo = await api('POST', '/projects/demo?kind=network', admin)
  const pid = demo.project.id
  await page.setViewportSize({ width: 1400, height: 900 })
  await loginUi(page, ADMIN.username, ADMIN.password, `/project/${pid}`)
  await page.locator('select', { hasText: 'Export' }).selectOption('image')
  const dlg = page.locator('.xd')
  await expect(dlg).toBeVisible()
  await expect(dlg.locator('.pv svg')).toBeVisible()
  const rowsAll = await dlg.locator('.pv svg text').count()
  expect(rowsAll).toBeGreaterThan(30)
  await dlg.screenshot({ path: 'export-all.tmp.png' })

  await dlg.locator('select').first().selectOption('phases')
  await expect(dlg.locator('.prev small')).toContainText('Zeilen')
  expect(await dlg.locator('.pv svg text').count()).toBeLessThan(rowsAll)
  await dlg.screenshot({ path: 'export-phases.tmp.png' })

  const [png] = await Promise.all([page.waitForEvent('download'), dlg.getByRole('button', { name: 'PNG', exact: true }).click()])
  expect(png.suggestedFilename()).toMatch(/\.png$/)
  const [svg] = await Promise.all([page.waitForEvent('download'), dlg.getByRole('button', { name: 'SVG', exact: true }).click()])
  expect(svg.suggestedFilename()).toMatch(/\.svg$/)
  await dlg.getByRole('button', { name: 'Schließen' }).click()

  await page.goto('/overview')
  await page.waitForSelector('table.pt tbody tr')
  const [png2] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'PNG', exact: true }).click()])
  expect(png2.suggestedFilename()).toMatch(/\.png$/)
  void png2
  await api('DELETE', `/projects/${pid}`, admin)
})
