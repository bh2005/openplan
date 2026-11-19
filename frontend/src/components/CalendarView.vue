<script setup lang="ts">
import { computed, ref } from 'vue'
import { addDays, dayDiff, fmt, todayIso, weekday, WorkCal } from '../lib/dates'
import { isoWeek } from '../lib/timeline'
import { STATUS_LABEL } from '../lib/status'
import { inRange, kindIcon, kindLabel } from '../lib/absence'
import type { Absence, Assignment, Resource, Task } from '../lib/types'
import { t as tr, monthLong, monthShort, weekdayShort } from '../lib/i18n'

const props = defineProps<{ tasks: Task[]; resources: Resource[]; assignments: Assignment[]; absences: Absence[]; cal: WorkCal }>()
const emit = defineEmits<{ (e: 'open', id: number): void }>()

type View = 'month' | 'week' | 'year' | 'list'
const view = ref<View>('month')
const cursor = ref(todayIso())            // beliebiger Tag im angezeigten Zeitraum
const resFilter = ref(0)
const showSummary = ref(false)
const hideDone = ref(false)

const WD = () => [0, 1, 2, 3, 4, 5, 6].map(weekdayShort)
const monday = (d: string) => addDays(d, -weekday(d))
const monthStart = (d: string) => d.slice(0, 8) + '01'
const monthEnd = (d: string) => { const [y, m] = d.split('-').map(Number); return addDays(new Date(Date.UTC(y, m, 1)).toISOString().slice(0, 10), -1) }

const title = computed(() => view.value === 'week'
  ? `${tr('KW')} ${isoWeek(cursor.value)} · ${fmt(monday(cursor.value))} – ${fmt(addDays(monday(cursor.value), 6))}`
  : view.value === 'year' ? cursor.value.slice(0, 4)
  : `${monthLong(Number(cursor.value.slice(5, 7)) - 1)} ${cursor.value.slice(0, 4)}`)
function nav(dir: -1 | 1) {
  if (view.value === 'week') cursor.value = addDays(cursor.value, 7 * dir)
  else if (view.value === 'year') cursor.value = `${Number(cursor.value.slice(0, 4)) + dir}${cursor.value.slice(4)}`
  else {
    const [y, m] = cursor.value.split('-').map(Number)
    cursor.value = new Date(Date.UTC(y, m - 1 + dir, 1)).toISOString().slice(0, 10)
  }
}

// Zeitraum (inkl. Randtage der Wochen)
const range = computed(() => view.value === 'week'
  ? { from: monday(cursor.value), to: addDays(monday(cursor.value), 6) }
  : { from: monday(monthStart(cursor.value)), to: addDays(monday(monthEnd(cursor.value)), 6) })

const visible = computed(() => {
  const resTasks = resFilter.value ? new Set(props.assignments.filter(a => a.resource_id === resFilter.value).map(a => a.task_id)) : null
  return props.tasks.filter(t =>
    (showSummary.value || !t.summary) && (!resTasks || resTasks.has(t.id)) && !(hideDone.value && t.status === 'done') &&
    t.start <= range.value.to && t.finish >= range.value.from)
})
const resNames = computed(() => {
  const m = new Map<number, string>()
  for (const r of props.resources) m.set(r.id, r.name)
  const by = new Map<number, string[]>()
  for (const a of props.assignments) by.set(a.task_id, [...(by.get(a.task_id) ?? []), m.get(a.resource_id) ?? '?'])
  return by
})

// ── Wochenzeilen mit Spuren (greedy Lane-Zuweisung) ───────────────────────
interface Seg { t: Task; c0: number; c1: number; lane: number; contL: boolean; contR: boolean }
interface Week { start: string; days: string[]; segs: Seg[]; lanes: number }
const weeks = computed<Week[]>(() => {
  const out: Week[] = []
  const n = dayDiff(range.value.from, range.value.to) + 1
  for (let w = 0; w < n / 7; w++) {
    const start = addDays(range.value.from, w * 7), end = addDays(start, 6)
    const items = visible.value.filter(t => t.start <= end && t.finish >= start)
      .sort((a, b) => (a.start < b.start ? -1 : a.start > b.start ? 1 : dayDiff(b.start, b.finish) - dayDiff(a.start, a.finish)))
    const laneEnd: number[] = []
    const segs: Seg[] = []
    for (const t of items) {
      const c0 = Math.max(dayDiff(start, t.start), 0), c1 = Math.min(dayDiff(start, t.finish), 6)
      let lane = laneEnd.findIndex(e => e < c0)
      if (lane < 0) { lane = laneEnd.length; laneEnd.push(c1) } else laneEnd[lane] = c1
      segs.push({ t, c0, c1, lane, contL: t.start < start, contR: t.finish > end })
    }
    out.push({ start, days: Array.from({ length: 7 }, (_, i) => addDays(start, i)), segs, lanes: laneEnd.length })
  }
  return out
})
const today = todayIso()

// ── Abwesenheiten (der Filter „Ressource" gilt auch hier) ───────────────────
const absList = computed(() => (resFilter.value ? props.absences.filter(a => a.resource_id === resFilter.value) : props.absences))
const rname = (id: number) => props.resources.find(r => r.id === id)?.name ?? '?'
const absByDay = computed(() => {                       // Tag -> Abwesenheiten, nur für den sichtbaren Zeitraum
  const from = view.value === 'year' ? `${cursor.value.slice(0, 4)}-01-01` : range.value.from
  const to = view.value === 'year' ? `${cursor.value.slice(0, 4)}-12-31` : range.value.to
  const m = new Map<string, Absence[]>()
  for (const a of inRange(absList.value, from, to)) {
    const s = a.start_date < from ? from : a.start_date, e = a.end_date > to ? to : a.end_date
    for (let i = 0, n = dayDiff(s, e); i <= n; i++) { const d = addDays(s, i); m.set(d, [...(m.get(d) ?? []), a]) }
  }
  return m
})
const absOn = (d: string) => (props.cal.isWork(d) ? absByDay.value.get(d) ?? [] : [])
const absTip = (d: string) => absOn(d).map(a => `${kindIcon(a.kind)} ${rname(a.resource_id)}: ${kindLabel(a.kind)}${a.note ? ' – ' + a.note : ''}`).join('\n')

// ── Jahresübersicht ───────────────────────────────────────────────────────
const yearNo = computed(() => Number(cursor.value.slice(0, 4)))
const taskScope = computed(() => {
  const set = resFilter.value ? new Set(props.assignments.filter(a => a.resource_id === resFilter.value).map(a => a.task_id)) : null
  return props.tasks.filter(t => !t.summary && (!set || set.has(t.id)) && !(hideDone.value && t.status === 'done'))
})
const marks = computed(() => {                          // Tag -> Meilensteine (◆) und Fristen (⚑)
  const m = new Map<string, { ms: Task[]; dl: Task[] }>()
  const slot = (d: string) => { let v = m.get(d); if (!v) m.set(d, (v = { ms: [], dl: [] })); return v }
  for (const t of taskScope.value) {
    if (t.milestone) slot(t.start).ms.push(t)
    else if (t.deadline) slot(t.deadline).dl.push(t)
  }
  return m
})
const months = computed(() => Array.from({ length: 12 }, (_, mi) => {
  const first = `${yearNo.value}-${String(mi + 1).padStart(2, '0')}-01`
  const lead = weekday(first), len = Number(monthEnd(first).slice(8))
  return { mi, first, lead, days: Array.from({ length: len }, (_, i) => addDays(first, i)) }
}))
const dayTip = (d: string) => {
  const parts = [fmt(d) + (props.cal.isWork(d) ? '' : ' · ' + tr('frei'))]
  const a = absTip(d); if (a) parts.push(a)
  const k = marks.value.get(d)
  for (const t of k?.ms ?? []) parts.push('◆ ' + t.name)
  for (const t of k?.dl ?? []) parts.push('⚑ ' + tr('Frist') + ': ' + t.name)
  return parts.join('\n')
}
const absShade = (d: string) => {
  const n = new Set(absOn(d).map(a => a.resource_id)).size
  return n ? `color-mix(in srgb, var(--accent) ${Math.min(22 + n * 20, 80)}%, transparent)` : undefined
}
function pickDay(d: string) { cursor.value = d; view.value = 'month' }
const LANE = computed(() => (view.value === 'week' ? 26 : 20))
const color = (t: Task) => (t.summary ? 'var(--bar-summary)' : t.milestone ? 'var(--bar-ms)' : t.critical ? 'var(--bar-critical)' : 'var(--bar)')
const tip = (t: Task) => `${t.wbs} ${t.name}\n${fmt(t.start)} – ${fmt(t.finish)} · ${t.percent}%` + (resNames.value.get(t.id) ? '\n' + resNames.value.get(t.id)!.join(', ') : '')

// ── Liste ─────────────────────────────────────────────────────────────────
const list = computed(() => {
  const from = view.value === 'list' ? monthStart(cursor.value) : range.value.from
  const to = view.value === 'list' ? monthEnd(cursor.value) : range.value.to
  const resTasks = resFilter.value ? new Set(props.assignments.filter(a => a.resource_id === resFilter.value).map(a => a.task_id)) : null
  return props.tasks.filter(t => (showSummary.value || !t.summary) && (!resTasks || resTasks.has(t.id)) && !(hideDone.value && t.status === 'done') &&
    t.start <= to && t.finish >= from).sort((a, b) => (a.start < b.start ? -1 : a.start > b.start ? 1 : a.id - b.id))
})
</script>

<template>
  <div class="cv">
    <div class="bar">
      <button @click="nav(-1)">‹</button><button @click="cursor = todayIso()">{{ $t('Heute') }}</button><button @click="nav(1)">›</button>
      <b class="title">{{ title }}</b>
      <span class="spacer" />
      <select v-model="resFilter" :title="$t('Nach Ressource filtern')"><option :value="0">{{ $t('Alle Ressourcen') }}</option><option v-for="r in resources" :key="r.id" :value="r.id">{{ r.name }}</option></select>
      <label class="chk"><input type="checkbox" v-model="showSummary" /> {{ $t('Sammelvorgänge') }}</label>
      <label class="chk"><input type="checkbox" v-model="hideDone" /> {{ $t('Erledigte ausblenden') }}</label>
      <nav class="seg"><button :class="{ on: view === 'month' }" @click="view = 'month'">{{ $t('Monat') }}</button><button :class="{ on: view === 'week' }" @click="view = 'week'">{{ $t('Woche') }}</button><button :class="{ on: view === 'year' }" @click="view = 'year'">{{ $t('Jahr') }}</button><button :class="{ on: view === 'list' }" @click="view = 'list'">{{ $t('Liste') }}</button></nav>
    </div>

    <div v-if="view === 'year'" class="yearv">
      <div v-for="m in months" :key="m.mi" class="ym">
        <b class="mt" @click="pickDay(m.first)">{{ monthLong(m.mi) }}</b>
        <div class="yg">
          <span v-for="d in WD()" :key="d" class="yw">{{ d.slice(0, 1) }}</span>
          <span v-for="n in m.lead" :key="'l' + n" />
          <button v-for="d in m.days" :key="d" class="yd" :class="{ off: !cal.isWork(d), today: d === today, ms: !!marks.get(d)?.ms.length, dl: !!marks.get(d)?.dl.length }"
                  :style="{ background: absShade(d) }" :title="dayTip(d)" @click="pickDay(d)">{{ Number(d.slice(8)) }}</button>
        </div>
      </div>
      <p class="legend">
        <span class="lg off">{{ $t('frei') }}</span><span class="lg ab">{{ $t('Abwesenheit (dunkler = mehr Personen)') }}</span>
        <span class="lg">◆ {{ $t('Meilenstein') }}</span><span class="lg">⚑ {{ $t('Frist') }}</span>
      </p>
    </div>

    <div v-else-if="view !== 'list'" class="grid">
      <div class="wd"><div v-for="d in WD()" :key="d">{{ d }}</div></div>
      <div v-for="w in weeks" :key="w.start" class="week" :style="{ minHeight: (view === 'week' ? 260 : 26 + Math.max(w.lanes, 1) * LANE + 6) + 'px', height: (26 + Math.max(w.lanes, 1) * LANE + 6) + 'px' }">
        <div class="cells">
          <div v-for="d in w.days" :key="d" class="cell" :class="{ off: !cal.isWork(d), today: d === today, other: view === 'month' && d.slice(0, 7) !== cursor.slice(0, 7) }">
            <span class="dn">{{ d.slice(8).replace(/^0/, '') }}<template v-if="d.slice(8) === '01'"> {{ monthShort(Number(d.slice(5, 7)) - 1) }}</template></span>
            <span v-if="absOn(d).length" class="abbar" :title="absTip(d)">{{ view === 'week' ? absOn(d).map(a => kindIcon(a.kind) + ' ' + rname(a.resource_id)).join(', ') : absOn(d).length > 1 ? absOn(d).length : '' }}</span>
          </div>
        </div>
        <div v-for="s in w.segs" :key="s.t.id + '-' + w.start" class="ev" :class="{ cl: s.contL, cr: s.contR, ms: s.t.milestone, done: s.t.status === 'done', blk: s.t.status === 'blocked' }"
             :style="{ left: `calc(${s.c0 / 7 * 100}% + 2px)`, width: `calc(${(s.c1 - s.c0 + 1) / 7 * 100}% - 4px)`, top: 24 + s.lane * LANE + 'px', height: LANE - 3 + 'px', background: color(s.t) }"
             :title="tip(s.t)" @click="emit('open', s.t.id)">
          <span>{{ s.t.status === 'done' ? '✓ ' : s.t.status === 'blocked' ? '⛔ ' : s.t.milestone ? '◆ ' : '' }}{{ s.t.name }}<small v-if="view === 'week' && resNames.get(s.t.id)"> · {{ resNames.get(s.t.id)!.join(', ') }}</small></span>
        </div>
      </div>
    </div>

    <div v-else class="listv">
      <table class="dt">
        <thead><tr><th>{{ $t('Beginn') }}</th><th>{{ $t('Ende') }}</th><th class="hm">{{ $t('PSP') }}</th><th>{{ $t('Vorgang') }}</th><th class="hm">{{ $t('Ressourcen') }}</th><th class="hm">{{ $t('Status') }}</th><th class="n">%</th></tr></thead>
        <tbody>
          <tr v-for="t in list" :key="t.id" :class="{ crit: t.critical && !t.summary, sum: t.summary }" @click="emit('open', t.id)">
            <td>{{ fmt(t.start) }}</td><td>{{ fmt(t.finish) }}</td><td class="hm">{{ t.wbs }}</td>
            <td>{{ t.milestone ? '◆ ' : '' }}{{ t.name }}<small class="sm">{{ STATUS_LABEL[t.status] }}<template v-if="resNames.get(t.id)"> · {{ resNames.get(t.id)!.join(', ') }}</template></small></td>
            <td class="hm">{{ resNames.get(t.id)?.join(', ') }}</td><td class="hm">{{ STATUS_LABEL[t.status] }}</td><td class="n">{{ Math.round(t.percent) }}%</td>
          </tr>
          <tr v-if="!list.length"><td colspan="7" class="dim">{{ $t('Keine Vorgänge in diesem Zeitraum.') }}</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.cv { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.bar { display: flex; align-items: center; gap: 8px; padding: 8px 14px; border-bottom: 1px solid var(--border); flex-wrap: wrap; }
.title { font-size: 16px; min-width: 190px; } .spacer { flex: 1; } .chk { display: inline-flex; gap: 4px; align-items: center; font-size: 13px; }
.seg button { border-radius: 0; } .seg button:first-child { border-radius: 6px 0 0 6px; } .seg button:last-child { border-radius: 0 6px 6px 0; } .seg button.on { background: var(--accent); color: #fff; border-color: var(--accent); }
.grid { flex: 1; overflow: auto; padding: 0 14px 14px; }
.wd { display: grid; grid-template-columns: repeat(7, 1fr); position: sticky; top: 0; background: var(--bg); z-index: 2; padding: 6px 0 4px; font-size: 12px; color: var(--fg-dim); text-align: center; }
.week { position: relative; border-top: 1px solid var(--border); }
.cells { position: absolute; inset: 0; display: grid; grid-template-columns: repeat(7, 1fr); }
.cell { border-right: 1px solid var(--border); padding: 2px 5px; } .cell:last-child { border-right: 0; }
.cell.off { background: var(--off); } .cell.other .dn { opacity: .4; } .cell.today { background: var(--row-sel); } .cell.today .dn { color: var(--accent); font-weight: 700; }
.dn { font-size: 12px; }
.cell { position: relative; }
.abbar { position: absolute; left: 0; right: 0; bottom: 0; min-height: 5px; padding: 0 4px; font-size: 10px; line-height: 14px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
  background: color-mix(in srgb, var(--accent) 35%, transparent); color: var(--fg); z-index: 1; }
.yearv { flex: 1; overflow: auto; padding: 10px 14px 20px; display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 14px 18px; align-content: start; }
.ym { min-width: 0; } .mt { display: block; margin-bottom: 4px; cursor: pointer; font-size: 13px; }
.yg { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; }
.yw { text-align: center; font-size: 10px; color: var(--fg-dim); }
.yd { aspect-ratio: 1; padding: 0; border: 1px solid transparent; border-radius: 4px; background: transparent; font-size: 11px; color: var(--fg); cursor: pointer; position: relative; }
.yd:hover { border-color: var(--accent); } .yd.off { background: var(--off); color: var(--fg-dim); } .yd.today { outline: 2px solid var(--today); outline-offset: -2px; font-weight: 700; }
.yd.ms::after { content: '◆'; position: absolute; right: 1px; top: -2px; font-size: 8px; color: var(--bar-ms); }
.yd.dl::before { content: '⚑'; position: absolute; left: 1px; top: -2px; font-size: 8px; color: var(--bar-critical); }
.legend { grid-column: 1 / -1; margin: 4px 0 0; display: flex; gap: 14px; flex-wrap: wrap; font-size: 12px; color: var(--fg-dim); }
.lg.off::before, .lg.ab::before { content: ''; display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: -1px; background: var(--off); border: 1px solid var(--border); }
.lg.ab::before { background: color-mix(in srgb, var(--accent) 50%, transparent); }
.ev { position: absolute; border-radius: 4px; color: #fff; font-size: 12px; line-height: 1.3; padding: 1px 6px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; cursor: pointer; display: flex; align-items: center; }
.ev span { overflow: hidden; text-overflow: ellipsis; } .ev small { opacity: .85; }
.ev.cl { border-top-left-radius: 0; border-bottom-left-radius: 0; } .ev.cr { border-top-right-radius: 0; border-bottom-right-radius: 0; } .ev.done { opacity: .55; text-decoration: line-through; } .ev.blk { outline: 2px dashed var(--blocked); outline-offset: -2px; }
.ev:hover { filter: brightness(1.1); }
.listv { flex: 1; overflow: auto; padding: 8px 14px 20px; }
.dt { border-collapse: collapse; width: 100%; font-size: 13px; }
.dt th, .dt td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border); } .dt .n { text-align: right; }
.dt tbody tr { cursor: pointer; } .dt tbody tr:hover { background: var(--row-sel); } .dt tr.crit td:nth-child(4) { color: var(--bar-critical); } .dt tr.sum { font-weight: 600; } .dim { color: var(--fg-dim); }
.sm { display: none; }
@media (max-width: 700px) {
  .bar { padding: 6px 10px; gap: 6px; }
  .title { min-width: 0; font-size: 15px; flex: 1; } .spacer { display: none; }
  .bar select { flex: 1 1 100%; } .chk { font-size: 12px; }
  .grid { padding: 0 6px 10px; } .ev { font-size: 11px; } .cell { padding: 2px 3px; }
  .listv { padding: 6px 8px 16px; } .dt { font-size: 12px; } .dt th, .dt td { padding: 5px 4px; }
  .dt .hm { display: none; } .sm { display: block; color: var(--fg-dim); font-size: 11px; }
}
</style>
