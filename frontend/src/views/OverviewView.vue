<script setup lang="ts">
// „Wer arbeitet woran“: Personen und Projekte über alle für mich sichtbaren Projekte (nur Lesen).
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { downloadBlob, elementToInlinedHtml, fileSlug, htmlToPngBlob, printInlinedHtml } from '../lib/exportImage'
import { api, type Overview, type OverviewPerson } from '../lib/api'
import { kindIcon, kindLabel } from '../lib/absence'
import { fmt } from '../lib/dates'
import { state, toast } from '../lib/store'
import { t as tr } from '../lib/i18n'

const data = ref<Overview | null>(null)
const loading = ref(true)
const exportEl = ref<HTMLElement | null>(null)
const busy = ref(false)
const todayTxt = computed(() => fmt(data.value?.today ?? ''))
async function exportPng() {
  if (!exportEl.value) return
  busy.value = true
  try {
    const { html, w, h } = elementToInlinedHtml(exportEl.value)
    downloadBlob(await htmlToPngBlob(html, w, h, 2), fileSlug(tr('Wer arbeitet woran')) + '_' + (data.value?.today ?? '') + '.png')
  } catch (e) { toast((e as Error).message, 'error') } finally { busy.value = false }
}
function exportPdf() {
  if (!exportEl.value) return
  const { html, w } = elementToInlinedHtml(exportEl.value)
  printInlinedHtml(html, w, tr('Wer arbeitet woran'))
}
const tab = ref<'people' | 'projects'>('people')
const q = ref('')
const flt = ref<'all' | 'over' | 'absent'>('all')
let timer: number | undefined

async function load() {
  try { data.value = await api.overview() } catch (e) { toast((e as Error).message, 'error') }
  loading.value = false
}
onMounted(() => { state.data = null; load(); timer = window.setInterval(() => { if (!document.hidden) load() }, 120000) })
onBeforeUnmount(() => window.clearInterval(timer))

const ROLE: Record<string, { icon: string; label: () => string }> = {
  lead: { icon: '★', label: () => tr('Projektleitung') },
  member: { icon: '👥', label: () => tr('Mitglied') },
  assigned: { icon: '🔧', label: () => tr('Arbeitet an Vorgängen') },
}
const norm = (s: string) => s.toLowerCase()
const match = (text: string) => norm(q.value).split(/\s+/).filter(Boolean).every(w => norm(text).includes(w))
const people = computed(() => (data.value?.people ?? []).filter(p =>
  (flt.value === 'all' || (flt.value === 'over' ? p.over : p.absent_today)) && match(p.name + ' ' + p.projects.map(x => x.name).join(' '))))
const projects = computed(() => (data.value?.projects ?? []).filter(p => match(p.name + ' ' + (p.owner ?? '') + ' ' + p.people.map(x => x.name).join(' '))))
const overCount = computed(() => (data.value?.people ?? []).filter(p => p.over).length)
const absentCount = computed(() => (data.value?.people ?? []).filter(p => p.absent_today).length)
const pct = (v: number) => Math.round(v)
const SHOW = 8                                           // so viele Projekt-Chips je Person, der Rest hinter „+ n weitere“
const expanded = ref(new Set<string>())
const toggleAll = (k: string) => { const s = new Set(expanded.value); s.has(k) ? s.delete(k) : s.add(k); expanded.value = s }
const chips = (p: OverviewPerson) => {
  const all = [...p.projects].sort((a, b) => b.tasks_open - a.tasks_open || a.name.localeCompare(b.name))
  return expanded.value.has(p.key) ? all : all.slice(0, SHOW)
}
const barW = (p: OverviewPerson) => Math.min(100, p.capacity ? (p.load_now / Math.max(p.capacity, p.load_now)) * 100 : 0)
const absTxt = (p: OverviewPerson) => p.absent_today && p.next_absence
  ? `${kindIcon(p.next_absence.kind)} ${tr('abwesend bis')} ${fmt(p.next_absence.end)}`
  : p.next_absence ? `${kindIcon(p.next_absence.kind)} ${kindLabel(p.next_absence.kind)} ${fmt(p.next_absence.start)}–${fmt(p.next_absence.end)}` : ''
const progress = (done: number, total: number) => (total ? Math.round((done / total) * 100) : 0)
</script>

<template>
  <div class="ov">
    <div class="head">
      <h2>{{ $t('Wer arbeitet woran') }}</h2>
      <nav class="seg"><button :class="{ on: tab === 'people' }" @click="tab = 'people'">{{ $t('Personen') }}</button><button :class="{ on: tab === 'projects' }" @click="tab = 'projects'">{{ $t('Projekte') }}</button></nav>
      <span class="spacer" />
      <button v-if="data?.projects.length" :disabled="busy" :title="$t('Aktuelle Ansicht als Bild speichern (z. B. für Folien)')" @click="exportPng">PNG</button>
      <button v-if="data?.projects.length" :title="$t('Aktuelle Ansicht als PDF drucken/speichern')" @click="exportPdf">PDF</button>
      <input v-model="q" type="search" class="q" :placeholder="$t('Person oder Projekt suchen …')" :aria-label="$t('Suchen')" />
    </div>
    <nav v-if="tab === 'people'" class="chips">
      <button :class="{ on: flt === 'all' }" @click="flt = 'all'">{{ $t('Alle') }} <span>{{ data?.people.length ?? 0 }}</span></button>
      <button class="late" :class="{ on: flt === 'over' }" @click="flt = 'over'">{{ $t('Überlastet (30 Tage)') }} <span>{{ overCount }}</span></button>
      <button :class="{ on: flt === 'absent' }" @click="flt = 'absent'">{{ $t('Heute abwesend') }} <span>{{ absentCount }}</span></button>
    </nav>
    <p v-if="loading" class="dim">{{ $t('Lade …') }}</p>
    <p v-else-if="!data || !data.projects.length" class="dim">{{ $t('Keine Projekte sichtbar.') }}</p>

    <div v-else ref="exportEl" class="xwrap">
    <p class="xhead"><b>{{ $t('Wer arbeitet woran') }}</b> · {{ tab === 'people' ? $t('Personen') : $t('Projekte') }} · {{ $t('Stand') }} {{ todayTxt }}</p>
    <table v-if="tab === 'people'" class="pt">
      <thead><tr><th>{{ $t('Person') }}</th><th>{{ $t('Auslastung heute') }}</th><th class="n" :title="$t('Höchste Tageslast in den nächsten 30 Tagen')">{{ $t('Spitze 30 T') }}</th><th>{{ $t('Abwesenheit') }}</th><th>{{ $t('Projekte') }}</th></tr></thead>
      <tbody>
        <tr v-for="p in people" :key="p.key" :class="{ over: p.over, away: p.absent_today }">
          <td class="nm">{{ p.name }}<small v-if="!p.user_id" class="dim" :title="$t('Ressource ohne Benutzerkonto')"> ◌</small></td>
          <td class="ld">
            <span v-if="p.capacity" class="bar" :title="$t('{1} % eingeplant bei {2} % verfügbar', { 1: pct(p.load_now), 2: pct(p.capacity) })"><i :style="{ width: barW(p) + '%' }" :class="{ bad: p.load_now > p.capacity }" /></span>
            <span :class="{ bad: p.load_now > p.capacity }">{{ pct(p.load_now) }} %</span>
          </td>
          <td class="n" :class="{ bad: p.over }">{{ pct(p.peak) }} %<span v-if="p.over" :title="$t('Überlast oder Einsatz während Abwesenheit')"> ⚠</span></td>
          <td class="ab">{{ absTxt(p) }}</td>
          <td class="pj">
            <router-link v-for="s in chips(p)" :key="s.pid" :to="'/project/' + s.pid" class="chip" :class="{ late: s.tasks_overdue, blk: s.tasks_blocked }"
                         :title="(s.funktion ? s.funktion + ' · ' : '') + s.roles.map(r => ROLE[r].label()).join(', ') + (s.until ? ' · ' + $t('bis') + ' ' + fmt(s.until) : '')">
              <b v-if="s.roles.includes('lead')">★</b>{{ s.name }}<span v-if="s.tasks_open" class="cnt">{{ s.tasks_open }}</span>
              <span v-if="s.tasks_overdue" class="cnt late" :title="$t('überfällig')">!{{ s.tasks_overdue }}</span>
            </router-link>
            <button v-if="p.projects.length > SHOW" class="more" @click="toggleAll(p.key)">{{ expanded.has(p.key) ? $t('weniger') : $t('+ {1} weitere', { 1: p.projects.length - SHOW }) }}</button>
          </td>
        </tr>
        <tr v-if="!people.length"><td colspan="5" class="dim">{{ $t('Keine Treffer.') }}</td></tr>
      </tbody>
    </table>

    <div v-else class="cards">
      <section v-for="pr in projects" :key="pr.id" class="card">
        <h3><router-link :to="'/project/' + pr.id">{{ pr.name }}</router-link></h3>
        <div class="meta">
          <span v-if="pr.owner">★ {{ pr.owner }}</span><span v-if="pr.finish">{{ $t('Ende') }} {{ fmt(pr.finish) }}</span>
          <span>{{ progress(pr.tasks_done, pr.tasks_total) }} % {{ $t('erledigt') }} ({{ pr.tasks_done }}/{{ pr.tasks_total }})</span>
          <span v-if="pr.tasks_overdue" class="bad">{{ $t('{1} überfällig', { 1: pr.tasks_overdue }) }}</span>
          <span v-if="pr.tasks_blocked" class="blk">{{ $t('⛔ {1} blockiert', { 1: pr.tasks_blocked }) }}</span>
        </div>
        <span class="bar wide"><i :style="{ width: progress(pr.tasks_done, pr.tasks_total) + '%' }" /></span>
        <ul>
          <li v-for="m in pr.people" :key="m.key">
            <span class="who" :title="m.roles.map(r => ROLE[r].label()).join(', ')">{{ m.name }}<small v-if="m.funktion" class="dim"> · {{ m.funktion }}</small></span>
            <span class="roles" :title="m.roles.map(r => ROLE[r].label()).join(', ')">{{ m.roles.map(r => ROLE[r].icon).join(' ') }}</span>
            <span class="spacer" />
            <span v-if="m.tasks_open" :title="$t('offene Vorgänge')">{{ $t('{1} offen', { 1: m.tasks_open }) }}</span>
            <span v-if="m.tasks_overdue" class="bad">!{{ m.tasks_overdue }}</span>
            <span v-if="m.load_now" class="dim">{{ pct(m.load_now) }} %</span>
          </li>
        </ul>
      </section>
      <p v-if="!projects.length" class="dim">{{ $t('Keine Treffer.') }}</p>
    </div>
    </div>
    <p class="dim foot">{{ $t('Es erscheinen nur Projekte, die du sehen darfst. „Krank“ wird für andere als „Sonstiges“ gezeigt. ◌ = Ressource ohne Benutzerkonto.') }}</p>
  </div>
</template>

<style scoped>
.ov { padding: 18px 22px; overflow: auto; max-width: 1300px; }
.head { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; } .spacer { flex: 1; } .q { min-width: 240px; }
.seg button { border-radius: 0; } .seg button:first-child { border-radius: 6px 0 0 6px; } .seg button:last-child { border-radius: 0 6px 6px 0; } .seg button.on { background: var(--accent); color: #fff; border-color: var(--accent); }
.chips { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; } .chips button { border-radius: 14px; padding: 3px 12px; } .chips button span { opacity: .7; margin-left: 4px; font-size: 12px; }
.chips button.on { background: var(--accent); border-color: var(--accent); color: #fff; } .chips button.late:not(.on) { border-color: var(--bar-critical); color: var(--bar-critical); }
.xhead { margin: 2px 0 10px; font-size: 13px; color: var(--fg-dim); } .xwrap { background: var(--bg); }
.dim { color: var(--fg-dim); } .bad { color: var(--bar-critical); font-weight: 600; } .blk { color: var(--blocked); } .foot { font-size: 12px; margin-top: 14px; }
.pt { border-collapse: collapse; width: 100%; font-size: 13px; }
.pt th, .pt td { text-align: left; padding: 7px 8px; border-bottom: 1px solid var(--border); vertical-align: top; } .pt .n { text-align: right; white-space: nowrap; }
.pt tr.away .nm { opacity: .65; } .nm { font-weight: 600; white-space: nowrap; } .ab { white-space: nowrap; color: var(--fg-dim); }
.ld { white-space: nowrap; } .bar { display: inline-block; width: 70px; height: 8px; background: var(--chip); border-radius: 4px; overflow: hidden; vertical-align: middle; margin-right: 6px; }
.bar i { display: block; height: 100%; background: var(--ok); } .bar i.bad { background: var(--bar-critical); } .bar.wide { display: block; width: 100%; margin: 6px 0 8px; } .bar.wide i { background: var(--accent); }
.pj { display: flex; gap: 5px; flex-wrap: wrap; }
.chip { display: inline-flex; align-items: center; gap: 5px; padding: 1px 9px; border: 1px solid var(--border); border-radius: 12px; background: var(--chip); color: var(--fg); text-decoration: none; font-size: 12px; }
.chip:hover { border-color: var(--accent); } .chip.blk { border-left: 3px solid var(--blocked); } .chip.late { border-color: var(--bar-critical); }
.cnt { color: var(--fg-dim); font-size: 11px; } .cnt.late { color: var(--bar-critical); font-weight: 700; }
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 14px; }
.card { border: 1px solid var(--border); border-radius: 10px; padding: 12px 14px; } .card h3 { margin: 0 0 4px; font-size: 15px; } .card h3 a { color: var(--fg); text-decoration: none; } .card h3 a:hover { color: var(--accent); }
.meta { display: flex; gap: 12px; flex-wrap: wrap; font-size: 12px; color: var(--fg-dim); }
.card ul { list-style: none; margin: 0; padding: 0; } .card li { display: flex; align-items: center; gap: 8px; padding: 4px 0; border-top: 1px solid var(--border); font-size: 13px; flex-wrap: wrap; }
.who { font-weight: 600; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; } .roles { font-size: 12px; flex: none; }
.card li { flex-wrap: nowrap; } .card li > span:not(.who):not(.spacer) { flex: none; white-space: nowrap; }
.more { border: 0; background: none; color: var(--accent); padding: 1px 6px; cursor: pointer; font-size: 12px; }
@media (max-width: 700px) { .ov { padding: 12px; } .q { min-width: 0; flex: 1; } .pt thead { display: none; } .pt tr { display: block; padding: 6px 0; border-bottom: 1px solid var(--border); } .pt td { display: block; border: 0; padding: 2px 4px; } .pt .n { text-align: left; } }
</style>
