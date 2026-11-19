// Gantt als eigenständiges SVG für Folien/PDF: unabhängig von der Bildschirmansicht (immer hell, feste Seitenformate,
// Phasen-/Management-Ansicht, Seitenumbruch). Die Seiten sind reine SVG-Strings und lassen sich als PNG/SVG/PDF ausgeben.
import { addDays, dayDiff, fmt, todayIso, weekday, WorkCal } from './dates'
import { monthShort, t as tr } from './i18n'
import { isoWeek } from './timeline'
import type { Dep, Task } from './types'

export type Scope = 'all' | 'phases' | 'critical'
export type Col = 'wbs' | 'name' | 'start' | 'finish' | 'duration' | 'percent' | 'status' | 'resources'
export type PageFmt = 'slide' | 'a4' | 'a3' | 'auto'

export interface GanttExportOptions {
  scope: Scope
  maxLevel: number            // bei „phases“: Sammelvorgänge bis zu dieser Ebene (1 = nur oberste)
  from: string                // '' = automatisch
  to: string
  cols: Col[]
  title: string
  subtitle: string
  fmt: PageFmt
  showToday: boolean
  showBaseline: boolean
  showCritical: boolean
  showDeps: boolean
  showLegend: boolean
  barLabels: boolean          // Name (und Datum) am Balken
}
export interface GanttExportInput {
  tasks: Task[]
  deps: Dep[]
  cal: WorkCal
  resourceNames: Record<number, string>
  statusLabel: (s: string) => string
}
export interface Built { pages: string[]; width: number; height: number; rows: number; days: number }

/** Seitengrößen in CSS-Pixeln (96 dpi), jeweils quer; Folie = 16:9. */
export const PAGE: Record<Exclude<PageFmt, 'auto'>, { w: number; h: number; mm: [number, number] }> = {
  slide: { w: 1600, h: 900, mm: [338.67, 190.5] },
  a4: { w: 1123, h: 794, mm: [297, 210] },
  a3: { w: 1587, h: 1123, mm: [420, 297] },
}

const FONT = "'Segoe UI', 'Helvetica Neue', Arial, sans-serif"
const C = { bar: '#3b82f6', done: '#93c5fd', crit: '#dc2626', sum: '#1f2937', ms: '#7c3aed', blocked: '#d97706', grid: '#e2e8f0', head: '#f1f5f9',
  text: '#0f172a', dim: '#64748b', off: '#f1f5f9', today: '#dc2626', base: '#94a3b8', zebra: '#f8fafc' }
const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
const cut = (s: string, w: number, fs: number) => { const n = Math.max(3, Math.floor(w / (fs * 0.52))); return s.length > n ? s.slice(0, n - 1) + '…' : s }

export const colLabel = (c: Col) => ({ wbs: tr('PSP'), name: tr('Vorgang'), start: tr('Beginn'), finish: tr('Ende'), duration: tr('Dauer'), percent: '%', status: tr('Status'), resources: tr('Ressourcen') })[c]
const colWidth = (c: Col) => ({ wbs: 44, name: 0, start: 74, finish: 74, duration: 50, percent: 40, status: 76, resources: 130 })[c]

function pickRows(tasks: Task[], o: GanttExportOptions): Task[] {
  if (o.scope === 'phases') return tasks.filter(t => t.milestone || (t.summary && t.level < o.maxLevel))
  if (o.scope === 'critical') {
    const keep = new Set<number>()
    const parent = new Map(tasks.map(t => [t.id, t.parent_id]))
    for (const t of tasks) if (!t.summary && t.critical) for (let c: number | null = t.id; c != null && !keep.has(c); c = parent.get(c) ?? null) keep.add(c)
    return tasks.filter(t => keep.has(t.id))
  }
  return tasks
}

interface Cell { x: number; w: number; label: string }
function header(origin: string, days: number, px: number): { top: Cell[]; bot: Cell[] } {
  const top: Cell[] = [], bot: Cell[] = []
  const years = px < 1.6
  let key = '', start = 0, last = ''
  for (let i = 0; i < days; i++) {
    const d = addDays(origin, i)
    const k = years ? d.slice(0, 4) : d.slice(0, 7)
    if (k !== key) { if (key) top.push({ x: start * px, w: (i - start) * px, label: last }); key = k; start = i }
    last = years ? d.slice(0, 4) : `${monthShort(Number(d.slice(5, 7)) - 1)} ${d.slice(0, 4)}`
    if (px >= 16) bot.push({ x: i * px, w: px, label: String(Number(d.slice(8))) })
    else if (px >= 3.2) { if (weekday(d) === 0 || i === 0) bot.push({ x: i * px, w: 7 * px, label: tr('KW') + isoWeek(d) }) }
    else if (d.slice(8) === '01' || i === 0) bot.push({ x: i * px, w: 30 * px, label: monthShort(Number(d.slice(5, 7)) - 1) })
  }
  if (key) top.push({ x: start * px, w: (days - start) * px, label: last })
  return { top, bot }
}

export function buildGanttPages(inp: GanttExportInput, o: GanttExportOptions): Built {
  const rowsAll = pickRows(inp.tasks, o)
  const today = todayIso()
  const MARGIN = 28, TITLE_H = 58, HEAD_H = 40, LEGEND_H = o.showLegend ? 30 : 0, FOOT_H = 22
  // ── Zeitraum ──
  let lo = rowsAll.length ? rowsAll[0].start : today, hi = rowsAll.length ? rowsAll[0].finish : today
  for (const t of rowsAll) {
    lo = t.start < lo ? t.start : lo; hi = t.finish > hi ? t.finish : hi
    if (o.showBaseline && t.baseline_start) { lo = t.baseline_start < lo ? t.baseline_start : lo; hi = (t.baseline_finish ?? hi) > hi ? (t.baseline_finish ?? hi) : hi }
  }
  const origin = o.from || addDays(lo, -2), end = o.to || addDays(hi, 3)
  const days = Math.max(dayDiff(origin, end) + 1, 7)
  // ── Spalten ──
  const cols = o.cols.length ? o.cols : (['name'] as Col[])
  const fixedW = cols.filter(c => c !== 'name').reduce((a, c) => a + colWidth(c), 0)
  const page = o.fmt === 'auto' ? null : PAGE[o.fmt]
  const longest = rowsAll.reduce((m, t) => Math.max(m, t.name.length + t.level * 2), 8)
  let nameW = cols.includes('name') ? Math.min(Math.max(longest * 6.6 + 14, 150), page ? page.w * 0.3 : 360) : 0
  if (cols.includes('name') && page && fixedW + nameW > page.w * 0.55) nameW = Math.max(120, page.w * 0.55 - fixedW)
  const tableW = fixedW + nameW
  // ── Seite / Maßstab ──
  const pageW = page ? page.w : 0
  const px = page ? Math.max((pageW - 2 * MARGIN - tableW) / days, 0.4) : days <= 120 ? 14 : days <= 400 ? 5 : 2
  const innerW = tableW + days * px
  const width = page ? page.w : Math.ceil(innerW + 2 * MARGIN)
  // ── Zeilen je Seite ──
  const chrome = MARGIN * 2 + TITLE_H + HEAD_H + LEGEND_H + FOOT_H
  let rowH = 26, perPage = rowsAll.length || 1
  if (page) {
    const avail = page.h - chrome
    const fit = Math.floor(avail / Math.max(rowsAll.length, 1))
    if (fit >= 18) rowH = Math.min(fit, 32)
    else { rowH = 22; perPage = Math.max(1, Math.floor(avail / rowH)) }
  }
  const nPages = Math.max(1, Math.ceil(rowsAll.length / perPage))
  const fs = Math.min(13, Math.max(9, rowH * 0.5))
  const hdr = header(origin, days, px)
  const X = (d: string) => (dayDiff(origin, d)) * px
  const offDays: number[] = []
  if (px >= 4) for (let i = 0; i < days; i++) if (!inp.cal.isWork(addDays(origin, i))) offDays.push(i)
  const bodyH = (n: number) => n * rowH
  const height = page ? page.h : Math.ceil(chrome + bodyH(rowsAll.length))
  const x0 = MARGIN + tableW                        // Beginn der Zeitachse
  const cellText = (t: Task, c: Col) => c === 'wbs' ? t.wbs : c === 'start' ? (t.milestone ? '' : fmt(t.start)) : c === 'finish' ? fmt(t.finish)
    : c === 'duration' ? (t.milestone ? '◆' : t.duration + ' T') : c === 'percent' ? Math.round(t.percent) + '%'
    : c === 'status' ? inp.statusLabel(t.status) : c === 'resources' ? t.resource_ids.map(r => inp.resourceNames[r] ?? '').filter(Boolean).join(', ') : t.name

  const pages: string[] = []
  for (let p = 0; p < nPages; p++) {
    const rows = rowsAll.slice(p * perPage, (p + 1) * perPage)
    const yTop = MARGIN + TITLE_H + HEAD_H                      // erste Datenzeile
    const idx = new Map(rows.map((t, i) => [t.id, i]))
    const yc = (i: number) => yTop + i * rowH + rowH / 2
    const bodyBottom = yTop + bodyH(rows.length)
    const out: string[] = []
    out.push(`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" font-family="${FONT}" font-size="${fs}">`)
    out.push(`<defs><clipPath id="clip${p}"><rect x="${x0}" y="${MARGIN + TITLE_H}" width="${days * px}" height="${HEAD_H + bodyH(rows.length)}"/></clipPath></defs>`)
    out.push(`<rect width="${width}" height="${height}" fill="#ffffff"/>`)
    // Titel
    out.push(`<text x="${MARGIN}" y="${MARGIN + 22}" font-size="24" font-weight="700" fill="${C.text}">${esc(o.title)}</text>`)
    if (o.subtitle) out.push(`<text x="${MARGIN}" y="${MARGIN + 44}" font-size="13" fill="${C.dim}">${esc(o.subtitle)}</text>`)
    if (nPages > 1) out.push(`<text x="${width - MARGIN}" y="${MARGIN + 22}" font-size="12" fill="${C.dim}" text-anchor="end">${tr('Seite')} ${p + 1} / ${nPages}</text>`)
    // Kopf
    out.push(`<rect x="${MARGIN}" y="${MARGIN + TITLE_H}" width="${tableW + days * px}" height="${HEAD_H}" fill="${C.head}"/>`)
    let cx = MARGIN
    for (const c of cols) {
      const w = c === 'name' ? nameW : colWidth(c)
      out.push(`<text x="${cx + 6}" y="${MARGIN + TITLE_H + HEAD_H - 12}" font-weight="600" fill="${C.dim}" font-size="${Math.min(fs, 12)}">${esc(colLabel(c))}</text>`)
      cx += w
    }
    const th = MARGIN + TITLE_H
    out.push(`<g clip-path="url(#clip${p})">`)
    for (const c of hdr.top) {
      out.push(`<line x1="${x0 + c.x}" x2="${x0 + c.x}" y1="${th}" y2="${bodyBottom}" stroke="${C.grid}"/>`)
      if (c.w > c.label.length * 6.5 + 6) out.push(`<text x="${x0 + c.x + 4}" y="${th + 15}" fill="${C.dim}" font-size="11">${esc(c.label)}</text>`)
    }
    for (const c of hdr.bot) {
      if (px >= 16 || c.w > 18) out.push(`<text x="${x0 + c.x + (px >= 16 ? c.w / 2 : 3)}" y="${th + 33}" fill="${C.dim}" font-size="10" ${px >= 16 ? 'text-anchor="middle"' : ''}>${esc(c.label)}</text>`)
      if (px >= 3.2) out.push(`<line x1="${x0 + c.x}" x2="${x0 + c.x}" y1="${th + 20}" y2="${bodyBottom}" stroke="${C.grid}" stroke-opacity=".6"/>`)
    }
    for (const i of offDays) out.push(`<rect x="${x0 + i * px}" y="${yTop}" width="${px}" height="${bodyH(rows.length)}" fill="${C.off}"/>`)
    out.push('</g>')
    // Zeilen + Tabelle
    rows.forEach((t, i) => {
      const y = yTop + i * rowH
      if (i % 2 === 1) out.push(`<rect x="${MARGIN}" y="${y}" width="${tableW}" height="${rowH}" fill="${C.zebra}"/>`)
      out.push(`<line x1="${MARGIN}" x2="${x0 + days * px}" y1="${y + rowH}" y2="${y + rowH}" stroke="${C.grid}"/>`)
      let tx = MARGIN
      for (const c of cols) {
        const w = c === 'name' ? nameW : colWidth(c)
        const indent = c === 'name' ? t.level * 12 : 0
        const bold = t.summary && (c === 'name' || c === 'wbs')
        const color = t.critical && o.showCritical && !t.summary && c === 'name' ? C.crit : C.text
        out.push(`<text x="${tx + 6 + indent}" y="${y + rowH / 2 + fs * 0.35}" fill="${color}" ${bold ? 'font-weight="700"' : ''}>${esc(cut(cellText(t, c), w - 10 - indent, fs))}</text>`)
        tx += w
      }
    })
    // Balken
    out.push(`<g clip-path="url(#clip${p})">`)
    if (o.showToday && today >= origin && today <= end) out.push(`<line x1="${x0 + X(today) + px / 2}" x2="${x0 + X(today) + px / 2}" y1="${th + HEAD_H - 4}" y2="${bodyBottom}" stroke="${C.today}" stroke-width="1.5" stroke-dasharray="5 3"/>`)
    const BH = Math.max(8, Math.round(rowH * 0.5))
    const xs = (t: Task) => x0 + X(t.start), xe = (t: Task) => x0 + X(t.finish) + px
    const label = (t: Task, i: number, xr: number) => {
      if (!o.barLabels) return
      const txt = (t.milestone ? fmt(t.finish) + '  ' : '') + t.name + (t.summary ? '  ' + fmt(t.start) + ' – ' + fmt(t.finish) : '')
      const room = x0 + days * px - xr - 8
      if (room >= Math.min(txt.length * (fs - 1) * 0.52 + 8, 260)) out.push(`<text x="${xr + 6}" y="${yc(i) + fs * 0.35}" fill="${C.text}" font-size="${Math.max(9, fs - 1)}">${esc(cut(txt, room, fs - 1))}</text>`)
      else out.push(`<text x="${xs(t) - 6}" y="${yc(i) + fs * 0.35}" text-anchor="end" fill="${C.text}" font-size="${Math.max(9, fs - 1)}">${esc(cut(txt, xs(t) - x0 - 8, fs - 1))}</text>`)
    }
    rows.forEach((t, i) => {
      const y = yc(i)
      if (o.showBaseline && t.baseline_start && t.baseline_finish && !t.milestone)
        out.push(`<rect x="${x0 + X(t.baseline_start)}" y="${y + BH / 2 + 1}" width="${Math.max(x0 + X(t.baseline_finish) + px - (x0 + X(t.baseline_start)), 2)}" height="3" rx="1" fill="${C.base}"/>`)
      if (t.milestone) {
        const cxm = xe(t), r = Math.max(6, BH * 0.7)
        out.push(`<path d="M${cxm},${y - r} L${cxm + r},${y} L${cxm},${y + r} L${cxm - r},${y} z" fill="${o.showCritical && t.critical ? C.crit : C.ms}"/>`)
        label(t, i, cxm + r)
      } else if (t.summary) {
        const a = xs(t), b = xe(t), h = Math.max(5, BH * 0.55)
        out.push(`<path d="M${a},${y - h} H${b} V${y + h - 1} L${b - 5},${y + 1} H${a + 5} L${a},${y + h - 1} z" fill="${C.sum}"/>`)
        label(t, i, b)
      } else {
        const a = xs(t), w = Math.max(xe(t) - a, 3)
        const fill = t.status === 'done' ? C.done : o.showCritical && t.critical ? C.crit : C.bar
        out.push(`<rect x="${a}" y="${y - BH / 2}" width="${w}" height="${BH}" rx="3" fill="${fill}" ${t.status === 'blocked' ? `stroke="${C.blocked}" stroke-width="2" stroke-dasharray="4 2"` : ''}/>`)
        if (t.percent > 0) out.push(`<rect x="${a}" y="${y - 2}" width="${w * t.percent / 100}" height="4" rx="2" fill="#000" fill-opacity=".35"/>`)
        label(t, i, a + w)
      }
    })
    if (o.showDeps) {
      out.push(`<defs><marker id="arr${p}" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#64748b"/></marker></defs>`)
      const byId = new Map(rows.map(t => [t.id, t]))
      for (const dep of inp.deps) {
        const a = byId.get(dep.pred_id), b = byId.get(dep.succ_id)
        if (!a || !b) continue
        const y1 = yc(idx.get(a.id)!), y2 = yc(idx.get(b.id)!), dir = y2 > y1 ? 1 : -1, ym = y1 + dir * rowH / 2
        const aS = a.milestone ? xe(a) : xs(a), aE = xe(a), bS = b.milestone ? xe(b) : xs(b), bE = xe(b)
        let d: string
        if (dep.type === 'FS') d = bS >= aE + 12 ? `M${aE},${y1} H${aE + 6} V${y2} H${bS - 1}` : `M${aE},${y1} H${aE + 6} V${ym} H${bS - 8} V${y2} H${bS - 1}`
        else if (dep.type === 'SS') d = `M${aS},${y1} H${Math.min(aS, bS) - 8} V${y2} H${bS - 1}`
        else if (dep.type === 'FF') d = `M${aE},${y1} H${Math.max(aE, bE) + 8} V${y2} H${bE + 1}`
        else d = `M${aS},${y1} H${aS - 8} V${ym} H${bE + 8} V${y2} H${bE + 1}`
        const crit = o.showCritical && a.critical && b.critical && !a.summary && !b.summary
        out.push(`<path d="${d}" fill="none" stroke="${crit ? C.crit : '#64748b'}" stroke-width="1" marker-end="url(#arr${p})"/>`)
      }
    }
    out.push('</g>')
    out.push(`<line x1="${x0}" x2="${x0}" y1="${th}" y2="${bodyBottom}" stroke="#cbd5e1"/>`)
    out.push(`<rect x="${MARGIN}" y="${th}" width="${tableW + days * px}" height="${bodyBottom - th}" fill="none" stroke="#cbd5e1"/>`)
    // Legende + Fuß
    const ly = height - MARGIN / 2 - FOOT_H - (o.showLegend ? 6 : 0)
    if (o.showLegend) {
      let lx = MARGIN
      const item = (shape: (x: number) => string, text: string) => { out.push(shape(lx)); out.push(`<text x="${lx + 22}" y="${ly + 4}" font-size="11" fill="${C.dim}">${esc(text)}</text>`); lx += 36 + text.length * 6.2 }
      item(x => `<rect x="${x}" y="${ly - 1}" width="16" height="9" rx="2" fill="${C.bar}"/>`, tr('Vorgang'))
      if (o.showCritical) item(x => `<rect x="${x}" y="${ly - 1}" width="16" height="9" rx="2" fill="${C.crit}"/>`, tr('Kritischer Pfad'))
      item(x => `<path d="M${x},${ly - 1} h16 l-3,9 h-10 z" fill="${C.sum}"/>`, tr('Sammelvorgang'))
      item(x => `<path d="M${x},${ly + 4} l6,-5 l6,5 l-6,5 z" fill="${C.ms}"/>`, tr('Meilenstein'))
      if (o.showBaseline) item(x => `<rect x="${x}" y="${ly + 2}" width="16" height="3" rx="1" fill="${C.base}"/>`, tr('Basisplan'))
      if (o.showToday) item(x => `<line x1="${x}" x2="${x + 16}" y1="${ly + 4}" y2="${ly + 4}" stroke="${C.today}" stroke-width="1.5" stroke-dasharray="4 2"/>`, tr('Heute'))
    }
    out.push(`<text x="${width - MARGIN}" y="${height - MARGIN / 2}" text-anchor="end" font-size="10" fill="${C.dim}">${tr('Stand')} ${fmt(today)} · OpenPlan</text>`)
    out.push('</svg>')
    pages.push(out.join('\n'))
  }
  return { pages, width, height, rows: rowsAll.length, days }
}
