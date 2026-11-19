import { expect, test, type Browser, type BrowserContext, type Page } from '@playwright/test'

const BASE = process.env.E2E_BASE_URL ?? 'http://localhost:5173'
export const ADMIN = { username: process.env.E2E_ADMIN_USER ?? 'admin', password: process.env.E2E_ADMIN_PASSWORD ?? 'openplan-dev-1' }
export const PW = 'e2e-passwort-1'
export const uniq = () => Math.random().toString(36).slice(2, 8)

/** Schlanker API-Client für Testdaten (Setup geht an der Oberfläche vorbei, geprüft wird dann im Browser). */
export async function api<T = any>(method: string, path: string, token?: string, body?: unknown): Promise<T> {
  const r = await fetch(`${BASE}/api${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: 'Bearer ' + token } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const text = await r.text()
  const j = text ? JSON.parse(text) : null
  if (!r.ok) throw new Error(`${method} ${path} → ${r.status} ${text}`)
  return j as T
}

export const loginApi = async (username: string, password: string) => (await api<{ token: string }>('POST', '/auth/login', undefined, { username, password })).token
export const adminToken = () => loginApi(ADMIN.username, ADMIN.password)

export async function createUser(admin: string, name: string, opts: { role?: string; email?: string } = {}) {
  const { id } = await api<{ id: number }>('POST', '/users', admin, { username: name, password: PW, role: opts.role ?? 'editor' })
  if (opts.email) await api('PUT', `/users/${id}/email`, admin, { email: opts.email })
  return id
}

/** Projekt mit Mitgliedern (editor) und je einer mit dem Benutzer verknüpften Ressource. */
export async function createProject(admin: string, name: string, members: { id: number; name: string }[] = []) {
  const pid = (await api('POST', '/projects', admin, { name, start_date: '2026-10-12' })).project.id as number
  if (members.length) await api('PUT', `/projects/${pid}/members`, admin, members.map(m => ({ user_id: m.id, role: 'editor' })))
  const res: Record<string, number> = {}
  for (const m of members) {
    const d = await api('POST', `/projects/${pid}/resources`, admin, { name: m.name, user_id: m.id })
    res[m.name] = d.resources.find((r: any) => r.user_id === m.id).id
  }
  return { pid, res }
}

export async function addTask(admin: string, pid: number, name: string, extra: Record<string, unknown> = {}) {
  const d = await api('POST', `/projects/${pid}/tasks`, admin, { name, duration: 3, ...extra })
  return Math.max(...d.tasks.map((t: any) => t.id)) as number
}

export async function loginUi(page: Page, username: string, password: string, target = '/') {
  await page.goto(target)
  await page.locator('input[autocomplete=username]').fill(username)
  await page.locator('input[type=password]').fill(password)
  await page.locator('button.primary').click()
}

/** Eigener Browser-Kontext = eigene Sitzung (z. B. zweiter Benutzer). */
export async function newSession(browser: Browser, username: string, password = PW, target = '/') {
  const context: BrowserContext = await browser.newContext()
  const page = await context.newPage()
  await loginUi(page, username, password, target)
  return { context, page }
}

export const tab = (page: Page, name: string) => page.locator('.tabs button', { hasText: name }).first()
export { expect, test }
