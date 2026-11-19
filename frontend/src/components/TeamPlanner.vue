<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { addDays, dayDiff, todayIso, weekday, WorkCal } from '../lib/dates'
import { buildHeader, PX, type Zoom } from '../lib/timeline'
import { absentDays, inRange, kindLabel } from '../lib/absence'
import type { Absence, Assignment, Resource, Task } from '../lib/types'
import { t as tr } from '../lib/i18n'

const props = defineProps<{
  tasks: Task[]
  resources: Resource[]
  assignments: Assignment[]
  absences: Absence[]
  cal: WorkCal
  readonly: boolean
}>()
const emit = defineEmits<{
  (e: 'open', id: number): void
  (e: 'move', id: number, newStart: string): void
  (e: 'reassign', id: number, from: number | null, to: number | null): void
  (e: 'level'): void
}>()

const RH = 28
const HH = 44
const zoom = ref<Zoom>('day')
const px = computed(() => PX[zoom.value])
const collapsed = reactive(new Set<number>())
const onlyOver = ref(false)
const selected = ref<number | null>(null)

const leaves = computed(() => props.tasks.filter(t => !t.summary && t.duration > 0))
const tmap = computed(() => new Map(props.tasks.map(t => [t.id, t])))

// ── Split-Layout (wie im Gantt): Tabelle links, Zeitachse rechts, verschiebbare Trennlinie ──
const LW = 420                                        // Inhaltsbreite der Tabelle
const leftPane = ref<HTMLElement | null>(null)        // links, ohne Scrollleisten, vertikal synchron zum rechten
const scroller = ref<HTMLElement | null>(null)        // rechts, scrollt in beide Richtungen
const sbH = ref(0)                                    // Höhe der horizontalen Scrollleiste rechts (links als Abstand ausgleichen)
const widthPref = ref<number | null>(null)
try { const v = Number(localStorage.getItem('openplan.teamw')); if (v) widthPref.value = v } catch { /* privat */ }
const leftWidth = computed(() => Math.min(Math.max(widthPref.value ?? LW, 240), LW))
function measureSb() { if (scroller.value) sbH.value = scroller.value.offsetHeight - scroller.value.clientHeight }
function onRightScroll() {
  if (leftPane.value && scroller.value && Math.abs(leftPane.value.scrollTop - scroller.value.scrollTop) > 0.5) leftPane.value.scrollTop = scroller.value.scrollTop
}
function onLeftScroll() {
  if (leftPane.value && scroller.value && Math.abs(leftPane.value.scrollTop - scroller.value.scrollTop) > 0.5) scroller.value.scrollTop = leftPane.value.scrollTop
}
function onLeftWheel(e: WheelEvent) {
  if (!scroller.value || !leftPane.value) return
  if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) leftPane.value.scrollLeft += e.deltaX
  else scroller.value.scrollTop += e.deltaY
}
function startResize(e: PointerEvent) {
  const el = e.currentTarget as HTMLElement
  el.setPointerCapture(e.pointerId)
  const x0 = e.clientX, w0 = leftWidth.value
  const move = (ev: PointerEvent) => { widthPref.value = Math.min(Math.max(w0 + ev.clientX - x0, 240), LW) }
  const up = () => {
    el.removeEventListener('pointermove', move); el.removeEventListener('pointerup', up)
    try { localStorage.setItem('openplan.teamw', String(widthPref.value ?? '')) } catch { /* privat */ }
  }
  el.addEventListener('pointermove', move); el.addEventListener('pointerup', up)
}
function resetWidth() { widthPref.value = null; try { localStorage.removeItem('openplan.teamw') } catch { /* privat */ } }
onMounted(measureSb)

// ── Zeitachse ────────────────────────────────────────────────────────────
const origin = computed(() => {
  const min = leaves.value.reduce((a, t) => (t.start < a ? t.start : a), leaves.value[0]?.start ?? todayIso())
  return addDays(min, -7 - weekday(min))
})
const totalDays = computed(() => {
  const max = leaves.value.reduce((a, t) => (t.finish > a ? t.finish : a), todayIso())
  return dayDiff(origin.value, addDays(max, zoom.value === 'month' ? 90 : 30)) + 1
})
const width = computed(() => Math.ceil(totalDays.value * px.value))
const X = (d: string) => dayDiff(origin.value, d) * px.value
watch([width, () => props.resources.length], () => nextTick(measureSb))
const head = computed(() => buildHeader(origin.value, totalDays.value, zoom.value))
const todayX = computed(() => X(todayIso()) + px.value / 2)
const offDays = computed(() => {
  if (px.value < 8) return []
  const out: number[] = []
  for (let i = 0; i < totalDays.value; i++) if (!props.cal.isWork(addDays(origin.value, i))) out.push(i * px.value)
  return out
})

// ── Auslastung je Ressource und Tag ───────────────────────────────────────
interface ResStat { load: number[]; cap: number[]; peak: number; effort: number; over: boolean; conflict: boolean }
const stats = computed(() => {
  const out = new Map<number, ResStat>()
  const last = addDays(origin.value, totalDays.value - 1)
  const away = absentDays(props.absences, origin.value, last)
  for (const r of props.resources) {
    const gone = away.get(r.id)
    const cap = new Array(totalDays.value).fill(r.max_units)
    if (gone) for (let i = 0; i < cap.length; i++) if (gone.has(addDays(origin.value, i))) cap[i] = 0     // abwesend = keine Kapazität
    out.set(r.id, { load: new Array(totalDays.value).fill(0), cap, peak: 0, effort: 0, over: false, conflict: false })
  }
  for (const a of props.assignments) {
    const t = tmap.value.get(a.task_id), s = out.get(a.resource_id)
    if (!t || !s || t.summary || t.duration <= 0) continue
    s.effort += t.duration * a.units / 100
    const from = Math.max(dayDiff(origin.value, t.start), 0), to = Math.min(dayDiff(origin.value, t.finish), totalDays.value - 1)
    for (let i = from; i <= to; i++) if (props.cal.isWork(addDays(origin.value, i))) s.load[i] += a.units
  }
  for (const r of props.resources) {
    const s = out.get(r.id)!
    s.peak = Math.max(0, ...s.load)
    s.over = s.load.some((v, i) => v > s.cap[i])
    s.conflict = s.load.some((v, i) => v > 0 && s.cap[i] === 0 && r.max_units > 0)
  }
  return out
})
const absBars = (rid: number) => inRange(props.absences.filter(a => a.resource_id === rid), origin.value, addDays(origin.value, totalDays.value - 1))
  .map(a => ({ id: a.id, x: X(a.start_date < origin.value ? origin.value : a.start_date), w: (dayDiff(a.start_date < origin.value ? origin.value : a.start_date, a.end_date) + 1) * px.value,
    tip: `${kindLabel(a.kind)}: ${a.start_date} → ${a.end_date}${a.note ? '\n' + a.note : ''}` }))
const overCount = computed(() => props.resources.filter(r => stats.value.get(r.id)?.over).length)

// ── Zeilen ────────────────────────────────────────────────────────────────
type Row =
  | { kind: 'res'; key: string; res: Resource }
  | { kind: 'task'; key: string; task: Task; resId: number | null; units: number }
  | { kind: 'head'; key: string }
const rows = computed<Row[]>(() => {
  const out: Row[] = []
  for (const r of props.resources) {
    if (onlyOver.value && !stats.value.get(r.id)?.over) continue
    out.push({ kind: 'res', key: 'r' + r.id, res: r })
    if (collapsed.has(r.id)) continue
    for (const a of props.assignments.filter(x => x.resource_id === r.id)) {
      const t = tmap.value.get(a.task_id)
      if (t && !t.summary && t.duration > 0) out.push({ kind: 'task', key: `t${t.id}r${r.id}`, task: t, resId: r.id, units: a.units })
    }
  }
  if (!onlyOver.value) {
    const un = leaves.value.filter(t => !props.assignments.some(a => a.task_id === t.id))
    out.push({ kind: 'head', key: 'unassigned' })
    for (const t of un) out.push({ kind: 'task', key: `t${t.id}u`, task: t, resId: null, units: 0 })
  }
  return out
})
const height = computed(() => rows.value.length * RH)
const yc = (i: number) => i * RH + RH / 2
const unassignedCount = computed(() => leaves.value.filter(t => !props.assignments.some(a => a.task_id === t.id)).length)

function cellColor(v: number, max: number) {
  if (v > max) return 'var(--bar-critical)'
  return `color-mix(in srgb, var(--ok) ${Math.round(25 + 55 * Math.min(v / Math.max(max, 1), 1))}%, transparent)`
}
function loadCells(r: Resource) {
  const s = stats.value.get(r.id)!
  const cells: { x: number; v: number; cap: number }[] = []
  s.load.forEach((v, i) => { if (v > 0) cells.push({ x: i * px.value, v, cap: s.cap[i] }) })
  return cells
}

// ── Ziehen: Zeit (horizontal) + Ressourcenwechsel (vertikal) ───────────────
const drag = ref<{ row: number; x0: number; y0: number; dx: number; dy: number } | null>(null)
const svgEl = ref<SVGSVGElement | null>(null)
function down(e: PointerEvent, i: number) {
  const row = rows.value[i]
  if (row.kind !== 'task') return
  selected.value = row.task.id
  if (props.readonly) return
  e.preventDefault()
  ;(e.currentTarget as Element).setPointerCapture(e.pointerId)
  drag.value = { row: i, x0: e.clientX, y0: e.clientY, dx: 0, dy: 0 }
}
function mv(e: PointerEvent) {
  if (drag.value) { drag.value.dx = e.clientX - drag.value.x0; drag.value.dy = e.clientY - drag.value.y0 }
}
function up(e: PointerEvent) {
  const d = drag.value
  drag.value = null
  if (!d || !svgEl.value) return
  const row = rows.value[d.row]
  if (row.kind !== 'task') return
  const days = Math.round(d.dx / px.value)
  const y = e.clientY - svgEl.value.getBoundingClientRect().top
  const target = rows.value[Math.min(Math.max(Math.floor(y / RH), 0), rows.value.length - 1)]
  let toRes: number | null | undefined
  if (target.kind === 'res') toRes = target.res.id
  else if (target.kind === 'task') toRes = target.resId
  else toRes = null   // Kopfzeile „Nicht zugeordnet"
  if (Math.abs(d.dy) > RH / 2 && toRes !== undefined && toRes !== row.resId) emit('reassign', row.task.id, row.resId, toRes)
  if (days !== 0) emit('move', row.task.id, addDays(row.task.start, days))
}
const ghost = (i: number) => {
  const d = drag.value
  return d && d.row === i ? { x: Math.round(d.dx / px.value) * px.value, y: d.dy } : { x: 0, y: 0 }
}
const dropRow = computed(() => {
  const d = drag.value
  return d ? Math.min(Math.max(Math.floor((d.row * RH + RH / 2 + d.dy) / RH), 0), rows.value.length - 1) : -1
})
const tip = (t: Task, units: number) => `${t.wbs} ${t.name}\n${t.start} → ${t.finish}\n${units ? units + ' % · ' + (t.duration * units / 100).toFixed(1) + ' ' + tr('PT') : tr('nicht zugeordnet')}`
const pt = (v: number) => (Math.round(v * 10) / 10).toString().replace('.', ',')
</script>

<template>
  <div class="tp">
    <div class="bar">
      <b>{{ $t('Team') }}</b>
      <span v-if="overCount" class="chip bad">{{ $t('{1} überlastet', { 1: overCount }) }}</span>
      <span v-else class="chip">{{ $t('keine Überlastung') }}</span>
      <span v-if="unassignedCount" class="chip">{{ $t('{1} Vorgänge ohne Ressource', { 1: unassignedCount }) }}</span>
      <span class="spacer" />
      <button v-if="!readonly && overCount" class="primary" :title="$t('Schlägt Verschiebungen innerhalb des freien Puffers vor')" @click="emit('level')">{{ $t('Überlastung auflösen …') }}</button>
      <label class="chk"><input type="checkbox" v-model="onlyOver" /> {{ $t('nur Überlastete') }}</label>
      <select v-model="zoom"><option value="day">{{ $t('Tage') }}</option><option value="week">{{ $t('Wochen') }}</option><option value="month">{{ $t('Monate') }}</option></select>
    </div>
    <p v-if="!resources.length" class="empty">{{ $t('Noch keine Ressourcen – lege sie im Tab „Ressourcen" an und ordne sie Vorgängen zu.') }}</p>
    <div v-else class="split">
      <div class="lpane" ref="leftPane" :style="{ width: leftWidth + 'px' }" @scroll="onLeftScroll" @wheel.prevent="onLeftWheel">
      <div class="left" :style="{ paddingBottom: sbH + 'px' }">
        <div class="lhead" :style="{ height: HH + 'px' }"><div class="c name">{{ $t('Ressource / Vorgang') }}</div><div class="c num">{{ $t('Zuord.') }}</div><div class="c num">{{ $t('Aufwand') }}</div></div>
        <div v-for="(r, i) in rows" :key="r.key" class="lrow" :class="[r.kind, { sel: r.kind === 'task' && r.task.id === selected, drop: i === dropRow && drag && r.kind !== 'task' }]" :style="{ height: RH + 'px' }">
          <template v-if="r.kind === 'res'">
            <div class="c name"><button class="tog" @click="collapsed.has(r.res.id) ? collapsed.delete(r.res.id) : collapsed.add(r.res.id)">{{ collapsed.has(r.res.id) ? '▸' : '▾' }}</button>{{ r.res.name }}</div>
            <div class="c num" :class="{ over: stats.get(r.res.id)?.over }" :title="stats.get(r.res.id)?.conflict ? $t('Einsatz während einer Abwesenheit') : $t('Spitze / Verfügbarkeit')">{{ stats.get(r.res.id)?.conflict ? '⚠ ' : '' }}{{ stats.get(r.res.id)?.peak }} / {{ r.res.max_units }} %</div>
            <div class="c num">{{ $t('{1} PT', { 1: pt(stats.get(r.res.id)?.effort ?? 0) }) }}</div>
          </template>
          <template v-else-if="r.kind === 'task'">
            <div class="c name sub" :title="r.task.name"><span :class="{ crit: r.task.critical }">{{ r.task.wbs }} {{ r.task.name }}</span></div>
            <div class="c num">{{ r.units ? r.units + ' %' : '' }}</div>
            <div class="c num">{{ r.units ? pt(r.task.duration * r.units / 100) + ' PT' : r.task.duration + ' T' }}</div>
          </template>
          <template v-else><div class="c name"><b>{{ $t('Nicht zugeordnet') }}</b> <small>{{ $t('(Vorgang hierher ziehen = Zuordnung entfernen)') }}</small></div></template>
        </div>
      </div>
      </div>
      <div class="gutter" :title="$t('Ziehen: Tabellenbreite ändern · Doppelklick: zurücksetzen')" @pointerdown="startResize" @dblclick="resetWidth" />
      <div class="rpane" ref="scroller" @scroll="onRightScroll">
      <div class="right" :style="{ width: width + 'px' }">
        <div class="ghead" :style="{ height: HH + 'px', width: width + 'px' }">
          <div class="hrow" :style="{ height: HH / 2 + 'px' }"><div v-for="c in head.top" :key="c.x" class="hcell" :style="{ left: c.x + 'px', width: c.w + 'px' }">{{ c.label }}</div></div>
          <div class="hrow" :style="{ height: HH / 2 + 'px' }"><div v-for="c in head.bot" :key="c.x" class="hcell sub" :style="{ left: c.x + 'px', width: c.w + 'px' }">{{ c.label }}</div></div>
        </div>
        <svg ref="svgEl" :width="width" :height="Math.max(height, 1)" class="tsvg" @pointermove="mv" @pointerup="up" @pointercancel="drag = null">
          <rect v-for="(r, i) in rows" :key="'b' + r.key" x="0" :y="i * RH" :width="width" :height="RH"
                :class="['bg', r.kind, { sel: r.kind === 'task' && r.task.id === selected, drop: i === dropRow && drag && r.kind !== 'task' }]" />
          <rect v-for="x in offDays" :key="'o' + x" :x="x" y="0" :width="px" :height="height" class="off" />
          <line :x1="todayX" :x2="todayX" y1="0" :y2="height" class="today" />
          <template v-for="(r, i) in rows" :key="r.key">
            <!-- Ressource: Tageslast -->
            <g v-if="r.kind === 'res'">
              <rect v-for="b in absBars(r.res.id)" :key="'a' + b.id" :x="b.x" :y="i * RH + 1" :width="b.w" :height="RH - 2" class="abs"><title>{{ b.tip }}</title></rect>
              <rect v-for="c in loadCells(r.res)" :key="c.x" :x="c.x" :y="i * RH + 3" :width="Math.max(px - (px > 6 ? 1 : 0), 1)" :height="RH - 6" rx="2" :fill="cellColor(c.v, c.cap)">
                <title>{{ $t('{1} % (verfügbar {2} %)', { 1: c.v, 2: c.cap }) }}</title></rect>
              <template v-if="px >= 26"><text v-for="c in loadCells(r.res)" :key="'t' + c.x" :x="c.x + px / 2" :y="yc(i) + 4" class="lt" text-anchor="middle">{{ c.v }}</text></template>
            </g>
            <!-- Vorgangsbalken -->
            <g v-else-if="r.kind === 'task'" :transform="`translate(${ghost(i).x},${ghost(i).y})`">
              <rect :x="X(r.task.start)" :y="yc(i) - 9" :width="Math.max(X(r.task.finish) + px - X(r.task.start), 4)" height="18" rx="3"
                    :class="['tb', { crit: r.task.critical, un: r.resId == null, ro: readonly, moving: drag && drag.row === i, done: r.task.status === 'done', blk: r.task.status === 'blocked' }]"
                    @pointerdown="down($event, i)" @dblclick="emit('open', r.task.id)"><title>{{ tip(r.task, r.units) }}</title></rect>
              <text v-if="X(r.task.finish) + px - X(r.task.start) > 70" :x="X(r.task.start) + 6" :y="yc(i) + 4" class="bt" pointer-events="none">{{ (r.task.status === 'done' ? '✓ ' : r.task.status === 'blocked' ? '⛔ ' : '') + r.task.name }}</text>
            </g>
          </template>
        </svg>
      </div>
      </div>
    </div>
    <p v-if="resources.length && !readonly" class="hint">{{ $t('Balken ziehen: horizontal = Termin verschieben · vertikal auf eine andere Ressource = Umplanen. Doppelklick öffnet die Details.') }}</p>
  </div>
</template>

<style scoped>
.tp { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.bar { display: flex; align-items: center; gap: 10px; padding: 8px 14px; border-bottom: 1px solid var(--border); flex-wrap: wrap; }
.chip { font-size: 12px; padding: 2px 8px; border-radius: 10px; background: var(--chip); color: var(--fg-dim); } .chip.bad { color: #fff; background: var(--bar-critical); }
.spacer { flex: 1; } .chk { display: inline-flex; gap: 4px; align-items: center; font-size: 13px; }
.empty, .hint { color: var(--fg-dim); padding: 12px 18px; margin: 0; font-size: 12px; }
.split { flex: 1; min-height: 0; display: flex; position: relative; }
.lpane { flex: none; max-width: 75%; overflow: auto; scrollbar-width: none; }
.lpane::-webkit-scrollbar { display: none; }
.gutter { flex: none; width: 6px; cursor: col-resize; background: var(--border); transition: background .15s; touch-action: none; }
.gutter:hover { background: var(--accent); }
.rpane { flex: 1; min-width: 0; overflow: auto; position: relative; }
.left { width: 420px; min-height: 100%; box-sizing: content-box; background: var(--bg); font-size: 13px; }
.lhead { position: sticky; top: 0; z-index: 4; display: flex; align-items: flex-end; background: var(--bg-head); border-bottom: 1px solid var(--border); font-weight: 600; color: var(--fg-dim); }
.lrow { display: flex; align-items: center; border-bottom: 1px solid var(--border); background: var(--bg); }
.lrow.res { background: var(--bg-head); font-weight: 600; } .lrow.head { background: var(--bg-head); color: var(--fg-dim); }
.lrow.sel { background: var(--row-sel-solid); } .lrow.drop { outline: 2px solid var(--accent); outline-offset: -2px; }
.c { padding: 0 6px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; } .lhead .c { padding-bottom: 6px; }
.name { flex: 1; min-width: 0; } .name.sub { padding-left: 26px; font-weight: 400; } .num { width: 104px; flex: none; text-align: right; font-weight: 400; }
.over { color: var(--bar-critical); font-weight: 700; } .crit { color: var(--bar-critical); }
.tog { width: 18px; background: none; border: 0; padding: 0; color: var(--fg-dim); cursor: pointer; }
.right { flex: none; position: relative; }
.ghead { position: sticky; top: 0; z-index: 3; background: var(--bg-head); border-bottom: 1px solid var(--border); }
.hrow { position: relative; border-bottom: 1px solid var(--border); overflow: hidden; } .hrow:last-child { border-bottom: 0; }
.hcell { position: absolute; top: 0; bottom: 0; border-left: 1px solid var(--border); font-size: 11px; line-height: 20px; padding-left: 4px; white-space: nowrap; overflow: hidden; color: var(--fg-dim); }
.tsvg { display: block; user-select: none; touch-action: none; }
.bg { fill: transparent; stroke: var(--border); stroke-width: 1; } .bg.res, .bg.head { fill: var(--bg-head); } .bg.sel { fill: var(--row-sel); } .bg.drop { stroke: var(--accent); stroke-width: 2; }
.off { fill: var(--off); pointer-events: none; } .today { stroke: var(--today); stroke-width: 1.5; stroke-dasharray: 4 3; }
.abs { fill: color-mix(in srgb, var(--accent) 22%, transparent); stroke: var(--accent); stroke-width: 1; stroke-dasharray: 3 2; rx: 3; }
.lt { font-size: 10px; fill: var(--fg); pointer-events: none; }
.tb { fill: var(--bar); cursor: grab; } .tb.crit { fill: var(--bar-critical); } .tb.un { fill: var(--fg-dim); } .tb.ro { cursor: default; } .tb.moving { opacity: .7; cursor: grabbing; }
.tb.done { opacity: .55; } .tb.blk { stroke: var(--blocked); stroke-width: 2.5; stroke-dasharray: 5 3; }
.bt { fill: #fff; font-size: 11px; }
</style>
