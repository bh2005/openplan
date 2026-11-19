<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Dep, Task } from '../lib/types'
import { addDays, dayDiff, ms, todayIso, weekday, WorkCal } from '../lib/dates'
import { monthShort, t as tr } from '../lib/i18n'

const props = defineProps<{
  rows: Task[]
  deps: Dep[]
  cal: WorkCal
  zoom: 'day' | 'week' | 'month'
  rowHeight: number
  headerHeight: number
  showCritical: boolean
  showBaseline: boolean
  showFloat?: boolean       // Pufferlinien hinter den Balken, „knapp kritisch“ orange
  nearDays?: number
  selectedId: number | null
  selectedIds?: Set<number>
  readonly: boolean
  resourceNames: Record<number, string>
}>()
const emit = defineEmits<{
  (e: 'select', id: number): void
  (e: 'open', id: number): void
  (e: 'move', id: number, newStart: string): void
  (e: 'resize', id: number, newDuration: number): void
  (e: 'link', pred: number, succ: number): void
}>()

const PX = { day: 28, week: 10, month: 3.2 } as const
const px = computed(() => PX[props.zoom])

// ── Zeitachse ────────────────────────────────────────────────────────────
const origin = computed(() => {
  let min = props.rows.length ? props.rows[0].start : todayIso()
  for (const t of props.rows) {
    if (t.start < min) min = t.start
    if (props.showBaseline && t.baseline_start && t.baseline_start < min) min = t.baseline_start
  }
  // auf Montag zurückrunden, 1 Woche Vorlauf
  return addDays(min, -7 - weekday(min))
})
const lastDay = computed(() => {
  let max = todayIso()
  for (const t of props.rows) {
    if (t.finish > max) max = t.finish
    if (props.showBaseline && t.baseline_finish && t.baseline_finish > max) max = t.baseline_finish
  }
  return addDays(max, props.zoom === 'month' ? 120 : props.zoom === 'week' ? 60 : 30)
})
const totalDays = computed(() => dayDiff(origin.value, lastDay.value) + 1)
const width = computed(() => Math.ceil(totalDays.value * px.value))
const height = computed(() => props.rows.length * props.rowHeight)

const X = (d: string) => dayDiff(origin.value, d) * px.value
const xs = (t: Task) => X(t.start)
const xe = (t: Task) => X(t.finish) + px.value
/** Ende der Pufferlinie: freier Puffer in Arbeitstagen hinter dem Ende (Kalendertage dazwischen mitgezählt). */
function floatEnd(t: Task): number {
  let d = t.finish, left = t.free_float ?? 0
  while (left > 0) { d = addDays(d, 1); if (props.cal.isWork(d)) left-- }
  return X(d) + px.value
}

interface HCell { x: number; w: number; label: string }
const head = computed(() => {
  const top: HCell[] = []
  const bot: HCell[] = []
  const n = totalDays.value
  let curKey = ''
  let start = 0
  const flush = (end: number, label: string) => top.push({ x: start * px.value, w: (end - start) * px.value, label })
  let lastLabel = ''
  for (let i = 0; i < n; i++) {
    const d = addDays(origin.value, i)
    const key = props.zoom === 'month' ? d.slice(0, 4) : d.slice(0, 7)
    const label = props.zoom === 'month' ? d.slice(0, 4) : `${monthShort(Number(d.slice(5, 7)) - 1)} ${d.slice(0, 4)}`
    if (key !== curKey) {
      if (curKey) flush(i, lastLabel)
      curKey = key; start = i
    }
    lastLabel = label
    if (props.zoom === 'day') bot.push({ x: i * px.value, w: px.value, label: String(Number(d.slice(8))) })
    else if (props.zoom === 'week' && weekday(d) === 0) bot.push({ x: i * px.value, w: 7 * px.value, label: tr('KW') + isoWeek(d) })
    else if (props.zoom === 'month' && d.slice(8) === '01') {
      bot.push({ x: i * px.value, w: 30 * px.value, label: monthShort(Number(d.slice(5, 7)) - 1) })
    }
  }
  if (curKey) flush(n, lastLabel)
  return { top, bot }
})
function isoWeek(d: string) {
  const t = new Date(ms(d))
  const day = (t.getUTCDay() + 6) % 7
  t.setUTCDate(t.getUTCDate() - day + 3)
  const first = new Date(Date.UTC(t.getUTCFullYear(), 0, 4))
  return 1 + Math.round(((t.getTime() - first.getTime()) / 86400000 - 3 + ((first.getUTCDay() + 6) % 7)) / 7)
}

const offDays = computed(() => {
  if (px.value < 8) return []
  const out: number[] = []
  for (let i = 0; i < totalDays.value; i++) if (!props.cal.isWork(addDays(origin.value, i))) out.push(i * px.value)
  return out
})
const todayX = computed(() => X(todayIso()) + px.value / 2)

// ── Balken ───────────────────────────────────────────────────────────────
const idx = computed(() => new Map(props.rows.map((t, i) => [t.id, i])))
const BAR_H = 16
const yc = (i: number) => i * props.rowHeight + props.rowHeight / 2

function barColor(t: Task) {
  if (t.summary) return 'var(--bar-summary)'
  if (props.showCritical && t.critical) return 'var(--bar-critical)'
  if (props.showFloat && t.total_float != null && t.total_float > 0 && t.total_float <= (props.nearDays ?? 0)) return 'var(--bar-near)'
  return 'var(--bar)'
}

// ── Abhängigkeitspfeile ──────────────────────────────────────────────────
const arrows = computed(() => {
  const out: { id: number; d: string; critical: boolean }[] = []
  const byId = new Map(props.rows.map(t => [t.id, t]))
  for (const dep of props.deps) {
    const a = byId.get(dep.pred_id), b = byId.get(dep.succ_id)
    if (!a || !b) continue
    const ia = idx.value.get(a.id)!, ib = idx.value.get(b.id)!
    const y1 = yc(ia), y2 = yc(ib)
    const a_s = a.milestone ? xe(a) : xs(a), a_e = xe(a)
    const b_s = b.milestone ? xe(b) : xs(b), b_e = xe(b)
    const dir = y2 > y1 ? 1 : -1
    const ym = y1 + dir * props.rowHeight / 2
    let d = ''
    if (dep.type === 'FS') {
      d = b_s >= a_e + 12
        ? `M${a_e},${y1} H${a_e + 6} V${y2} H${b_s - 1}`
        : `M${a_e},${y1} H${a_e + 6} V${ym} H${b_s - 8} V${y2} H${b_s - 1}`
    } else if (dep.type === 'SS') {
      const x = Math.min(a_s, b_s) - 8
      d = `M${a_s},${y1} H${x} V${y2} H${b_s - 1}`
    } else if (dep.type === 'FF') {
      const x = Math.max(a_e, b_e) + 8
      d = `M${a_e},${y1} H${x} V${y2} H${b_e + 1}`
    } else {
      d = `M${a_s},${y1} H${a_s - 8} V${ym} H${b_e + 8} V${y2} H${b_e + 1}`
    }
    out.push({ id: dep.id, d, critical: props.showCritical && a.critical && b.critical && !a.summary && !b.summary })
  }
  return out
})

// ── Interaktion: Verschieben / Dauer / Verknüpfen ────────────────────────
type Drag =
  | { kind: 'move' | 'resize'; id: number; x0: number; dx: number }
  | { kind: 'link'; id: number; x: number; y: number }
const drag = ref<Drag | null>(null)
const svgEl = ref<SVGSVGElement | null>(null)

function localPoint(e: PointerEvent) {
  const r = svgEl.value!.getBoundingClientRect()
  return { x: e.clientX - r.left, y: e.clientY - r.top }
}
function down(e: PointerEvent, t: Task, kind: 'move' | 'resize' | 'link') {
  emit('select', t.id)
  if (props.readonly) return
  if (t.summary && kind === 'resize') return
  e.preventDefault()
  ;(e.currentTarget as Element).setPointerCapture(e.pointerId)
  const p = localPoint(e)
  drag.value = kind === 'link' ? { kind, id: t.id, x: p.x, y: p.y } : { kind, id: t.id, x0: e.clientX, dx: 0 }
}
function moveEv(e: PointerEvent) {
  const d = drag.value
  if (!d) return
  if (d.kind === 'link') { const p = localPoint(e); d.x = p.x; d.y = p.y } else d.dx = e.clientX - d.x0
}
function up(e: PointerEvent) {
  const d = drag.value
  drag.value = null
  if (!d) return
  const t = props.rows.find(r => r.id === d.id)
  if (!t) return
  if (d.kind === 'link') {
    const p = localPoint(e)
    const row = Math.floor(p.y / props.rowHeight)
    const target = props.rows[row]
    if (target && target.id !== t.id) emit('link', t.id, target.id)
    return
  }
  const days = Math.round(d.dx / px.value)
  if (days === 0) return
  if (d.kind === 'move') {
    emit('move', t.id, addDays(t.start, days))
  } else {
    const newFinish = addDays(t.finish, days)
    if (newFinish < t.start) return
    const n = props.cal.count(t.start, newFinish)
    if (n >= 1 && n !== t.duration) emit('resize', t.id, n)
  }
}
const ghost = (t: Task) => {
  const d = drag.value
  if (!d || d.kind === 'link' || d.id !== t.id) return { x: 0, w: 0 }
  const snap = Math.round(d.dx / px.value) * px.value
  return d.kind === 'move' ? { x: snap, w: 0 } : { x: 0, w: snap }
}
const linkLine = computed(() => {
  const d = drag.value
  if (!d || d.kind !== 'link') return null
  const i = idx.value.get(d.id)
  if (i === undefined) return null
  const t = props.rows[i]
  return { x1: xe(t), y1: yc(i), x2: d.x, y2: d.y }
})
const tip = (t: Task) =>
  `${t.wbs} ${t.name}\n${t.start} → ${t.finish} (${t.duration} ${tr('AT')}, ${t.percent}%)` +
  (t.total_float != null ? `\n${tr('Puffer')}: ${t.total_float} ${tr('AT')}${t.free_float != null ? ' · ' + tr('frei') + ': ' + t.free_float + ' ' + tr('AT') : ''}${t.critical ? ' – ' + tr('kritisch') : ''}` : '')

defineExpose({ todayX })
</script>

<template>
  <div class="gantt" :style="{ width: width + 'px' }">
    <div class="ghead" :style="{ height: headerHeight + 'px', width: width + 'px' }">
      <div class="hrow" :style="{ height: headerHeight / 2 + 'px' }">
        <div v-for="c in head.top" :key="c.x" class="hcell" :style="{ left: c.x + 'px', width: c.w + 'px' }">{{ c.label }}</div>
      </div>
      <div class="hrow" :style="{ height: headerHeight / 2 + 'px' }">
        <div v-for="c in head.bot" :key="c.x" class="hcell sub" :style="{ left: c.x + 'px', width: c.w + 'px' }">{{ c.label }}</div>
      </div>
    </div>
    <svg ref="svgEl" :width="width" :height="Math.max(height, 1)" class="gsvg"
         @pointermove="moveEv" @pointerup="up" @pointercancel="drag = null">
      <defs>
        <marker id="arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M0,0 L8,4 L0,8 z" fill="var(--dep)" />
        </marker>
        <marker id="arrc" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M0,0 L8,4 L0,8 z" fill="var(--bar-critical)" />
        </marker>
      </defs>
      <!-- Zeilenhintergrund -->
      <rect v-for="(t, i) in rows" :key="'r' + t.id" :x="0" :y="i * rowHeight" :width="width" :height="rowHeight"
            :class="['grow', { sel: t.id === selectedId || selectedIds?.has(t.id), alt: i % 2 }]" @click="emit('select', t.id)" />
      <rect v-for="x in offDays" :key="'o' + x" :x="x" y="0" :width="px" :height="height" class="off" />
      <line v-for="c in head.bot" :key="'g' + c.x" :x1="c.x" :x2="c.x" y1="0" :y2="height" class="gridline" />
      <line :x1="todayX" :x2="todayX" y1="0" :y2="height" class="today" />

      <!-- Pfeile -->
      <path v-for="a in arrows" :key="a.id" :d="a.d" fill="none" class="dep"
            :class="{ crit: a.critical }" :marker-end="a.critical ? 'url(#arrc)' : 'url(#arr)'" />

      <!-- Balken -->
      <g v-for="(t, i) in rows" :key="t.id" @dblclick="emit('open', t.id)">
        <!-- Basisplan -->
        <rect v-if="showBaseline && t.baseline_start && t.baseline_finish"
              :x="X(t.baseline_start)" :y="i * rowHeight + rowHeight - 7" :width="Math.max(X(t.baseline_finish) + px - X(t.baseline_start), 3)"
              height="4" rx="1" class="baseline"><title>{{ $t('Basisplan {1} → {2}', { 1: t.baseline_start, 2: t.baseline_finish }) }}</title></rect>

        <!-- Meilenstein -->
        <g v-if="t.milestone" :transform="`translate(${xe(t) + ghost(t).x},${yc(i)})`" class="ms"
           @pointerdown="down($event, t, 'move')">
          <path d="M0,-9 L9,0 L0,9 L-9,0 z" :fill="showCritical && t.critical ? 'var(--bar-critical)' : 'var(--bar-ms)'" />
          <title>{{ tip(t) }}</title>
        </g>

        <!-- Sammelvorgang -->
        <g v-else-if="t.summary">
          <path :d="`M${xs(t)},${yc(i) - 6} H${xe(t)} V${yc(i) + 5} L${xe(t) - 5},${yc(i)} H${xs(t) + 5} L${xs(t)},${yc(i) + 5} z`"
                :transform="`translate(${ghost(t).x},0)`" fill="var(--bar-summary)" :class="['bar', { ro: readonly, moving: drag && drag.id === t.id }]"
                @pointerdown="down($event, t, 'move')"><title>{{ $t('{1}\nZiehen verschiebt die ganze Phase', { 1: tip(t) }) }}</title></path>
        </g>

        <!-- Normaler Vorgang -->
        <g v-else>
          <rect :x="xs(t) + ghost(t).x" :y="yc(i) - BAR_H / 2" :width="Math.max(xe(t) - xs(t) + ghost(t).w, 4)" :height="BAR_H" rx="3"
                :fill="barColor(t)" class="bar" :class="[{ ro: readonly, moving: drag && drag.id === t.id }, 'st-' + t.status]"
                @pointerdown="down($event, t, 'move')"><title>{{ tip(t) }}</title></rect>
          <line v-if="showFloat && !t.milestone && (t.free_float ?? 0) > 0" :x1="xe(t) + ghost(t).x" :x2="floatEnd(t) + ghost(t).x" :y1="yc(i)" :y2="yc(i)" class="flt" pointer-events="none" />
          <rect v-if="t.percent > 0" :x="xs(t) + ghost(t).x" :y="yc(i) - 3" :width="(xe(t) - xs(t) + ghost(t).w) * t.percent / 100"
                height="6" rx="2" class="prog" pointer-events="none" />
          <text v-if="(t.status === 'done' || t.status === 'blocked') && xe(t) - xs(t) > 22" :x="xs(t) + ghost(t).x + 5" :y="yc(i) + 4" class="stmark" pointer-events="none">{{ t.status === 'done' ? '✓' : '⛔' }}</text>
          <rect v-if="!readonly" :x="xe(t) + ghost(t).x + ghost(t).w - 5" :y="yc(i) - BAR_H / 2" width="8" :height="BAR_H"
                class="handle" @pointerdown="down($event, t, 'resize')" />
        </g>

        <!-- Link-Griff + Ressourcenlabel -->
        <circle v-if="!readonly && !t.milestone" :cx="xe(t) + 11" :cy="yc(i)" r="4.5" class="linkdot"
                @pointerdown="down($event, t, 'link')"><title>{{ $t('Ziehen zum Verknüpfen (Ende → Start)') }}</title></circle>
        <text v-if="t.resource_ids.length" :x="xe(t) + 24" :y="yc(i) + 4" class="rlabel">{{ t.resource_ids.map(r => (resourceNames[r] ?? '').replace(/\s*\(.*\)$/, '')).join(', ') }}</text>
      </g>

      <line v-if="linkLine" v-bind="linkLine" class="linkline" />
    </svg>
  </div>
</template>

<style scoped>
.gantt { position: relative; }
.flt { stroke: var(--bar-near); stroke-width: 2; stroke-dasharray: 3 2; opacity: .9; }
.ghead { position: sticky; top: 0; z-index: 3; background: var(--bg-head); border-bottom: 1px solid var(--border); }
.hrow { position: relative; border-bottom: 1px solid var(--border); overflow: hidden; }
.hrow:last-child { border-bottom: 0; }
.hcell { position: absolute; top: 0; bottom: 0; border-left: 1px solid var(--border); font-size: 11px; line-height: 20px; padding-left: 4px; white-space: nowrap; overflow: hidden; color: var(--fg-dim); }
.hcell.sub { text-align: left; padding-left: 2px; }
.gsvg { display: block; user-select: none; touch-action: none; }
.grow { fill: transparent; }
.grow.alt { fill: var(--row-alt); }
.grow.sel { fill: var(--row-sel); }
.off { fill: var(--off); }
.gridline { stroke: var(--border); stroke-width: 1; opacity: .5; }
.today { stroke: var(--today); stroke-width: 1.5; stroke-dasharray: 4 3; }
.dep { stroke: var(--dep); stroke-width: 1.3; }
.dep.crit { stroke: var(--bar-critical); }
.bar { cursor: grab; }
.bar.ro { cursor: default; }
.bar.moving { opacity: .7; cursor: grabbing; }
.prog { fill: var(--prog); }
.bar.st-done { opacity: .6; } .bar.st-blocked { stroke: var(--blocked); stroke-width: 2.5; stroke-dasharray: 5 3; }
.stmark { font-size: 11px; fill: #fff; font-weight: 700; }
.handle { fill: transparent; cursor: ew-resize; }
.baseline { fill: var(--baseline); }
.ms { cursor: grab; }
.linkdot { fill: var(--accent); opacity: 0; cursor: crosshair; }
g:hover > .linkdot { opacity: .9; }
.linkline { stroke: var(--accent); stroke-width: 2; stroke-dasharray: 4 3; pointer-events: none; }
.rlabel { font-size: 11px; fill: var(--fg-dim); pointer-events: none; }
</style>
