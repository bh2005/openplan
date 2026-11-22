import type { DeviceParse, DeviceReport, Template, BackupState, TaskComment, AppNotification, LdapSettings, MailSettings, ReportAdmin, ReportSub, TlsStatus, TaskFile, Actual, Budget, Finance, ImportReport, DirUser, JournalEntry, Project, ProjectData, User } from './types'

const KEY = 'openplan.token'
let onUnauthorized: () => void = () => {}
export const setUnauthorizedHandler = (fn: () => void) => { onUnauthorized = fn }

export const getToken = () => { try { return localStorage.getItem(KEY) } catch { return null } }
export const setToken = (t: string | null) => {
  try { t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY) } catch { /* privat */ }
}

import { lang, t as tr } from './i18n'
import { translateApi } from '../locales/en.api'

/** Serverfehler in der Benutzersprache anzeigen (das Backend liefert deutsche Texte). */
const tmsg = (m: string) => (lang.value === 'en' ? translateApi(m) : m)

export interface LevelingMove { task_id: number; name: string; shift: number; old_start: string; old_finish: string; new_start: string; new_finish: string; resources: string[] }
export interface LevelingProposal {
  conflicts_before: number; conflicts_after: number; moves: LevelingMove[]
  unresolved: { resource_id: number; resource: string; date: string; load: number; capacity: number; tasks: { id: number; name: string }[] }[]
}
export interface OverviewProject { pid: number; name: string; roles: ('lead' | 'member' | 'assigned')[]; tasks_open: number; tasks_blocked: number; tasks_overdue: number; load_now: number; until: string | null; funktion?: string }
export interface OverviewPerson {
  key: string; name: string; user_id: number | null; capacity: number; load_now: number; peak: number; over: boolean; absent_today: boolean
  next_absence: { start: string; end: string; kind: 'vacation' | 'training' | 'sick' | 'other' } | null; projects: OverviewProject[]
}
export interface Overview {
  today: string; people: OverviewPerson[]
  projects: { id: number; name: string; owner: string | null; finish: string | null; tasks_total: number; tasks_done: number; tasks_blocked: number; tasks_overdue: number
    people: (OverviewProject & { key: string })[] }[]
}
export interface DashReason { key: string; n: number; total?: number; pct?: number }
export interface DashBudget { budget: number | null; plan: number; ac: number; eac: number | null; cpi: number | null; spi: number | null; over: boolean }
export interface DashProject {
  id: number; name: string; owner: string | null; finish: string | null; tasks_total: number; tasks_done: number; percent: number
  overdue: number; blocked: number; deadline_missed: number; status: 'red' | 'yellow' | 'green' | 'done' | 'empty'; reasons: DashReason[]
  next_milestone: { name: string; date: string; late: boolean } | null; budget: DashBudget | null
}
export interface Dashboard {
  today: string; rules: { overdue_pct: number; milestone_days: number; risk_limit: number }
  kpi: { projects: number; status: Record<string, number>; overdue: number; blocked: number; deadline_missed: number; percent: number; people: number; people_over: number; absent_today: number }
  projects: DashProject[]
  milestones: { pid: number; project: string; task_id: number; name: string; date: string; late: boolean; critical: boolean }[]
  risks: { counts: { deadline: number; blocked: number; overdue: number }
    items: { kind: 'blocked' | 'overdue' | 'deadline'; pid: number; project: string; task_id: number; name: string; who: string[]; note?: string; days: number | null; date?: string }[] }
  load: { over: { name: string; peak: number; capacity: number; load_now: number; projects: number }[]; absent: { name: string; until: string | null; kind: 'vacation' | 'training' | 'sick' | 'other' | null }[] }
  cost: { budget: number; ac: number; eac: number; over: number; projects: number } | null
}
export interface HolidaysApiState { url: string; default: string; cache: { year: number; fetched: string; count: number }[] }
export interface HolidaysApiTest { ok: boolean; called: string; message?: string; year?: number; count?: number; sample?: { date: string; name: string }[] }
export interface EnvState {
  enabled: boolean; reason: string; path: string; writable?: boolean; restart_enabled: boolean; pending_restart: boolean; backup_dir: string; known: string[]
  entries: { key: string; secret: boolean; set: boolean; value: string | null }[]
}
export interface ApiToken {
  id: number; name: string; username: string; role: string; prefix: string; scope: 'read' | 'write'; project_ids: number[]
  expires_at: string | null; expired: boolean; last_used_at: string | null; created_by: string; created_at: string
}
export interface ApiTokenIn { name: string; username: string; role: 'editor' | 'viewer'; scope: 'read' | 'write'; project_ids: number[]; expires_days: number }
export interface Webhook {
  id: number; name: string; url: string; events: string[]; project_id: number | null; enabled: boolean; created_by: string
  pending: number; failed: number; last_ok: string | null; secret?: string
}
export interface WebhookIn { name: string; url: string; events: string[]; project_id: number | null; enabled: boolean; rotate_secret?: boolean }
export interface WebhookDelivery { id: number; event: string; status: 'pending' | 'ok' | 'failed'; attempts: number; last_code: number | null; last_error: string; next_try: string; ts: string }
export interface TaskRef { system: string; ref: string; url: string }
export interface MyAbsence { id: number; start_date: string; end_date: string; kind: 'vacation' | 'training' | 'sick' | 'other'; note: string }
export interface MyTask {
  pid: number; project: string; id: number; wbs: string; name: string; start: string; finish: string; deadline: string | null
  status: 'open' | 'in_progress' | 'blocked' | 'done'; status_note: string; percent: number; critical: boolean; milestone: boolean
  bucket: 'overdue' | 'week' | 'later'
}

export type DemoKind = 'network' | 'migration' | 'release'
export type WizardKind = 'empty' | DemoKind | 'patchpanel'
export interface WizardPayload {
  kind: WizardKind; name: string; description: string; start_date: string; work_days: number[]; holidays: string[]; holiday_state?: string; owner_id?: number
  members: { user_id: number; role: 'editor' | 'viewer' }[]
  report_enabled: boolean; report_weekday: number; report_hour: number; report_to: 'owner' | 'members'
}

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}

async function req<T>(method: string, url: string, body?: unknown, raw = false): Promise<T> {
  const headers: Record<string, string> = {}
  const t = getToken()
  if (t) headers.Authorization = 'Bearer ' + t
  let payload: BodyInit | undefined
  if (body instanceof FormData) payload = body
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body) }
  let res: Response
  try { res = await fetch(url, { method, headers, body: payload }) }
  catch { throw new ApiError(0, tr('Server nicht erreichbar (offline?)')) }
  if (res.status === 401 && !url.endsWith('/auth/login')) { onUnauthorized(); throw new ApiError(401, tr('Sitzung abgelaufen')) }
  if (!res.ok) {
    let msg = res.statusText
    try {
      const j = await res.json()
      const d = j.detail
      msg = typeof d === 'string' ? d : d?.message ?? (Array.isArray(d) ? d.map((e: any) => e.msg).join('; ') : msg)
    } catch { /* kein JSON */ }
    throw new ApiError(res.status, tmsg(msg))
  }
  if (raw) return (await res.blob()) as unknown as T
  return (await res.json()) as T
}

/** Server-Sent Events per fetch (EventSource kann keinen Authorization-Header senden). Liefert eine Stop-Funktion. */
export function subscribeRevision(pid: number, onRevision: (rev: number) => void, onState: (live: boolean) => void): () => void {
  const ctl = new AbortController()
  let stopped = false
  ;(async () => {
    let delay = 1000
    while (!stopped) {
      try {
        const res = await fetch(`/api/projects/${pid}/events`, { headers: { Authorization: 'Bearer ' + (getToken() ?? '') }, signal: ctl.signal })
        if (res.status === 401) { onUnauthorized(); return }
        if (!res.ok || !res.body) throw new Error(String(res.status))
        onState(true); delay = 1000
        const rd = res.body.getReader(), dec = new TextDecoder()
        let buf = ''
        for (;;) {
          const { done, value } = await rd.read()
          if (done) break
          buf += dec.decode(value, { stream: true })
          let i: number
          while ((i = buf.indexOf('\n\n')) >= 0) {
            const block = buf.slice(0, i); buf = buf.slice(i + 2)
            if (block.includes('event: revision')) {
              const m = block.match(/data:\s*(\{.*\})/)
              if (m) { try { onRevision(JSON.parse(m[1]).revision) } catch { /* ignorieren */ } }
            } else if (block.includes('event: gone')) { stopped = true }
          }
        }
      } catch { /* Abbruch/Offline: neu verbinden */ }
      onState(false)
      if (stopped) return
      await new Promise(r => setTimeout(r, delay)); delay = Math.min(delay * 2, 15000)
    }
  })()
  return () => { stopped = true; ctl.abort() }
}

export const api = {
  login: (username: string, password: string) =>
    req<{ token: string; user: User }>('POST', '/api/auth/login', { username, password }),
  me: () => req<User>('GET', '/api/auth/me'),
  changePassword: (old_password: string, new_password: string) =>
    req<{ ok: boolean; token?: string }>('POST', '/api/auth/password', { old_password, new_password }),
  endSessions: (id: number) => req('POST', `/api/users/${id}/logout`),
  setReportsTo: (rid: number, reports_to: number | null) => req<ProjectData>('PUT', `/api/resources/${rid}/reports-to`, { reports_to }),
  users: () => req<(User & { created_at: string; auth_source: string })[]>('GET', '/api/users'),
  createUser: (u: { username: string; display_name?: string; password?: string; role: string; source?: string; see_all?: boolean }) => req('POST', '/api/users', u),
  setUserPassword: (id: number, new_password: string) => req('PUT', `/api/users/${id}/password`, { new_password }),
  setUserDisplayName: (id: number, display_name: string) => req('PUT', `/api/users/${id}/display-name`, { display_name }),
  setUserRole: (id: number, role: string) => req('PUT', `/api/users/${id}/role`, { role }),
  setSeeAll:(id: number, see_all: boolean) => req('PUT', `/api/users/${id}/see-all`, { see_all }),
  deleteUser: (id: number) => req('DELETE', '/api/users/' + id),

  projects: () => req<Project[]>('GET', '/api/projects'),
  directory: (q = '', limit = 0) => req<DirUser[]>('GET', `/api/users/directory?q=${encodeURIComponent(q)}&limit=${limit}`),
  setMembers: (id: number, items: { user_id: number; role: string }[]) =>
    req<ProjectData>('PUT', `/api/projects/${id}/members`, items),
  createProject: (p: { name: string; description: string; start_date: string; owner_id?: number }) =>
    req<ProjectData>('POST', '/api/projects', p),
  createProjectWizard: (p: WizardPayload) => req<ProjectData>('POST', '/api/projects/wizard', p),
  createDemo: (kind: DemoKind = 'network') => req<ProjectData>('POST', '/api/projects/demo?kind=' + kind),
  project: (id: number) => req<ProjectData>('GET', '/api/projects/' + id),
  revision: (id: number) => req<{ revision: number }>('GET', `/api/projects/${id}/revision`),
  holidayStates: () => req<{ code: string; name: string }[]>('GET', '/api/holidays/states'),
  holidays: (state: string, years: number[]) =>
    req<{ state: string; holidays: { date: string; name: string }[]; missing_years: number[] }>('GET', `/api/holidays?state=${state}&years=${years.join(',')}`),
  patchProject: (id: number, p: Record<string, unknown>) => req<ProjectData | { transferred: true }>('PATCH', '/api/projects/' + id, p),
  deleteProject: (id: number) => req('DELETE', '/api/projects/' + id),
  journal: (id: number) => req<JournalEntry[]>('GET', `/api/projects/${id}/journal`),
  setBaseline: (id: number) => req<ProjectData>('POST', `/api/projects/${id}/baseline`),
  clearBaseline: (id: number) => req<ProjectData>('DELETE', `/api/projects/${id}/baseline`),
  exportFile: (id: number, fmt: string) => req<Blob>('GET', `/api/projects/${id}/export?fmt=${fmt}`, undefined, true),
  importFile: (f: File) => { const fd = new FormData(); fd.append('file', f); return req<ProjectData>('POST', '/api/projects/import', fd) },

  addTask: (pid: number, t: Record<string, unknown>) => req<ProjectData>('POST', `/api/projects/${pid}/tasks`, t),
  patchTask: (id: number, t: Record<string, unknown>) => req<ProjectData>('PATCH', '/api/tasks/' + id, t),
  deleteTask: (id: number) => req<ProjectData>('DELETE', '/api/tasks/' + id),
  moveTask: (id: number, parent_id: number | null, index: number) =>
    req<ProjectData>('POST', `/api/tasks/${id}/move`, { parent_id, index }),
  bulkStatus: (pid: number, task_ids: number[], status: string) => req<ProjectData>('POST', `/api/projects/${pid}/tasks/status`, { task_ids, status }),
  shiftTask: (id: number, days: number) => req<ProjectData>('POST', `/api/tasks/${id}/shift`, { days }),
  setPreds: (id: number, preds: { pred_id: number; type: string; lag: number }[]) =>
    req<ProjectData>('PUT', `/api/tasks/${id}/predecessors`, preds),

  addResource: (pid: number, r: Record<string, unknown>) =>
    req<ProjectData>('POST', `/api/projects/${pid}/resources`, r),
  updateResource: (id: number, r: Record<string, unknown>) =>
    req<ProjectData>('PUT', '/api/resources/' + id, r),
  deleteResource: (id: number) => req<ProjectData>('DELETE', '/api/resources/' + id),
  addAbsence: (pid: number, a: Record<string, unknown>) => req<ProjectData>('POST', `/api/projects/${pid}/absences`, a),
  updateAbsence: (id: number, a: Record<string, unknown>) => req<ProjectData>('PUT', '/api/absences/' + id, a),
  deleteAbsence: (id: number) => req<ProjectData>('DELETE', '/api/absences/' + id),
  leveling: (pid: number) => req<LevelingProposal>('GET', `/api/projects/${pid}/leveling`),
  applyLeveling: (pid: number, moves: { task_id: number; new_start: string }[]) => req<ProjectData>('POST', `/api/projects/${pid}/leveling/apply`, { moves }),
  overview: () => req<Overview>('GET', '/api/overview/people'),
  myAbsences: () => req<MyAbsence[]>('GET', '/api/me/absences'),
  addMyAbsence: (a: Record<string, unknown>) => req<MyAbsence[]>('POST', '/api/me/absences', a),
  updateMyAbsence: (id: number, a: Record<string, unknown>) => req<MyAbsence[]>('PUT', '/api/me/absences/' + id, a),
  deleteMyAbsence: (id: number) => req<MyAbsence[]>('DELETE', '/api/me/absences/' + id),
  undo: (pid: number) => req<ProjectData>('POST', `/api/projects/${pid}/undo`),
  redo: (pid: number) => req<ProjectData>('POST', `/api/projects/${pid}/redo`),
  ldapSettings: () => req<LdapSettings>('GET', '/api/admin/settings/ldap'),
  saveLdapSettings: (s: Record<string, unknown>) => req<LdapSettings>('PUT', '/api/admin/settings/ldap', s),
  testLdap: (settings: Record<string, unknown>, username: string, password: string) =>
    req<{ ok: boolean; steps: { step: string; ok: boolean; detail: string }[] }>('POST', '/api/admin/settings/ldap/test', { settings, username, password }),
  tls: () => req<TlsStatus>('GET', '/api/admin/tls'),
  saveTls: (s: Record<string, unknown>) => req<TlsStatus>('PUT', '/api/admin/tls', s),
  fetchTlsCa: (url: string) => req<{ pem: string; certs: { subject: string; fingerprint: string }[] }>('POST', '/api/admin/tls/fetch-ca', { url }),
  issueTls: () => req<{ started: boolean }>('POST', '/api/admin/tls/issue'),
  tlsCert: () => req<Blob>('GET', '/api/admin/tls/cert', undefined, true),
  notifications: () => req<{ unread: number; items: AppNotification[] }>('GET', '/api/notifications'),
  readNotification: (id: number) => req<{ unread: number; items: AppNotification[] }>('POST', `/api/notifications/${id}/read`),
  readAllNotifications: () => req<{ unread: number; items: AppNotification[] }>('POST', '/api/notifications/read-all'),
  saveProfile: (p: { email?: string; notify_email?: boolean; lang?: 'de' | 'en'; theme?: 'auto' | 'light' | 'dark' }) => req<User>('PUT', '/api/auth/profile', p),
  setUserEmail: (id: number, email: string) => req('PUT', `/api/users/${id}/email`, { email }),
  mailSettings: () => req<MailSettings>('GET', '/api/admin/settings/mail'),
  saveMailSettings: (s: Record<string, unknown>) => req<MailSettings>('PUT', '/api/admin/settings/mail', s),
  testMail: (to: string) => req<{ ok: boolean; message: string }>('POST', '/api/admin/settings/mail/test', { to }),
  reportPreview: (pid: number) => req<{ html: string; text: string; recipients: { username: string; email: string }[] }>('GET', `/api/projects/${pid}/report/preview`),
  reportSend: (pid: number) => req<{ notified: number; mails: number; without_email: number }>('POST', `/api/projects/${pid}/report/send`),
  adminReports: () => req<ReportAdmin>('GET', '/api/admin/reports'),
  createReportSub: (b: Record<string, unknown>) => req<ReportSub>('POST', '/api/admin/reports', b),
  updateReportSub: (id: number, b: Record<string, unknown>) => req<ReportSub>('PUT', `/api/admin/reports/${id}`, b),
  deleteReportSub: (id: number) => req('DELETE', `/api/admin/reports/${id}`),
  sendReportSub: (id: number) => req<{ notified: number; mails: number }>('POST', `/api/admin/reports/${id}/send`),
  saveCostOwners: (items: { code: string; name: string; user_id: number }[]) => req<ReportAdmin>('PUT', '/api/admin/cost-owners', items),
  myTasks: () => req<{ items: MyTask[]; pool: number; today: string }>('GET', '/api/my-tasks'),
  myReports: () => req<{ id: number; kind: string; name: string }[]>('GET', '/api/reports/mine'),
  viewReport: (id: number) => req<{ id: number; title: string; html: string; text: string }>('GET', `/api/reports/${id}`),
  comments: (tid: number) => req<{ items: TaskComment[]; people: string[] }>('GET', `/api/tasks/${tid}/comments`),
  addComment: (tid: number, body: string) => req<{ items: TaskComment[]; people: string[] }>('POST', `/api/tasks/${tid}/comments`, { body }),
  deleteComment: (id: number) => req<{ items: TaskComment[]; people: string[] }>('DELETE', `/api/comments/${id}`),
  audit: (q: string, action: string, limit: number, offset: number) =>
    req<{ total: number; items: { id: number; ts: string; username: string; action: string; detail: string; ip: string }[]; actions: string[] }>(
      'GET', `/api/admin/audit?q=${encodeURIComponent(q)}&action=${encodeURIComponent(action)}&limit=${limit}&offset=${offset}`),
  auditCsv: (q: string, action: string) => req<Blob>('GET', `/api/admin/audit/export?q=${encodeURIComponent(q)}&action=${encodeURIComponent(action)}`, undefined, true),
  dashboard: () => req<Dashboard>('GET', '/api/dashboard'),
  holidaysApi: () => req<HolidaysApiState>('GET', '/api/admin/settings/holidays'),
  saveHolidaysApi: (url: string) => req<HolidaysApiState>('PUT', '/api/admin/settings/holidays', { url }),
  testHolidaysApi: (url: string) => req<HolidaysApiTest>('POST', '/api/admin/settings/holidays/test', { url }),
  clearHolidaysCache: () => req<HolidaysApiState>('DELETE', '/api/admin/settings/holidays/cache'),
  envState: () => req<EnvState>('GET', '/api/admin/env'),
  saveEnv: (entries: { key: string; value: string | null }[]) => req<EnvState>('PUT', '/api/admin/env', { entries }),
  apiTokens: () => req<ApiToken[]>('GET', '/api/admin/tokens'),
  createApiToken: (b: ApiTokenIn) => req<ApiToken & { token: string }>('POST', '/api/admin/tokens', b),
  revokeApiToken: (id: number) => req<{ ok: boolean }>('DELETE', `/api/admin/tokens/${id}`),
  taskRefs: (tid: number) => req<TaskRef[]>('GET', `/api/tasks/${tid}/refs`),
  putTaskRef: (tid: number, system: string, b: { ref: string; url: string }) => req<TaskRef & { changed: boolean }>('PUT', `/api/tasks/${tid}/refs/${encodeURIComponent(system)}`, b),
  deleteTaskRef: (tid: number, system: string) => req<{ ok: boolean; removed: boolean }>('DELETE', `/api/tasks/${tid}/refs/${encodeURIComponent(system)}`),
  webhooks: () => req<{ items: Webhook[]; events: string[] }>('GET', '/api/admin/webhooks'),
  createWebhook: (b: WebhookIn) => req<Webhook>('POST', '/api/admin/webhooks', b),
  updateWebhook: (id: number, b: WebhookIn) => req<Webhook>('PUT', `/api/admin/webhooks/${id}`, b),
  deleteWebhook: (id: number) => req<{ ok: boolean }>('DELETE', `/api/admin/webhooks/${id}`),
  testWebhook: (id: number) => req<{ status: string; code: number | null; error: string; delivery_id: number }>('POST', `/api/admin/webhooks/${id}/test`),
  webhookDeliveries: (id: number) => req<WebhookDelivery[]>('GET', `/api/admin/webhooks/${id}/deliveries`),
  restartServer: () => req<{ restarting: boolean }>('POST', '/api/admin/restart'),
  backupState: () => req<BackupState>('GET', '/api/admin/backup'),
  saveBackupSettings: (s: Record<string, unknown>) => req<BackupState>('PUT', '/api/admin/backup', s),
  createBackup: () => req<BackupState>('POST', '/api/admin/backup'),
  verifyBackup: (n: string) => req<{ ok: boolean; message: string; counts?: Record<string, number>; files?: number }>('POST', `/api/admin/backup/${n}/verify`),
  downloadBackup: (n: string) => req<Blob>('GET', `/api/admin/backup/${n}/download`, undefined, true),
  deleteBackup: (n: string) => req<BackupState>('DELETE', `/api/admin/backup/${n}`),
  reminderSettings: () => req<any>('GET', '/api/admin/settings/reminders'),
  saveReminderSettings: (s: Record<string, unknown>) => req<any>('PUT', '/api/admin/settings/reminders', s),
  runReminders: () => req<Record<string, number>>('POST', '/api/admin/reminders/run'),
  templates: () => req<Template[]>('GET', '/api/templates'),
  deviceSample: () => req<Blob>('GET', '/api/templates/sample.xlsx', undefined, true),
  saveTemplate: (t: Omit<Template, 'id'>, id?: number) => req<Template>(id ? 'PUT' : 'POST', id ? `/api/templates/${id}` : '/api/templates', t),
  deleteTemplate: (id: number) => req('DELETE', `/api/templates/${id}`),
  roleMap: (pid: number) => req<{ roles: string[]; map: Record<string, number> }>('GET', `/api/projects/${pid}/role-map`),
  parseDevices: (pid: number, file: File) => { const fd = new FormData(); fd.append('file', file); return req<DeviceParse>('POST', `/api/projects/${pid}/devices/parse`, fd) },
  importDevices: (pid: number, file: File, o: { mapping: Record<string, number>; dry_run: boolean; partial: boolean; create_missing: boolean; parent_id: number | null; role_map: Record<string, number> }) => {
    const fd = new FormData()
    fd.append('file', file); fd.append('mapping', JSON.stringify(o.mapping)); fd.append('dry_run', String(o.dry_run)); fd.append('partial', String(o.partial))
    fd.append('create_missing', String(o.create_missing)); fd.append('role_map', JSON.stringify(o.role_map)); if (o.parent_id) fd.append('parent_id', String(o.parent_id))
    return req<DeviceReport>('POST', `/api/projects/${pid}/devices/import`, fd)
  },
  addDevice: (pid: number, b: Record<string, unknown>) => req<ProjectData>('POST', `/api/projects/${pid}/devices`, b),
  claimTask: (id: number) => req<ProjectData>('POST', `/api/tasks/${id}/claim`),
  releaseTask: (id: number) => req<ProjectData>('POST', `/api/tasks/${id}/release`),
  setAssignments: (tid: number, items: { resource_id?: number; user_id?: number; units: number }[]) =>
    req<ProjectData>('PUT', `/api/tasks/${tid}/assignments`, items),

  // ── Kosten & Budget (EUR) ──
  finance: (pid: number) => req<Finance>('GET', `/api/projects/${pid}/finance`),
  budget: (pid: number, status?: string) => req<Budget>('GET', `/api/projects/${pid}/budget${status ? '?status=' + status : ''}`),
  setCostSettings: (pid: number, members_see_costs: boolean) =>
    req<Finance>('PUT', `/api/projects/${pid}/finance/settings`, { members_see_costs }),
  masterAdd: (pid: number, kind: string, m: { code: string; name: string }) => req<Finance>('POST', `/api/projects/${pid}/${kind}`, m),
  masterUpdate: (kind: string, id: number, m: { code: string; name: string }) => req<Finance>('PUT', `/api/${kind}/${id}`, m),
  masterDelete: (kind: string, id: number) => req<Finance>('DELETE', `/api/${kind}/${id}`),
  masterImport: (pid: number, kind: string, text: string) => req<Finance>('POST', `/api/projects/${pid}/${kind}/import`, { text }),
  itemAdd: (tid: number, i: Record<string, unknown>) => req<Finance>('POST', `/api/tasks/${tid}/cost-items`, i),
  itemUpdate: (id: number, i: Record<string, unknown>) => req<Finance>('PUT', `/api/cost-items/${id}`, i),
  itemDelete: (id: number) => req<Finance>('DELETE', `/api/cost-items/${id}`),
  setBudgetLines: (pid: number, lines: { cost_center_id: number | null; cost_type_id: number | null; amount: number }[]) =>
    req<Finance>('PUT', `/api/projects/${pid}/budget-lines`, lines),
  actuals: (pid: number, q = '', offset = 0, limit = 100) =>
    req<{ total: number; sum: number; items: Actual[] }>('GET', `/api/projects/${pid}/actuals?limit=${limit}&offset=${offset}&q=${encodeURIComponent(q)}`),
  actualAdd: (pid: number, a: Record<string, unknown>) => req('POST', `/api/projects/${pid}/actuals`, a),
  actualUpdate: (id: number, a: Record<string, unknown>) => req('PUT', `/api/actuals/${id}`, a),
  actualDelete: (id: number) => req('DELETE', `/api/actuals/${id}`),
  actualsImport: (pid: number, f: File, o: { dry_run: boolean; create_missing: boolean; partial: boolean }) => {
    const fd = new FormData()
    fd.append('file', f)
    fd.append('dry_run', String(o.dry_run)); fd.append('create_missing', String(o.create_missing)); fd.append('partial', String(o.partial))
    return req<ImportReport>('POST', `/api/projects/${pid}/actuals/import`, fd)
  },
  budgetExport: (pid: number, what: 'matrix' | 'actuals') => req<Blob>('GET', `/api/projects/${pid}/budget/export?what=${what}`, undefined, true),

  // ── Dokumente an Vorgängen ──
  files: (tid: number) => req<TaskFile[]>('GET', `/api/tasks/${tid}/files`),
  uploadFiles: (tid: number, files: File[], comment = '') => {
    const fd = new FormData()
    files.forEach(f => fd.append('files', f))
    fd.append('comment', comment)
    return req<TaskFile[]>('POST', `/api/tasks/${tid}/files`, fd)
  },
  addLink: (tid: number, l: { url: string; title: string; comment: string }) => req<TaskFile[]>('POST', `/api/tasks/${tid}/links`, l),
  downloadFile: (id: number, inline = false) => req<Blob>('GET', `/api/files/${id}/download${inline ? '?inline=true' : ''}`, undefined, true),
  deleteFile: (id: number) => req('DELETE', `/api/files/${id}`),
}

/** Muster-Geräteliste (aus den aktuellen Vorlagen erzeugt) als Datei speichern. */
export async function downloadDeviceSample(): Promise<void> {
  const b = await api.deviceSample()
  const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = "geraeteliste-vorlage.xlsx"; a.click(); URL.revokeObjectURL(a.href)
}
