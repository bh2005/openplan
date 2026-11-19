<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../lib/api'
import { eur, finMutate, fin, label, parseNum } from '../lib/finance'
import { downloadBlob } from '../lib/finance'
import { fmt, parseDate, todayIso } from '../lib/dates'
import { state, toast } from '../lib/store'
import type { Actual, ImportReport } from '../lib/types'
import { t as tr } from '../lib/i18n'

const props = defineProps<{ pid: number; canEdit: boolean }>()
const PAGE = 100
const rows = ref<Actual[]>([])
const total = ref(0)
const sum = ref(0)
const offset = ref(0)
const q = ref('')

async function load() {
  try {
    const r = await api.actuals(props.pid, q.value, offset.value, PAGE)
    rows.value = r.items; total.value = r.total; sum.value = r.sum
  } catch (e) { toast((e as Error).message, 'error') }
}
onMounted(load)
let t: number | undefined
watch(q, () => { window.clearTimeout(t); t = window.setTimeout(() => { offset.value = 0; load() }, 300) })
const refresh = async () => { await load(); await finMutate(props.pid, async () => null) }

// ── Buchung anlegen/ändern ──────────────────────────────────────────────
const editing = ref<null | 'new' | number>(null)
const f = reactive({ date: '', amount: '', task: 0, cc: 0, ct: 0, ref: '', desc: '' })
const leaves = computed(() => (state.data?.tasks ?? []).filter(x => !x.summary))
function openNew() { Object.assign(f, { date: fmt(todayIso()).replace(/\.(\d\d)$/, '.20$1'), amount: '', task: 0, cc: 0, ct: 0, ref: '', desc: '' }); editing.value = 'new' }
function openEdit(a: Actual) {
  Object.assign(f, { date: a.booking_date.split('-').reverse().join('.'), amount: a.amount.toFixed(2).replace('.', ','), task: a.task_id ?? 0,
    cc: a.cost_center_id ?? 0, ct: a.cost_type_id ?? 0, ref: a.reference, desc: a.description })
  editing.value = a.id
}
async function save() {
  const d = parseDate(f.date), a = parseNum(f.amount)
  if (!d) return toast(tr('Datum ungültig (TT.MM.JJJJ)'), 'error')
  if (!Number.isFinite(a)) return toast(tr('Betrag ungültig'), 'error')
  const body = { booking_date: d, amount: a, task_id: f.task || null, cost_center_id: f.cc || null, cost_type_id: f.ct || null, reference: f.ref, description: f.desc }
  const id = editing.value
  const ok = await finMutate(props.pid, () => (id === 'new' ? api.actualAdd(props.pid, body) : api.actualUpdate(id as number, body)))
  if (ok) { editing.value = null; await load() }
}
async function del(a: Actual) {
  if (confirm(tr('Buchung {1} ({2}) löschen?', { 1: eur(a.amount), 2: a.reference || a.description || a.id })) && await finMutate(props.pid, () => api.actualDelete(a.id))) await load()
}
const tname = (id: number | null) => { const x = state.data?.tasks.find(t => t.id === id); return x ? `${x.wbs} ${x.name}` : '' }

// ── CSV-Import ────────────────────────────────────────────────────────────
const imp = reactive({ open: false, file: null as File | null, create: false, partial: false, report: null as ImportReport | null, busy: false })
const fileEl = ref<HTMLInputElement | null>(null)
function onFile(e: Event) {
  imp.file = (e.target as HTMLInputElement).files?.[0] ?? null
  imp.report = null
  if (imp.file) check()
}
async function check() {
  if (!imp.file) return
  imp.busy = true
  try { imp.report = await api.actualsImport(props.pid, imp.file, { dry_run: true, create_missing: imp.create, partial: imp.partial }) }
  catch (e) { toast((e as Error).message, 'error'); imp.report = null } finally { imp.busy = false }
}
async function run() {
  if (!imp.file) return
  imp.busy = true
  try {
    const r = await api.actualsImport(props.pid, imp.file, { dry_run: false, create_missing: imp.create, partial: imp.partial })
    if (r.imported) { toast(tr('{1} Buchungen importiert ({2})', { 1: r.imported, 2: eur(r.sum) })); imp.open = false; imp.file = null; imp.report = null; offset.value = 0; await refresh() }
    else imp.report = r
  } catch (e) { toast((e as Error).message, 'error') } finally { imp.busy = false }
}
const canRun = computed(() => imp.report && imp.report.valid > 0 && (imp.report.error_count === 0 || imp.partial))
async function exp() { try { await downloadBlob(await api.budgetExport(props.pid, 'actuals'), 'ist-kosten.csv') } catch (e) { toast((e as Error).message, 'error') } }
</script>

<template>
  <div class="ac">
    <div class="bar">
      <input v-model="q" type="search" :placeholder="$t('Suche Belegnummer / Text …')" />
      <span class="dim">{{ $t('{1} Buchungen · Summe', { 1: total }) }} <b>{{ eur(sum) }}</b></span>
      <span class="spacer" />
      <button @click="exp">{{ $t('CSV exportieren') }}</button>
      <template v-if="canEdit"><button @click="imp.open = true">{{ $t('CSV importieren …') }}</button><button class="primary" @click="openNew">{{ $t('+ Buchung') }}</button></template>
    </div>
    <table class="dt">
      <thead><tr><th>{{ $t('Datum') }}</th><th>{{ $t('Beleg') }}</th><th>{{ $t('Text') }}</th><th>{{ $t('Kostenstelle') }}</th><th>{{ $t('Kostenart') }}</th><th>{{ $t('Vorgang') }}</th><th class="n">{{ $t('Betrag') }}</th><th /></tr></thead>
      <tbody>
        <tr v-for="a in rows" :key="a.id">
          <td>{{ fmt(a.booking_date) }}</td><td>{{ a.reference }}</td><td>{{ a.description }} <small v-if="a.source === 'import'" class="dim">{{ $t('(Import)') }}</small></td>
          <td>{{ label(fin.data!.cost_centers, a.cost_center_id, '') }}</td><td>{{ label(fin.data!.cost_types, a.cost_type_id, '') }}</td><td>{{ tname(a.task_id) }}</td>
          <td class="n" :class="{ neg: a.amount < 0 }">{{ eur(a.amount) }}</td>
          <td class="n"><template v-if="canEdit"><button @click="openEdit(a)">✎</button> <button class="danger" @click="del(a)">×</button></template></td>
        </tr>
        <tr v-if="!rows.length"><td colspan="8" class="dim">{{ $t('Keine Buchungen. Erfasse Ist-Kosten manuell oder importiere einen SAP-/Excel-Export (CSV).') }}</td></tr>
      </tbody>
    </table>
    <div v-if="total > PAGE" class="pager">
      <button :disabled="offset === 0" @click="offset -= PAGE; load()">‹</button>
      <span>{{ $t('{1}–{2} von {3}', { 1: offset + 1, 2: Math.min(offset + PAGE, total), 3: total }) }}</span>
      <button :disabled="offset + PAGE >= total" @click="offset += PAGE; load()">›</button>
    </div>

    <!-- Buchung -->
    <div v-if="editing != null" class="modal-back" @mousedown.self="editing = null">
      <form class="modal" @submit.prevent="save">
        <h3>{{ editing === 'new' ? $t('Ist-Kosten buchen') : $t('Buchung ändern') }}</h3>
        <div class="g2"><label>{{ $t('Buchungsdatum') }} <input v-model="f.date" required :placeholder="$t('TT.MM.JJJJ')" /></label>
          <label>{{ $t('Betrag (EUR, Gutschrift negativ)') }} <input v-model="f.amount" required placeholder="0,00" /></label></div>
        <div class="g2">
          <label>{{ $t('Kostenstelle') }} <select v-model.number="f.cc"><option :value="0">–</option><option v-for="c in fin.data!.cost_centers" :key="c.id" :value="c.id">{{ label(fin.data!.cost_centers, c.id) }}</option></select></label>
          <label>{{ $t('Kostenart') }} <select v-model.number="f.ct"><option :value="0">–</option><option v-for="c in fin.data!.cost_types" :key="c.id" :value="c.id">{{ label(fin.data!.cost_types, c.id) }}</option></select></label></div>
        <label>{{ $t('Vorgang (optional)') }} <select v-model.number="f.task"><option :value="0">{{ $t('– keinem Vorgang zugeordnet –') }}</option><option v-for="t in leaves" :key="t.id" :value="t.id">{{ t.wbs }} {{ t.name }}</option></select></label>
        <div class="g2"><label>{{ $t('Belegnummer') }} <input v-model="f.ref" maxlength="80" /></label><label>{{ $t('Text') }} <input v-model="f.desc" maxlength="300" /></label></div>
        <div class="actions"><button type="button" @click="editing = null">{{ $t('Abbrechen') }}</button><button class="primary">{{ $t('Speichern') }}</button></div>
      </form>
    </div>

    <!-- Import -->
    <div v-if="imp.open" class="modal-back" @mousedown.self="imp.open = false">
      <div class="modal wide">
        <h3>{{ $t('Ist-Kosten aus CSV importieren') }}</h3>
        <p class="dim">{{ $t('Erwartete Spalten (Überschriften, Reihenfolge egal):') }} <b>{{ $t('Buchungsdatum') }}</b>, <b>{{ $t('Betrag') }}</b> {{ $t('(Pflicht) sowie') }} <i>{{ $t('Kostenstelle, Kostenart, Belegnummer, Text, Vorgang (PSP-Nr.), Währung') }}</i>{{ $t('. Trennzeichen ; , oder Tab; Zahlen deutsch (1.234,56) oder englisch; nur Währung EUR. Führende Nullen bei SAP-Nummern werden beim Abgleich ignoriert. Buchungen mit gleicher Belegnummer/Kostenstelle/Kostenart/Betrag/Datum gelten als Dublette und werden übersprungen.') }}</p>
        <input ref="fileEl" type="file" accept=".csv,.txt,.tsv" @change="onFile" />
        <div class="opts">
          <label class="chk"><input type="checkbox" v-model="imp.create" @change="check" /> {{ $t('unbekannte Kostenstellen/-arten automatisch anlegen') }}</label>
          <label class="chk"><input type="checkbox" v-model="imp.partial" @change="check" /> {{ $t('trotz fehlerhafter Zeilen die gültigen importieren') }}</label>
        </div>
        <div v-if="imp.busy" class="dim">{{ $t('Prüfe …') }}</div>
        <div v-if="imp.report" class="rep">
          <p><b>{{ imp.report.rows }}</b> {{ $t('Zeilen:') }} <b class="okc">{{ $t('{1} gültig', { 1: imp.report.valid }) }}</b> {{ $t('(Summe {1}), {2} Dubletten,', { 1: eur(imp.report.sum), 2: imp.report.duplicates }) }} <b :class="{ badc: imp.report.error_count }">{{ $t('{1} Fehler', { 1: imp.report.error_count }) }}</b>.
            <span v-if="imp.report.new_cost_centers.length"> {{ $t('Neue Kostenstellen: {1}.', { 1: imp.report.new_cost_centers.join(', ') }) }}</span>
            <span v-if="imp.report.new_cost_types.length"> {{ $t('Neue Kostenarten: {1}.', { 1: imp.report.new_cost_types.join(', ') }) }}</span></p>
          <ul v-if="imp.report.errors.length" class="errs"><li v-for="e in imp.report.errors.slice(0, 12)" :key="e.row">{{ $t('Zeile {1}: {2}', { 1: e.row, 2: e.message }) }}</li>
            <li v-if="imp.report.error_count > 12">{{ $t('… und {1} weitere', { 1: imp.report.error_count - 12 }) }}</li></ul>
          <p v-if="imp.report.error_count && !imp.partial" class="dim">{{ $t('Mit Fehlern wird nichts importiert (Alles-oder-nichts). Korrigiere die Datei oder wähle „gültige importieren".') }}</p>
          <table v-if="imp.report.preview.length" class="dt"><thead><tr><th>Z.</th><th>{{ $t('Datum') }}</th><th>{{ $t('KST') }}</th><th>{{ $t('Kostenart') }}</th><th>{{ $t('Beleg') }}</th><th>{{ $t('Text') }}</th><th class="n">{{ $t('Betrag') }}</th></tr></thead>
            <tbody><tr v-for="p in imp.report.preview" :key="p.row"><td>{{ p.row }}</td><td>{{ fmt(p.booking_date) }}</td><td>{{ p.cc_code }}</td><td>{{ p.ct_code }}</td><td>{{ p.reference }}</td><td>{{ p.description }}</td><td class="n">{{ eur(p.amount) }}</td></tr></tbody></table>
        </div>
        <div class="actions"><button @click="imp.open = false">{{ $t('Schließen') }}</button><button class="primary" :disabled="!canRun || imp.busy" @click="run">{{ $t('{1} Buchungen importieren', { 1: imp.report ? imp.report.valid : 0 }) }}</button></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ac { padding: 12px 18px 40px; }
.bar { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.bar input[type=search] { width: 260px; }
.spacer { flex: 1; } .dim { color: var(--fg-dim); font-size: 12px; }
.dt { border-collapse: collapse; width: 100%; font-size: 13px; }
.dt th, .dt td { text-align: left; padding: 5px 8px; border-bottom: 1px solid var(--border); }
.dt .n { text-align: right; white-space: nowrap; } .neg { color: var(--ok); }
.pager { display: flex; gap: 10px; align-items: center; justify-content: center; margin-top: 10px; }
.g2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.modal.wide { width: 860px; }
.opts { display: flex; flex-direction: column; gap: 4px; margin: 8px 0; }
.rep { border-top: 1px solid var(--border); margin-top: 8px; padding-top: 4px; max-height: 46vh; overflow: auto; }
.okc { color: var(--ok); } .badc { color: var(--bar-critical); }
.errs { color: var(--bar-critical); margin: 4px 0 8px; padding-left: 18px; }
</style>
