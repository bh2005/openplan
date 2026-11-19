import { test, expect, adminToken, api, createProject, loginUi, ADMIN, uniq } from '../helpers/api'

test('Puffer: Spalten, Pufferlinie, Nur kritische', async ({ page }) => {
  const admin = await adminToken()
  const { pid } = await createProject(admin, 'E2E Puffer ' + uniq())
  const mk = async (name: string, duration: number) =>
    (await api('POST', `/projects/${pid}/tasks`, admin, { name, duration })).tasks.find((x: any) => x.name === name).id as number
  const a = await mk('Lang', 5), b = await mk('Kurz', 1), c = await mk('Ende', 2)
  await api('PUT', `/tasks/${c}/predecessors`, admin, [{ pred_id: a, type: 'FS', lag: 0 }, { pred_id: b, type: 'FS', lag: 0 }])
  const d = await api('GET', `/projects/${pid}`, admin)
  const kurz = d.tasks.find((x: any) => x.name === 'Kurz')
  expect([kurz.total_float, kurz.free_float]).toEqual([4, 4])

  await loginUi(page, ADMIN.username, ADMIN.password, `/project/${pid}`)
  await expect(page.locator('.thead .c', { hasText: 'fr. Puffer' })).toHaveCount(0)
  await page.getByLabel('Puffer', { exact: true }).check()
  await expect(page.locator('.thead .c', { hasText: 'fr. Puffer' })).toBeVisible()
  await expect(page.locator('.trow', { hasText: 'Kurz' }).locator('.c.var').first()).toHaveText('4 T')
  await expect(page.locator('line.flt')).toHaveCount(1)                       // nur „Kurz“ hat freien Puffer
  await page.getByLabel('Nur kritische').check()
  await expect(page.locator('.trow', { hasText: 'Kurz' })).toHaveCount(0)
  await expect(page.locator('.trow', { hasText: 'Lang' })).toHaveCount(1)
  await api('DELETE', `/projects/${pid}`, admin)
})
