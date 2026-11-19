import { reactive } from 'vue'
import { api, ApiError } from './api'
import { toast } from './store'
import type { Budget, Finance } from './types'
import { locale } from './i18n'

export const fin = reactive({
  pid: 0,
  data: null as Finance | null,
  budget: null as Budget | null,
  loading: false,
})

const fmts = new Map<string, Intl.NumberFormat>()
const nfor = (key: string, o: Intl.NumberFormatOptions) => {
  const k = locale() + key
  let f = fmts.get(k)
  if (!f) { f = new Intl.NumberFormat(locale(), o); fmts.set(k, f) }
  return f
}
export const eur = (v: number | null | undefined) => (v == null ? '–' : nfor('c', { style: 'currency', currency: 'EUR' }).format(v))
export const eur0 = (v: number | null | undefined) => (v == null ? '–' : nfor('0', { maximumFractionDigits: 0 }).format(v) + ' €')
export const idx = (v: number | null | undefined) => (v == null ? '–' : nfor('i', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v))
/** Zahleneingabe "1.234,56" / "1234.5" -> number (NaN bei Fehler) */
export const parseNum = (s: string) => {
  let t = s.trim().replace(/\s/g, '')
  if (t.includes(',') && t.includes('.')) t = t.lastIndexOf(',') > t.lastIndexOf('.') ? t.replace(/\./g, '').replace(',', '.') : t.replace(/,/g, '')
  else if (t.includes(',')) t = t.replace(',', '.')
  return t === '' ? NaN : Number(t)
}

export async function loadFinance(pid: number) {
  fin.pid = pid
  try { fin.data = await api.finance(pid) } catch (e) { toast((e as Error).message, 'error') }
}
export async function loadBudget(pid: number) {
  fin.loading = true
  try { fin.budget = await api.budget(pid) } catch (e) { toast((e as Error).message, 'error') } finally { fin.loading = false }
}
/** Mutation, die ein Finance-Objekt liefert; danach Budget neu berechnen. */
export async function finMutate(pid: number, fn: () => Promise<Finance | unknown>): Promise<boolean> {
  try {
    const r = await fn()
    if (r && typeof r === 'object' && 'cost_centers' in r) fin.data = r as Finance
    else await loadFinance(pid)
    await loadBudget(pid)
    return true
  } catch (e) {
    toast(e instanceof ApiError ? e.message : String(e), 'error')
    return false
  }
}
export const label = (list: { id: number; code: string; name: string }[] | undefined, id: number | null | undefined, empty = '–') => {
  const m = list?.find(x => x.id === id)
  return m ? (m.name ? `${m.code} ${m.name}` : m.code) : empty
}
export async function downloadBlob(blob: Blob, name: string) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = name
  a.click()
  URL.revokeObjectURL(a.href)
}
