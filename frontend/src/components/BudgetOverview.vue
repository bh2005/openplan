<script setup lang="ts">
import { computed } from 'vue'
import { api } from '../lib/api'
import { downloadBlob, eur, eur0, fin, idx } from '../lib/finance'
import { state, toast } from '../lib/store'
import { t as tr } from '../lib/i18n'

const props = defineProps<{ pid: number }>()
const b = computed(() => fin.budget!)
const s = computed(() => b.value.summary)
const tasks = computed(() => (state.data?.tasks ?? []).filter(t => {
  const v = b.value.per_task[String(t.id)]
  return v && (v.plan || v.actual || v.bac)
}))

const warns = computed(() => {
  const w: string[] = []
  if (s.value.plan_over_budget) w.push(tr('Die Plankosten ({1}) liegen über dem Budget ({2}).', { 1: eur0(s.value.plan), 2: eur0(s.value.budget) }))
  if (s.value.actual_over_budget) w.push(tr('Die Ist-Kosten ({1}) überschreiten das Budget ({2}).', { 1: eur0(s.value.ac), 2: eur0(s.value.budget) }))
  else if (s.value.budget != null && s.value.eac > s.value.budget + 0.005) w.push(tr('Prognose bei Projektende ({1}) liegt über dem Budget.', { 1: eur0(s.value.eac) }))
  if (!b.value.has_baseline && s.value.ac > 0) w.push(tr('Kein Basisplan gesetzt – Kennzahlen (EV/PV) beziehen sich auf den aktuellen Plan. Basisplan unter „Gantt" setzen.'))
  return w
})
const tone = (v: number | null) => (v == null ? '' : v >= 0.98 ? 'ok' : v >= 0.9 ? 'warn' : 'bad')

// ── Verlaufskurve ─────────────────────────────────────────────────────────
const W = 760, H = 260, L = 64, R = 16, T = 14, B = 34
const chart = computed(() => {
  const ser = b.value.series
  if (!ser.length) return null
  const maxV = Math.max(1, ...ser.map(p => Math.max(p.pv, p.ac ?? 0)), s.value.budget ?? 0, s.value.eac) * 1.08
  const x = (i: number) => L + (ser.length === 1 ? (W - L - R) / 2 : (i * (W - L - R)) / (ser.length - 1))
  const y = (v: number) => T + (1 - v / maxV) * (H - T - B)
  const line = (pick: (p: (typeof ser)[number]) => number | null) =>
    ser.map((p, i) => ({ p, i, v: pick(p) })).filter(o => o.v != null).map((o, k) => `${k ? 'L' : 'M'}${x(o.i).toFixed(1)},${y(o.v!).toFixed(1)}`).join(' ')
  const ticks = [0, 0.25, 0.5, 0.75, 1].map(f => ({ y: y(maxV / 1.08 * f), label: eur0(maxV / 1.08 * f) }))
  const statusMonth = b.value.status_date.slice(0, 7)
  const si = ser.findIndex(p => p.month === statusMonth)
  return {
    pv: line(p => p.pv), ac: line(p => p.ac), ticks, x, y, ser, si,
    budgetY: s.value.budget != null ? y(s.value.budget) : null,
    evPt: si >= 0 ? { x: x(si), y: y(s.value.ev) } : null,
    step: Math.ceil(ser.length / 12),
  }
})

async function exp(what: 'matrix' | 'actuals') {
  try { await downloadBlob(await api.budgetExport(props.pid, what), what === 'matrix' ? 'plan-ist-abgleich.csv' : 'ist-kosten.csv') }
  catch (e) { toast((e as Error).message, 'error') }
}
const pct = (a: number, b?: number | null) => (b ? Math.min(Math.round(a / b * 100), 999) : null)
</script>

<template>
  <div class="ov">
    <div v-for="w in warns" :key="w" class="warn">⚠ {{ w }}</div>

    <div class="tiles">
      <div class="tile"><span>{{ $t('Budget') }}</span><b>{{ eur0(s.budget) }}</b><small>{{ s.budget == null ? $t('nicht gesetzt') : $t('Rest') + ': ' + eur0(s.remaining_budget) }}</small></div>
      <div class="tile"><span>{{ $t('Plan (aktuell)') }}</span><b :class="{ bad: s.plan_over_budget }">{{ eur0(s.plan) }}</b><small>{{ $t('Basisplan (BAC): {1}', { 1: eur0(s.bac) }) }}</small></div>
      <div class="tile"><span>{{ $t('Ist-Kosten (AC)') }}</span><b :class="{ bad: s.actual_over_budget }">{{ eur0(s.ac) }}</b><small>{{ $t('Fertigstellungswert (EV): {1}', { 1: eur0(s.ev) }) }}</small></div>
      <div class="tile"><span>{{ $t('Prognose bei Ende (EAC)') }}</span><b :class="{ bad: s.budget != null && s.eac > s.budget + 0.005 }">{{ eur0(s.eac) }}</b><small>{{ $t('Restkosten (ETC): {1}', { 1: eur0(s.etc) }) }}</small></div>
      <div class="tile" :class="tone(s.cpi)" :title="$t('Kostenindex = EV / AC. ≥ 1: im Kostenrahmen')"><span>{{ $t('Kostenindex (CPI)') }}</span><b>{{ idx(s.cpi) }}</b><small>{{ $t('Abweichung (CV): {1}', { 1: eur0(s.cv) }) }}</small></div>
      <div class="tile" :class="tone(s.spi)" :title="$t('Terminindex = EV / PV. ≥ 1: im Zeitplan')"><span>{{ $t('Terminindex (SPI)') }}</span><b>{{ idx(s.spi) }}</b><small>{{ $t('Abweichung (SV): {1}', { 1: eur0(s.sv) }) }}</small></div>
    </div>
    <p class="dim">{{ $t('Stichtag {1} · PV (Plan bis Stichtag): {2} · Abweichung zum Basisplan (VAC): {3}', { 1: b.status_date.split('-').reverse().join('.'), 2: eur0(s.pv), 3: eur0(s.vac) }) }}</p>

    <section>
      <h3>{{ $t('Kostenverlauf (kumuliert)') }}</h3>
      <svg v-if="chart" :viewBox="`0 0 ${W} ${H}`" class="chart" role="img" :aria-label="$t('Kostenverlauf Plan gegen Ist')">
        <g v-for="t in chart.ticks" :key="t.y"><line :x1="64" :x2="W - 16" :y1="t.y" :y2="t.y" class="grid" /><text :x="58" :y="t.y + 4" class="axis" text-anchor="end">{{ t.label }}</text></g>
        <g v-for="(p, i) in chart.ser" :key="p.month"><text v-if="i % chart.step === 0" :x="chart.x(i)" :y="H - 12" class="axis" text-anchor="middle">{{ p.month.slice(5) }}/{{ p.month.slice(2, 4) }}</text></g>
        <line v-if="chart.budgetY != null" :x1="64" :x2="W - 16" :y1="chart.budgetY" :y2="chart.budgetY" class="budget" />
        <text v-if="chart.budgetY != null" :x="70" :y="chart.budgetY - 5" class="axis bl">{{ $t('Budget') }}</text>
        <path :d="chart.pv" class="l-pv" fill="none" /><path :d="chart.ac" class="l-ac" fill="none" />
        <g v-if="chart.evPt"><circle :cx="chart.evPt.x" :cy="chart.evPt.y" r="5" class="ev" /><text :x="chart.evPt.x + 8" :y="chart.evPt.y + 4" class="axis">{{ $t('EV') }}</text></g>
      </svg>
      <div class="legend"><span class="k pv" />{{ $t('Plan (Basisplan)') }} <span class="k ac" />{{ $t('Ist') }} <span class="k bu" />{{ $t('Budget') }} <span class="k ev" />{{ $t('Fertigstellungswert') }}</div>
    </section>

    <div class="two">
      <section v-for="g in [{ t: $t('Nach Kostenstelle'), rows: b.by_cost_center }, { t: $t('Nach Kostenart'), rows: b.by_cost_type }]" :key="g.t">
        <h3>{{ g.t }}</h3>
        <table class="dt">
          <thead><tr><th>{{ $t('Bezeichnung') }}</th><th class="n">{{ $t('Budget') }}</th><th class="n">{{ $t('Plan') }}</th><th class="n">{{ $t('Ist') }}</th><th class="n">{{ $t('Ist/Plan') }}</th></tr></thead>
          <tbody>
            <tr v-for="r in g.rows" :key="r.id ?? 'x'">
              <td>{{ r.code }} {{ r.name }}</td><td class="n">{{ eur0(r.budget) }}</td><td class="n" :class="{ bad: r.budget != null && r.plan > r.budget + 0.005 }">{{ eur0(r.plan) }}</td>
              <td class="n" :class="{ bad: r.budget != null && r.actual > r.budget }">{{ eur0(r.actual) }}</td>
              <td class="n">{{ pct(r.actual, r.plan) == null ? '–' : pct(r.actual, r.plan) + '%' }}</td>
            </tr>
            <tr v-if="!g.rows.length"><td colspan="5" class="dim">{{ $t('Noch keine Daten.') }}</td></tr>
          </tbody>
        </table>
      </section>
    </div>

    <section>
      <h3>{{ $t('Abgleich Kostenstelle × Kostenart') }} <button class="sm" @click="exp('matrix')">{{ $t('CSV exportieren') }}</button> <button class="sm" @click="exp('actuals')">{{ $t('Ist-Buchungen exportieren') }}</button></h3>
      <table class="dt">
        <thead><tr><th>{{ $t('Kostenstelle') }}</th><th>{{ $t('Kostenart') }}</th><th class="n">{{ $t('Budget') }}</th><th class="n">{{ $t('Plan') }}</th><th class="n">{{ $t('Ist') }}</th><th class="n">{{ $t('Plan − Ist') }}</th></tr></thead>
        <tbody>
          <tr v-for="(m, i) in b.matrix" :key="i">
            <td>{{ fin.data!.cost_centers.find(c => c.id === m.cost_center_id)?.code ?? 'nicht zugeordnet' }}</td>
            <td>{{ fin.data!.cost_types.find(c => c.id === m.cost_type_id)?.code ?? 'nicht zugeordnet' }}</td>
            <td class="n">{{ eur0(m.budget) }}</td><td class="n">{{ eur(m.plan) }}</td><td class="n">{{ eur(m.actual) }}</td>
            <td class="n" :class="{ bad: m.plan - m.actual < 0 }">{{ eur(m.plan - m.actual) }}</td>
          </tr>
          <tr v-if="!b.matrix.length"><td colspan="6" class="dim">{{ $t('Noch keine Daten.') }}</td></tr>
        </tbody>
      </table>
    </section>

    <section>
      <h3>{{ $t('Nach Vorgang') }}</h3>
      <table class="dt">
        <thead><tr><th>{{ $t('PSP') }}</th><th>{{ $t('Vorgang') }}</th><th class="n">{{ $t('Plan') }}</th><th class="n">{{ $t('Basisplan') }}</th><th class="n">{{ $t('Ist') }}</th><th class="n">{{ $t('EV') }}</th><th class="n">{{ $t('% fertig') }}</th></tr></thead>
        <tbody>
          <tr v-for="t in tasks" :key="t.id" :class="{ sum: t.summary }">
            <td>{{ t.wbs }}</td><td :style="{ paddingLeft: 8 + t.level * 14 + 'px' }">{{ t.name }}</td>
            <td class="n">{{ eur0(b.per_task[String(t.id)].plan) }}</td><td class="n">{{ eur0(b.per_task[String(t.id)].bac) }}</td>
            <td class="n" :class="{ bad: b.per_task[String(t.id)].actual > b.per_task[String(t.id)].bac + 0.005 }">{{ eur0(b.per_task[String(t.id)].actual) }}</td>
            <td class="n">{{ eur0(b.per_task[String(t.id)].ev) }}</td><td class="n">{{ Math.round(t.percent) }}%</td>
          </tr>
          <tr v-if="!tasks.length"><td colspan="7" class="dim">{{ $t('Noch keine Kosten geplant: Ressourcen mit Tagessatz zuordnen oder Plankosten erfassen.') }}</td></tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.ov { padding: 14px 18px 40px; }
.warn { background: color-mix(in srgb, var(--bar-critical) 14%, transparent); border: 1px solid var(--bar-critical); border-radius: 6px; padding: 6px 12px; margin-bottom: 8px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 10px; }
.tile { border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; background: var(--bg-head); display: flex; flex-direction: column; gap: 2px; }
.tile span { font-size: 12px; color: var(--fg-dim); }
.tile b { font-size: 21px; }
.tile small { font-size: 12px; color: var(--fg-dim); }
.tile.ok { border-left: 4px solid var(--ok); } .tile.warn { border-left: 4px solid #d29922; } .tile.bad { border-left: 4px solid var(--bar-critical); }
.bad { color: var(--bar-critical); }
.dim { color: var(--fg-dim); font-size: 12px; }
section { margin-top: 18px; }
h3 { margin: 0 0 8px; font-size: 15px; display: flex; align-items: center; gap: 8px; }
.sm { font-size: 12px; padding: 2px 8px; font-weight: 400; }
.two { display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 18px; }
.chart { width: 100%; max-width: 900px; background: var(--bg-head); border: 1px solid var(--border); border-radius: 8px; }
.grid { stroke: var(--border); } .axis { fill: var(--fg-dim); font-size: 11px; }
.l-pv { stroke: var(--bar); stroke-width: 2.4; } .l-ac { stroke: var(--bar-critical); stroke-width: 2.4; }
.budget { stroke: #d29922; stroke-dasharray: 6 4; stroke-width: 1.8; } .bl { fill: #d29922; font-weight: 600; } .ev { fill: var(--ok); }
.legend { font-size: 12px; color: var(--fg-dim); display: flex; gap: 6px; align-items: center; margin-top: 4px; flex-wrap: wrap; }
.k { display: inline-block; width: 14px; height: 4px; border-radius: 2px; margin-left: 10px; }
.k.pv { background: var(--bar); } .k.ac { background: var(--bar-critical); } .k.bu { background: #d29922; } .k.ev { background: var(--ok); height: 8px; width: 8px; border-radius: 50%; }
.dt { border-collapse: collapse; width: 100%; font-size: 13px; }
.dt th, .dt td { text-align: left; padding: 5px 8px; border-bottom: 1px solid var(--border); }
.dt .n { text-align: right; white-space: nowrap; }
.dt tr.sum td { font-weight: 600; }
</style>
