import { addDays, dayDiff } from './dates'
import { t as tr } from './i18n'
import type { Absence } from './types'

export const ABSENCE_KINDS: Absence['kind'][] = ['vacation', 'training', 'sick', 'other']
export const kindLabel = (k: Absence['kind']) =>
  ({ vacation: tr('Urlaub'), training: tr('Schulung'), sick: tr('Krank'), other: tr('Sonstiges') })[k]
export const kindIcon = (k: Absence['kind']) => ({ vacation: '🏖', training: '🎓', sick: '🤒', other: '•' })[k]

/** Abwesenheiten, die den Zeitraum [from, to] berühren (Tage inklusive). */
export function inRange(abs: Absence[], from: string, to: string): Absence[] {
  return abs.filter(a => a.start_date <= to && a.end_date >= from)
}

/** Ressource -> Menge der abwesenden Tage innerhalb [from, to]. */
export function absentDays(abs: Absence[], from: string, to: string): Map<number, Set<string>> {
  const out = new Map<number, Set<string>>()
  for (const a of inRange(abs, from, to)) {
    const s = a.start_date < from ? from : a.start_date, e = a.end_date > to ? to : a.end_date
    let set = out.get(a.resource_id)
    if (!set) out.set(a.resource_id, (set = new Set()))
    for (let i = 0, n = dayDiff(s, e); i <= n; i++) set.add(addDays(s, i))
  }
  return out
}
