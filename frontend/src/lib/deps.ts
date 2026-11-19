import type { Dep, DepType, Task } from './types'
import { lang, t as tr } from './i18n'

/** Anzeige-Kürzel (deutsch, wie MS Project DE) */
export const DE: Record<DepType, string> = { FS: 'EA', SS: 'AA', FF: 'EE', SF: 'AE' }
const FROM_TXT: Record<string, DepType> = { FS: 'FS', SS: 'SS', FF: 'FF', SF: 'SF', EA: 'FS', AA: 'SS', EE: 'FF', AE: 'SF' }

export function depToText(d: Dep, wbs: (id: number) => string | undefined): string {
  const en = lang.value === 'en'                      // englisch: FS/SS/FF/SF und D (days), deutsch: EA/AA/EE/AE und T
  const lag = d.lag ? (d.lag > 0 ? '+' : '') + d.lag + (en ? 'D' : 'T') : ''
  return `${wbs(d.pred_id) ?? '?'}${d.type === 'FS' && !lag ? '' : en ? d.type : DE[d.type]}${lag}`
}

/** "1.2, 3AA+2T, 4EE-1" -> Vorgänger-Liste; wirft bei Fehlern */
export function parsePreds(text: string, tasks: Task[]): { pred_id: number; type: DepType; lag: number }[] {
  const byWbs = new Map(tasks.map(t => [t.wbs, t.id]))
  const out: { pred_id: number; type: DepType; lag: number }[] = []
  for (const part of text.split(/[;,]/).map(s => s.trim()).filter(Boolean)) {
    const m = part.match(/^(\d+(?:\.\d+)*)\s*(FS|SS|FF|SF|EA|AA|EE|AE)?\s*(?:([+-])\s*(\d+)\s*[tTdD]?)?$/i)
    if (!m) throw new Error(tr('Ungültiger Vorgänger: "{1}" (Beispiel: 3, 4AA+2T, 5EE-1T)', { 1: part }))
    const id = byWbs.get(m[1])
    if (id === undefined) throw new Error(tr('PSP-Nr. {1} existiert nicht', { 1: m[1] }))
    out.push({
      pred_id: id,
      type: m[2] ? FROM_TXT[m[2].toUpperCase()] : 'FS',
      lag: m[3] ? Number(m[4]) * (m[3] === '-' ? -1 : 1) : 0,
    })
  }
  return out
}
