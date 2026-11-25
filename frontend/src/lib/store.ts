import { reactive, computed } from 'vue'
import { api, ApiError, getToken, setToken, setUnauthorizedHandler } from './api'
import { applyPrefs, lang, theme, type Lang, type Theme } from './i18n'
import type { ProjectData, User } from './types'

export const state = reactive({
  user: null as User | null,
  data: null as ProjectData | null,
  busy: false,
  toast: '',
  toastKind: 'info' as 'info' | 'error',
  online: navigator.onLine,
})

/** UI-Kontext: bestimmt, welches Hilfethema das Panel zeigt (Tab/Unterreiter im Projekt) */
export const ui = reactive({ tab: 'gantt', sub: 'overview', helpOpen: false })

let toastTimer: number | undefined
/** Kleine hessische Bestätigung, wenn etwas auf „erledigt“ gesetzt wurde (bewusst in jeder Sprache hessisch). */
export function ferdisch(detail = '') {
  toast('Ferdisch! ✓' + (detail ? ' ' + detail : ''))
}

export function toast(msg: string, kind: 'info' | 'error' = 'info') {
  state.toast = msg
  state.toastKind = kind
  window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => (state.toast = ''), kind === 'error' ? 6000 : 2500)
}

export const canEdit = computed(() => state.user?.role === 'admin' || state.user?.role === 'editor')
export const isAdmin = computed(() => state.user?.role === 'admin')

export async function restoreSession(): Promise<boolean> {
  if (!getToken()) return false
  try { state.user = await api.me(); applyPrefs(state.user); return true } catch { return false }
}
export async function login(u: string, p: string) {
  const r = await api.login(u, p)
  setToken(r.token)
  state.user = r.user
  applyPrefs(r.user)
}

/** Sprache/Darstellung sofort umstellen und – falls angemeldet – im Benutzerprofil merken. */
export async function savePrefs(p: { lang?: Lang; theme?: Theme }) {
  applyPrefs({ lang: p.lang ?? lang.value, theme: p.theme ?? theme.value })
  if (!state.user) return
  try { state.user = { ...state.user, ...(await api.saveProfile(p)) } } catch { /* bleibt lokal gespeichert */ }
}
export function logout() {
  setToken(null)
  state.user = null
  state.data = null
}
setUnauthorizedHandler(() => { logout(); if (location.pathname !== '/login') location.assign('/login') })
window.addEventListener('online', () => (state.online = true))
window.addEventListener('offline', () => (state.online = false))

/** Führt eine Mutation aus, übernimmt das neue Projekt und meldet Fehler als Toast. */
export async function mutate(fn: () => Promise<ProjectData>): Promise<boolean> {
  state.busy = true
  try {
    state.data = await fn()
    return true
  } catch (e) {
    toast(e instanceof ApiError ? e.message : String(e), 'error')
    return false
  } finally {
    state.busy = false
  }
}
