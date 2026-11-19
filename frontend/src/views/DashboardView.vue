<script setup lang="ts">
// Management-Dashboard: Portfolio-Ampel, Meilensteine, Risiken, Auslastung, Budget (nur Projekte, die ich sehen darf).
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api, type Dashboard, type DashProject } from '../lib/api'
import { addDays, dayDiff, fmt } from '../lib/dates'
import { downloadBlob, elementToInlinedHtml, fileSlug, htmlToPngBlob, printInlinedHtml } from '../lib/exportImage'
import { eur } from '../lib/finance'
import { kindIcon } from '../lib/absence'
import { state, toast } from '../lib/store'
import { t as tr } from '../lib/i18n'

const d = ref<Dashboard | null>(null)
const loading = ref(true)
const flt = ref<'all' | 'red' | 'yellow' | 'green' | 'done'>('all')
const exportEl = ref<HTMLElement | null>(null)
const busy = ref(false)
let timer: number | undefined

async function load() {
  try { d.value = await api.dashboard() } catch (e) { toast((e as Error).message, 'error') }
  loading.value = false
}
onMounted(() => { state.data = null; load(); timer = window.setInterval(() => { if (!document.hidden) load() }, 300000) })
onBeforeUnmount(() => window.clearInterval(timer))

const LABEL = (s: string) => ({ red: tr('Rot'), yellow: tr('Gelb'), green: tr('Grün'), done: tr('Abgeschlossen'), empty: tr('Leer') })[s] ?? s
const projects = computed(() => (d.value?.projects ?? []).filter(p => flt.value === 'all' || p.status === flt.value))
const reasonText = (r: DashProject['reasons'][number]) => ({
  deadline: () => tr('{1} Frist(en) überschritten', { 1: r.n }),
  overdue_pct: () => tr('{1} % überfällig ({2} von {3})', { 1: r.pct, 2: r.n, 3: r.total }),
  overdue: () => tr('{1} überfällig', { 1: r.n }),
  blocked: () => tr('{1} blockiert', { 1: r.n }),
} as Record<string, () => string>)[r.key]?.() ?? r.key
const seg = computed(() => {
  const s = d.value?.kpi.status, n = d.value?.kpi.projects || 1
  return s ? (['red', 'yellow', 'green', 'done'] as const).map(k => ({ k, n: s[k], w: (s[k] / n) * 100 })).filter(x => x.n) : []
})

// ── Meilenstein-Zeitstrahl ──
const T0 = computed(() => addDays(d.value?.today ?? '2000-01-01', -14))
const SPAN = 14 + (d.value?.rules.milestone_days ?? 60) + 1
const TL = { w: 760, left: 170, row: 26, top: 26 }
const tlRows = computed(() => {
  const by = new Map<number, { project: string; items: Dashboard['milestones'] }>()
  for (const m of d.value?.milestones ?? []) {
    if (m.date < T0.value) continue
    if (!by.has(m.pid)) by.set(m.pid, { project: m.project, items: [] })
    by.get(m.pid)!.items.push(m)
  }
  return [...by.values()].slice(0, 14)
})
const tx = (date: string) => TL.left + (Math.max(0, Math.min(dayDiff(T0.value, date), SPAN)) / SPAN) * (TL.w - TL.left - 10)
const ticks = computed(() => Array.from({ length: Math.floor(SPAN / 14) + 1 }, (_, i) => addDays(T0.value, i * 14)))
const tlH = computed(() => TL.top + Math.max(tlRows.value.length, 1) * TL.row + 8)

const riskIcon = (k: string) => ({ blocked: '⛔', overdue: '⏰', deadline: '⚑' })[k] ?? '•'
const riskText = (r: Dashboard['risks']['items'][number]) => r.kind === 'blocked'
  ? (r.note ? r.note + ' · ' : '') + (r.days != null ? tr('seit {1} Tagen', { 1: r.days }) : tr('blockiert'))
  : r.kind === 'overdue' ? tr('{1} Tage überfällig (Ende {2})', { 1: r.days, 2: fmt(r.date) })
  : tr('Ende {1} Tage nach der Frist ({2})', { 1: r.days, 2: fmt(r.date) })
const riskMore = computed(() => { const c = d.value?.risks.counts; return c ? c.blocked + c.overdue + c.deadline - (d.value?.risks.items.length ?? 0) : 0 })
const pct = (v: number) => Math.round(v)

async function exportPng() {
  if (!exportEl.value) return
  busy.value = true
  try {
    const { html, w, h } = elementToInlinedHtml(exportEl.value)
    downloadBlob(await htmlToPngBlob(html, w, h, 2), fileSlug(tr('Management-Dashboard')) + '_' + (d.value?.today ?? '') + '.png')
  } catch (e) { toast((e as Error).message, 'error') } finally { busy.value = false }
}
function exportPdf() {
  if (!exportEl.value) return
  const { html, w } = elementToInlinedHtml(exportEl.value)
  printInlinedHtml(html, w, tr('Management-Dashboard'))
}
</script>

<template>
  <div class="db">
    <div class="head">
      <h2>{{ $t('Management-Dashboard') }}</h2>
      <span class="spacer" />
      <button v-if="d" :disabled="busy" :title="$t('Dashboard als Bild speichern (z. B. für Folien)')" @click="exportPng">PNG</button>
      <button v-if="d" :title="$t('Dashboard als PDF drucken/speichern')" @click="exportPdf">PDF</button>
    </div>
    <p v-if="loading" class="dim">{{ $t('Lade …') }}</p>
    <p v-else-if="!d || !d.projects.length" class="dim">{{ $t('Keine Projekte sichtbar.') }}</p>

    <div v-else ref="exportEl" class="xwrap">
      <p class="xhead"><b>{{ $t('Management-Dashboard') }}</b> · {{ $t('Stand') }} {{ fmt(d.today) }}</p>

      <section class="tiles">
        <div class="tile wide">
          <small>{{ $t('Projekte') }}</small>
          <b class="big">{{ d.kpi.projects }}</b>
          <div class="seg"><i v-for="s in seg" :key="s.k" :class="s.k" :style="{ width: s.w + '%' }" :title="LABEL(s.k) + ': ' + s.n">{{ s.n }}</i></div>
          <small class="legend"><span class="dot red" /> {{ d.kpi.status.red }} {{ $t('Rot') }} · <span class="dot yellow" /> {{ d.kpi.status.yellow }} {{ $t('Gelb') }} · <span class="dot green" /> {{ d.kpi.status.green }} {{ $t('Grün') }}<template v-if="d.kpi.status.done"> · {{ d.kpi.status.done }} {{ $t('abgeschlossen') }}</template></small>
        </div>
        <div class="tile" :class="{ warn: d.kpi.deadline_missed }"><small>{{ $t('Fristen überschritten') }}</small><b class="big">{{ d.kpi.deadline_missed }}</b></div>
        <div class="tile" :class="{ warn: d.kpi.overdue }"><small>{{ $t('Überfällige Vorgänge') }}</small><b class="big">{{ d.kpi.overdue }}</b></div>
        <div class="tile" :class="{ warn: d.kpi.blocked }"><small>{{ $t('Blockierte Vorgänge') }}</small><b class="big">{{ d.kpi.blocked }}</b></div>
        <div class="tile" :class="{ warn: d.kpi.people_over }"><small>{{ $t('Überlastete Personen') }}</small><b class="big">{{ d.kpi.people_over }}</b><small class="dim">{{ $t('von {1}', { 1: d.kpi.people }) }}</small></div>
        <div class="tile"><small>{{ $t('Heute abwesend') }}</small><b class="big">{{ d.kpi.absent_today }}</b></div>
        <div class="tile"><small>{{ $t('Ø Fortschritt (laufende)') }}</small><b class="big">{{ d.kpi.percent }} %</b></div>
        <div v-if="d.cost" class="tile" :class="{ warn: d.cost.over }">
          <small>{{ $t('Budget (sichtbare Projekte)') }}</small>
          <b class="mid">{{ eur(d.cost.ac) }} <span class="dim">/ {{ eur(d.cost.budget) }}</span></b>
          <small class="dim">{{ $t('Ist / Budget') }} · {{ $t('Prognose {1}', { 1: eur(d.cost.eac) }) }}<template v-if="d.cost.over"> · <span class="bad">{{ $t('{1} über Budget', { 1: d.cost.over }) }}</span></template></small>
        </div>
      </section>

      <section class="panel">
        <div class="ph">
          <h3>{{ $t('Projekt-Ampel') }}</h3>
          <nav class="chips" data-noexport>
            <button :class="{ on: flt === 'all' }" @click="flt = 'all'">{{ $t('Alle') }}</button>
            <button class="r" :class="{ on: flt === 'red' }" @click="flt = 'red'">{{ $t('Rot') }} {{ d.kpi.status.red }}</button>
            <button class="y" :class="{ on: flt === 'yellow' }" @click="flt = 'yellow'">{{ $t('Gelb') }} {{ d.kpi.status.yellow }}</button>
            <button class="g" :class="{ on: flt === 'green' }" @click="flt = 'green'">{{ $t('Grün') }} {{ d.kpi.status.green }}</button>
            <button :class="{ on: flt === 'done' }" @click="flt = 'done'">{{ $t('Abgeschlossen') }} {{ d.kpi.status.done }}</button>
          </nav>
        </div>
        <table class="pt">
          <thead><tr><th /><th>{{ $t('Projekt') }}</th><th>{{ $t('Leitung') }}</th><th>{{ $t('Fortschritt') }}</th><th>{{ $t('Ende') }}</th><th>{{ $t('Warum') }}</th><th v-if="d.cost">{{ $t('Budget') }}</th><th>{{ $t('Nächster Meilenstein') }}</th></tr></thead>
          <tbody>
            <tr v-for="p in projects" :key="p.id">
              <td><span class="dot big" :class="p.status" :title="LABEL(p.status)" /></td>
              <td class="nm"><router-link :to="'/project/' + p.id">{{ p.name }}</router-link></td>
              <td>{{ p.owner }}</td>
              <td class="pg"><span class="bar"><i :style="{ width: p.percent + '%' }" /></span> {{ p.percent }} %</td>
              <td>{{ fmt(p.finish) }}</td>
              <td class="why"><span v-for="(r, i) in p.reasons" :key="i" :class="{ bad: r.key !== 'overdue' }">{{ reasonText(r) }}<template v-if="i < p.reasons.length - 1"> · </template></span></td>
              <td v-if="d.cost" class="bu">
                <template v-if="p.budget"><span :class="{ bad: p.budget.over }">{{ p.budget.over ? '⚠ ' : '' }}{{ p.budget.budget != null ? eur(p.budget.ac) + ' / ' + eur(p.budget.budget) : eur(p.budget.ac) }}</span>
                  <small v-if="p.budget.cpi != null" class="dim"> · CPI {{ p.budget.cpi.toFixed(2) }}<template v-if="p.budget.spi != null"> / SPI {{ p.budget.spi.toFixed(2) }}</template></small></template>
              </td>
              <td class="ms"><template v-if="p.next_milestone"><span :class="{ bad: p.next_milestone.late }">◆ {{ fmt(p.next_milestone.date) }}</span> {{ p.next_milestone.name }}</template></td>
            </tr>
            <tr v-if="!projects.length"><td colspan="8" class="dim">{{ $t('Keine Treffer.') }}</td></tr>
          </tbody>
        </table>
        <p class="rules dim">{{ $t('Rot: ein Vorgang plant sein Ende nach der gesetzten Frist, mehr als {1} % der Vorgänge sind überfällig oder etwas ist blockiert. Gelb: nicht rot, aber mindestens ein Vorgang überfällig. Grün: sonst. Das Budget fließt nicht in die Ampel ein.', { 1: d.rules.overdue_pct }) }}</p>
      </section>

      <div class="two">
        <section class="panel">
          <h3>{{ $t('Meilensteine – nächste {1} Tage', { 1: d.rules.milestone_days }) }}</h3>
          <p v-if="!tlRows.length" class="dim">{{ $t('Keine offenen Meilensteine im Zeitraum.') }}</p>
          <svg v-else :viewBox="`0 0 ${TL.w} ${tlH}`" class="tl" role="img" :aria-label="$t('Meilensteine')">
            <g v-for="(t, i) in ticks" :key="t"><line :x1="tx(t)" :x2="tx(t)" :y1="TL.top - 6" :y2="tlH - 4" stroke="#e2e8f0" /><text :x="tx(t) + 3" y="14" font-size="10" fill="#64748b">{{ fmt(t).slice(0, 5) }}</text></g>
            <line :x1="tx(d.today)" :x2="tx(d.today)" :y1="TL.top - 6" :y2="tlH - 4" stroke="#dc2626" stroke-dasharray="4 3" />
            <g v-for="(r, i) in tlRows" :key="r.project">
              <rect v-if="i % 2" :x="0" :y="TL.top + i * TL.row" :width="TL.w" :height="TL.row" fill="#f8fafc" />
              <text :x="4" :y="TL.top + i * TL.row + TL.row / 2 + 4" font-size="11" fill="#0f172a">{{ r.project.length > 26 ? r.project.slice(0, 25) + '…' : r.project }}</text>
              <path v-for="m in r.items" :key="m.task_id" :transform="`translate(${tx(m.date)},${TL.top + i * TL.row + TL.row / 2})`" d="M0,-7 L7,0 L0,7 L-7,0 z" :fill="m.late ? '#dc2626' : m.critical ? '#7c3aed' : '#2563eb'">
                <title>{{ fmt(m.date) }} · {{ m.name }}{{ m.late ? ' (' + $t('überfällig') + ')' : '' }}</title>
              </path>
            </g>
          </svg>
          <p v-if="tlRows.length" class="dim small">◆ <span class="pu">{{ $t('kritisch') }}</span> · ◆ <span class="re">{{ $t('überfällig') }}</span> · ◆ <span class="bl">{{ $t('geplant') }}</span> · {{ $t('gestrichelt = heute') }}</p>
        </section>

        <section class="panel">
          <h3>{{ $t('Risiken & Handlungsbedarf') }}
            <small class="dim">{{ d.risks.counts.deadline }} {{ $t('Frist') }} · {{ d.risks.counts.blocked }} {{ $t('blockiert') }} · {{ d.risks.counts.overdue }} {{ $t('überfällig') }}</small></h3>
          <p v-if="!d.risks.items.length" class="ok">✓ {{ $t('Keine Risiken: nichts blockiert, nichts überfällig.') }}</p>
          <ul v-else class="rk">
            <li v-for="r in d.risks.items" :key="r.kind + r.task_id">
              <span class="ico">{{ riskIcon(r.kind) }}</span>
              <div><b>{{ r.name }}</b> <small class="dim">· <router-link :to="`/project/${r.pid}?task=${r.task_id}`">{{ r.project }}</router-link><template v-if="r.who.length"> · {{ r.who.join(', ') }}</template></small>
                <div class="rt" :class="{ bad: r.kind !== 'overdue' }">{{ riskText(r) }}</div></div>
            </li>
          </ul>
          <p v-if="riskMore > 0" class="dim small">{{ $t('… und {1} weitere', { 1: riskMore }) }}</p>
        </section>
      </div>

      <section class="panel">
        <h3>{{ $t('Auslastung & Abwesenheit') }}</h3>
        <div class="two">
          <div>
            <h4>{{ $t('Überlastet (nächste 30 Tage)') }}</h4>
            <p v-if="!d.load.over.length" class="ok">✓ {{ $t('Niemand überlastet.') }}</p>
            <div v-for="p in d.load.over" :key="p.name" class="lrow">
              <span class="who">{{ p.name }}</span>
              <span class="bar red"><i :style="{ width: Math.min(100, p.capacity ? (p.peak / Math.max(p.peak, p.capacity)) * 100 : 100) + '%' }" /></span>
              <span class="bad">{{ pct(p.peak) }} %</span><small class="dim"> {{ $t('bei {1} % · {2} Projekte', { 1: pct(p.capacity), 2: p.projects }) }}</small>
            </div>
          </div>
          <div>
            <h4>{{ $t('Heute abwesend') }}</h4>
            <p v-if="!d.load.absent.length" class="dim">{{ $t('Niemand.') }}</p>
            <div v-for="p in d.load.absent" :key="p.name" class="lrow"><span class="who">{{ p.name }}</span><span class="dim">{{ p.kind ? kindIcon(p.kind) : '' }} {{ p.until ? $t('bis {1}', { 1: fmt(p.until) }) : '' }}</span></div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.db { padding: 18px 22px; overflow: auto; max-width: 1400px; }
.head { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; } .spacer { flex: 1; }
.dim { color: var(--fg-dim); } .bad { color: var(--bar-critical); font-weight: 600; } .ok { color: var(--ok); } .small { font-size: 12px; }
.xwrap { background: var(--bg); } .xhead { margin: 2px 0 12px; font-size: 13px; color: var(--fg-dim); }
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 12px; margin-bottom: 18px; }
.tile { border: 1px solid var(--border); border-radius: 10px; padding: 10px 14px; display: flex; flex-direction: column; gap: 3px; } .tile.wide { grid-column: span 2; }
.tile small { color: var(--fg-dim); font-size: 12px; } .tile.warn { border-color: var(--bar-critical); } .tile.warn .big { color: var(--bar-critical); }
.big { font-size: 28px; line-height: 1.1; } .mid { font-size: 17px; }
.seg { display: flex; height: 16px; border-radius: 8px; overflow: hidden; background: var(--chip); margin: 4px 0; }
.seg i { font-style: normal; font-size: 11px; color: #fff; text-align: center; line-height: 16px; } .seg .red { background: #dc2626; } .seg .yellow { background: #f59e0b; } .seg .green { background: #16a34a; } .seg .done { background: #94a3b8; }
.dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; background: #94a3b8; vertical-align: middle; } .dot.big { width: 14px; height: 14px; }
.dot.red { background: #dc2626; } .dot.yellow { background: #f59e0b; } .dot.green { background: #16a34a; } .dot.done, .dot.empty { background: #94a3b8; }
.panel { border: 1px solid var(--border); border-radius: 10px; padding: 12px 16px; margin-bottom: 18px; min-width: 0; } .panel h3 { margin: 0 0 8px; font-size: 15px; } .panel h3 small { font-weight: 400; margin-left: 8px; }
.ph { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 4px; } .ph h3 { margin: 0; }
.chips { display: flex; gap: 6px; flex-wrap: wrap; } .chips button { border-radius: 14px; padding: 2px 11px; font-size: 12px; } .chips button.on { background: var(--accent); border-color: var(--accent); color: #fff; }
.chips .r:not(.on) { border-color: #dc2626; color: #dc2626; } .chips .y:not(.on) { border-color: #d97706; color: #d97706; } .chips .g:not(.on) { border-color: #16a34a; color: #16a34a; }
.pt { border-collapse: collapse; width: 100%; font-size: 13px; } .pt th, .pt td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border); vertical-align: top; }
.nm a { color: var(--fg); font-weight: 600; text-decoration: none; } .nm a:hover { color: var(--accent); } .pg { white-space: nowrap; } .ms, .bu { white-space: nowrap; }
.bar { display: inline-block; width: 70px; height: 8px; background: var(--chip); border-radius: 4px; overflow: hidden; vertical-align: middle; } .bar i { display: block; height: 100%; background: var(--accent); } .bar.red i { background: var(--bar-critical); }
.rules { font-size: 12px; margin: 10px 0 0; }
.two { display: grid; grid-template-columns: 1.3fr 1fr; gap: 18px; } .two .panel { margin-bottom: 0; } .two + .panel, .two { margin-bottom: 18px; }
.tl { width: 100%; height: auto; background: #fff; border-radius: 6px; } .pu { color: #7c3aed; } .re { color: #dc2626; } .bl { color: #2563eb; }
.rk { list-style: none; margin: 0; padding: 0; } .rk li { display: flex; gap: 10px; padding: 6px 0; border-top: 1px solid var(--border); font-size: 13px; } .rk li:first-child { border-top: 0; }
.rk a { color: var(--accent); text-decoration: none; } .ico { font-size: 14px; flex: none; } .rt { font-size: 12px; }
h4 { margin: 0 0 6px; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: var(--fg-dim); }
.lrow { display: flex; align-items: center; gap: 10px; padding: 3px 0; font-size: 13px; } .who { min-width: 150px; font-weight: 600; }
@media (max-width: 900px) { .db { padding: 12px; } .two { grid-template-columns: 1fr; } .tile.wide { grid-column: span 1; } .pt thead { display: none; } .pt tr { display: block; padding: 6px 0; border-bottom: 1px solid var(--border); } .pt td { display: block; border: 0; padding: 2px 4px; } }
</style>
