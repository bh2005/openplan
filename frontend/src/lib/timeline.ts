import { addDays, ms, weekday } from './dates'
import { monthShort, t as tr } from './i18n'

export type Zoom = 'day' | 'week' | 'month'
export const PX: Record<Zoom, number> = { day: 28, week: 10, month: 3.2 }
export interface HCell { x: number; w: number; label: string }


export function isoWeek(d: string): number {
  const t = new Date(ms(d))
  const day = (t.getUTCDay() + 6) % 7
  t.setUTCDate(t.getUTCDate() - day + 3)
  const first = new Date(Date.UTC(t.getUTCFullYear(), 0, 4))
  return 1 + Math.round(((t.getTime() - first.getTime()) / 86400000 - 3 + ((first.getUTCDay() + 6) % 7)) / 7)
}

/** Zweizeiliger Kopf (oben Monat/Jahr, unten Tag/KW/Monat) für eine Zeitachse ab `origin`. */
export function buildHeader(origin: string, totalDays: number, zoom: Zoom): { top: HCell[]; bot: HCell[] } {
  const px = PX[zoom]
  const top: HCell[] = []
  const bot: HCell[] = []
  let curKey = ''
  let start = 0
  let lastLabel = ''
  for (let i = 0; i < totalDays; i++) {
    const d = addDays(origin, i)
    const key = zoom === 'month' ? d.slice(0, 4) : d.slice(0, 7)
    const label = zoom === 'month' ? d.slice(0, 4) : `${monthShort(Number(d.slice(5, 7)) - 1)} ${d.slice(0, 4)}`
    if (key !== curKey) {
      if (curKey) top.push({ x: start * px, w: (i - start) * px, label: lastLabel })
      curKey = key
      start = i
    }
    lastLabel = label
    if (zoom === 'day') bot.push({ x: i * px, w: px, label: String(Number(d.slice(8))) })
    else if (zoom === 'week' && weekday(d) === 0) bot.push({ x: i * px, w: 7 * px, label: tr('KW') + isoWeek(d) })
    else if (zoom === 'month' && d.slice(8) === '01') bot.push({ x: i * px, w: 30 * px, label: monthShort(Number(d.slice(5, 7)) - 1) })
  }
  if (curKey) top.push({ x: start * px, w: (totalDays - start) * px, label: lastLabel })
  return { top, bot }
}
