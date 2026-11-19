import { test, expect, ADMIN, PW, api, adminToken, createUser, createProject, uniq } from '../helpers/api'

test('Meine Aufgaben: Liste, Filter, Erledigen und Zähler', async ({ page }) => {
  const admin = await adminToken()
  const name = 'todo' + uniq()
  const uid = await createUser(admin, name)
  const { pid, res } = await createProject(admin, 'E2E Todo ' + uniq(), [{ id: uid, name }])
  const mk = async (n: string, dur: number) => {
    const d = await api('POST', `/projects/${pid}/tasks`, admin, { name: n, duration: dur })
    const tid = Math.max(...d.tasks.map((t: any) => t.id))
    await api('PUT', `/tasks/${tid}/assignments`, admin, [{ resource_id: res[name], units: 100 }])
    return tid
  }
  await api('PATCH', `/projects/${pid}`, admin, { start_date: '2026-09-01' })      // weit in der Vergangenheit -> überfällig
  await mk('Aufgabe Eins', 2)
  await mk('Aufgabe Zwei', 3)

  await page.goto('/login')
  await page.locator('input[autocomplete=username]').fill(name)
  await page.locator('input[type=password]').fill(PW)
  await page.locator('button.primary').click()
  await page.waitForURL(/\/$/)
  await page.getByRole('link', { name: /Meine Aufgaben/ }).click()
  await expect(page.locator('.todo li')).toHaveCount(2)
  await expect(page.locator('.grp.overdue')).toContainText('Aufgabe Eins')
  await page.getByRole('button', { name: /Diese Woche/ }).click()
  await expect(page.locator('.todo li')).toHaveCount(0)
  await page.getByRole('button', { name: /^Alle/ }).click()
  await page.locator('.todo li', { hasText: 'Aufgabe Eins' }).locator('.chk').click()
  await expect(page.locator('.todo li')).toHaveCount(1)
  await page.locator('.todo li .main').click()
  await page.waitForURL(new RegExp('/project/' + pid))
  await expect(page.locator('.modal')).toBeVisible()           // Details des Vorgangs öffnen sich direkt
  await api('DELETE', `/projects/${pid}`, admin)
})
