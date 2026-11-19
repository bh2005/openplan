const DAY = 86400000

/** ISO-Datum -> UTC-Millisekunden (Mitternacht) */
export const ms = (s: string) => {
  const [y, m, d] = s.slice(0, 10).split('-').map(Number)
  return Date.UTC(y, m - 1, d)
}
export const iso = (t: number) => new Date(t).toISOString().slice(0, 10)
export const dayDiff = (a: string, b: string) => Math.round((ms(b) - ms(a)) / DAY)
export const addDays = (s: string, n: number) => iso(ms(s) + n * DAY)
export const todayIso = () => {
  const d = new Date()
  return iso(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))
}
/** 0=Mo … 6=So (wie Python) */
export const weekday = (s: string) => (new Date(ms(s)).getUTCDay() + 6) % 7

export const fmt = (s: string | null | undefined) => {
  if (!s) return ''
  const [y, m, d] = s.slice(0, 10).split('-')
  return `${d}.${m}.${y.slice(2)}`
}
/** DD.MM.YY(YY) oder ISO -> ISO, sonst null */
export const parseDate = (s: string): string | null => {
  s = s.trim()
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s
  const m = s.match(/^(\d{1,2})\.(\d{1,2})\.(\d{2}|\d{4})$/)
  if (!m) return null
  const y = m[3].length === 2 ? 2000 + Number(m[3]) : Number(m[3])
  return iso(Date.UTC(y, Number(m[2]) - 1, Number(m[1])))
}

export class WorkCal {
  days: Set<number>
  hol: Set<string>
  constructor(workDays: number[], holidays: string[]) {
    this.days = new Set(workDays)
    this.hol = new Set(holidays)
  }
  isWork(s: string) { return this.days.has(weekday(s)) && !this.hol.has(s) }
  /** Arbeitstage im geschlossenen Intervall [a, b] */
  count(a: string, b: string) {
    let n = 0
    for (let t = ms(a); t <= ms(b); t += DAY) if (this.isWork(iso(t))) n++
    return n
  }
}
