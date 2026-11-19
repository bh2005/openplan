<script setup lang="ts">
import { dfull, dname } from '../lib/people'
import type { DirUser } from '../lib/types'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../lib/api'
import { ABSENCE_KINDS, kindIcon, kindLabel } from '../lib/absence'
import { addDays, fmt, todayIso, weekday, WorkCal } from '../lib/dates'
import { mutate, state, toast } from '../lib/store'
import { eur, fin, label, loadFinance } from '../lib/finance'
import { t as tr } from '../lib/i18n'
import UserLink from './UserLink.vue'

const props = defineProps<{ readonly: boolean }>()
const d = computed(() => state.data!)
const nr = reactive({ name: '', funktion: '', reports_to: 0, max_units: 100, cost_rate: 0, cost_center_id: 0, cost_type_id: 0, user_id: 0 })
const edit = ref<number | null>(null)
const ed = reactive({ name: '', funktion: '', reports_to: 0, max_units: 100, cost_rate: 0, cost_center_id: 0, cost_type_id: 0, user_id: 0 })
const nrLabel = ref('')
const bossName = (id?: number | null) => d.value.resources.find(x => x.id === id)?.name ?? ''
const edLabel = ref('')
// Benutzer verknüpfen (Suche nach ID/Name/E-Mail); ist der Ressourcenname noch leer, wird der Anzeigename vorgeschlagen
function linkUser(v: { name: string; user_id: number }, setLabel: (s: string) => void, u: DirUser | null) {
  v.user_id = u ? u.id : 0
  setLabel(u ? dfull(u) : '')
  if (u && !v.name.trim()) v.name = dname(u)
}
const costs = computed(() => d.value.cost_access !== 'none')          // Kostenspalten sichtbar
const costEdit = computed(() => d.value.cost_access === 'edit')       // ... und bearbeitbar
onMounted(() => { if (costs.value && fin.pid !== d.value.project.id) loadFinance(d.value.project.id) })
const payload = (v: typeof nr) => ({ name: v.name.trim(), funktion: v.funktion.trim(), reports_to: v.reports_to || null, max_units: v.max_units, user_id: v.user_id || null,
  ...(costEdit.value ? { cost_rate: v.cost_rate, cost_center_id: v.cost_center_id || null, cost_type_id: v.cost_type_id || null } : {}) })

async function add() {
  if (!nr.name.trim()) return
  if (await mutate(() => api.addResource(d.value.project.id, payload(nr)))) { nr.name = ''; nr.funktion = ''; nr.reports_to = 0; nr.user_id = 0; nrLabel.value = '' }
}
function startEdit(r: { id: number; name: string; funktion?: string; reports_to?: number | null; max_units: number; user_id?: number | null; user_label?: string; cost_rate?: number; cost_center_id?: number | null; cost_type_id?: number | null }) {
  edit.value = r.id
  edLabel.value = r.user_label ?? ''
  Object.assign(ed, { name: r.name, funktion: r.funktion ?? '', reports_to: r.reports_to ?? 0, max_units: r.max_units, user_id: r.user_id ?? 0, cost_rate: r.cost_rate ?? 0, cost_center_id: r.cost_center_id ?? 0, cost_type_id: r.cost_type_id ?? 0 })
}
async function saveEdit() {
  if (edit.value == null) return
  const id = edit.value
  edit.value = null
  await mutate(() => api.updateResource(id, payload(ed)))
}
async function remove(id: number, name: string) {
  if (confirm(tr('Ressource „{1}" löschen? Zuordnungen gehen verloren.', { 1: name }))) await mutate(() => api.deleteResource(id))
}

// Auslastung je Woche (Maximum der Tageswerte in der Woche)
const weeks = computed(() => {
  const tasks = d.value.tasks.filter(t => !t.summary)
  if (!tasks.length) return []
  const min = tasks.reduce((a, t) => (t.start < a ? t.start : a), tasks[0].start)
  const max = tasks.reduce((a, t) => (t.finish > a ? t.finish : a), tasks[0].finish)
  const out: string[] = []
  for (let s = addDays(min, -weekday(min)); s <= max; s = addDays(s, 7)) out.push(s)
  return out
})
const load = computed(() => {
  const cal = new WorkCal(d.value.project.work_days, d.value.project.holidays)
  const tmap = new Map(d.value.tasks.map(t => [t.id, t]))
  const res: Record<number, number[]> = {}
  for (const r of d.value.resources) {
    const cells = weeks.value.map(w => {
      let peak = 0
      for (let i = 0; i < 7; i++) {
        const day = addDays(w, i)
        if (!cal.isWork(day)) continue
        let sum = 0
        for (const a of d.value.assignments) {
          if (a.resource_id !== r.id) continue
          const t = tmap.get(a.task_id)
          if (t && !t.summary && !t.milestone && t.start <= day && day <= t.finish) sum += a.units
        }
        peak = Math.max(peak, sum)
      }
      return peak
    })
    res[r.id] = cells
  }
  return res
})
const wl = (w: string) => fmt(w).slice(0, 5)

// ── Abwesenheiten ─────────────────────────────────────────────────────────
// Bearbeiter/Verantwortliche pflegen alle, Mitarbeiter (nur lesender Zugriff + Zuordnung) die Abwesenheiten der eigenen Ressource.
const canAbsence = (r: { user_id?: number | null }) => d.value.access === 'owner' || d.value.access === 'edit' || (d.value.access === 'work' && r.user_id === state.user?.id)
const absRes = computed(() => d.value.resources.filter(canAbsence))
const absences = computed(() => [...(d.value.absences ?? [])].sort((a, b) => (a.start_date < b.start_date ? -1 : a.start_date > b.start_date ? 1 : a.id - b.id)))
const resName = (id: number) => d.value.resources.find(r => r.id === id)?.name ?? '?'
const resById = (id: number) => d.value.resources.find(r => r.id === id)
const af = reactive({ id: 0, resource_id: 0, start: todayIso(), end: todayIso(), kind: 'vacation' as 'vacation' | 'training' | 'sick' | 'other', note: '' })
watch(absRes, l => { if (!l.some(r => r.id === af.resource_id)) af.resource_id = l[0]?.id ?? 0 }, { immediate: true })
function absReset() { Object.assign(af, { id: 0, start: todayIso(), end: todayIso(), kind: 'vacation', note: '' }) }
function absEdit(a: { id: number; resource_id: number; start_date: string; end_date: string; kind: typeof af.kind; note: string }) {
  Object.assign(af, { id: a.id, resource_id: a.resource_id, start: a.start_date, end: a.end_date, kind: a.kind, note: a.note })
}
async function absSave() {
  const rid = af.resource_id || absRes.value[0]?.id
  if (!rid) return toast(tr('Zuerst eine Ressource anlegen.'), 'error')
  if (!af.start || !af.end) return toast(tr('Beginn und Ende angeben.'), 'error')
  if (af.end < af.start) return toast(tr('Das Ende liegt vor dem Beginn'), 'error')
  const body = { start_date: af.start, end_date: af.end, kind: af.kind, note: af.note }
  const ok = await mutate(() => af.id ? api.updateAbsence(af.id, body) : api.addAbsence(d.value.project.id, { ...body, resource_id: rid }))
  if (ok) absReset()
}
async function absDelete(id: number) { if (confirm(tr('Abwesenheit löschen?'))) await mutate(() => api.deleteAbsence(id)) }
</script>

<template>
  <div class="rp">
    <h3>{{ $t('Ressourcen') }}</h3>
    <table class="tbl">
      <thead><tr><th>{{ $t('Name') }}</th><th :title="$t('Funktion in diesem Projekt, z. B. Projektleiter oder Netzwerktechniker')">{{ $t('Funktion') }}</th><th :title="$t('Vorgesetzte Ressource im Organigramm (leer = Projektleitung)')">{{ $t('Berichtet an') }}</th><th>{{ $t('Max. Verfügbarkeit %') }}</th><th :title="$t('Verknüpfung für „Arbeitspaket übernehmen“')">{{ $t('Benutzer') }}</th>
        <template v-if="costs"><th>{{ $t('Tagessatz (EUR)') }}</th><th>{{ $t('Kostenstelle') }}</th><th>{{ $t('Kostenart') }}</th></template><th /></tr></thead>
      <tbody>
        <tr v-for="r in d.resources" :key="r.id">
          <template v-if="edit === r.id">
            <td><input v-model="ed.name" @keydown.enter="saveEdit" /></td>
            <td><input v-model="ed.funktion" maxlength="120" :placeholder="$t('z. B. Projektleiter')" @keydown.enter="saveEdit" /></td>
            <td><select v-model.number="ed.reports_to"><option :value="0">{{ $t('– Projektleitung –') }}</option><option v-for="x in d.resources.filter(x => x.id !== edit)" :key="x.id" :value="x.id">{{ x.name }}</option></select></td>
            <td><input v-model.number="ed.max_units" type="number" min="0" @keydown.enter="saveEdit" /></td>
            <td><UserLink :user-id="ed.user_id" :label="edLabel" @pick="linkUser(ed, s => (edLabel = s), $event)" /></td>
            <template v-if="costEdit">
              <td><input v-model.number="ed.cost_rate" type="number" min="0" step="0.01" @keydown.enter="saveEdit" /></td>
              <td><select v-model.number="ed.cost_center_id"><option :value="0">–</option><option v-for="c in fin.data?.cost_centers" :key="c.id" :value="c.id">{{ label(fin.data?.cost_centers, c.id) }}</option></select></td>
              <td><select v-model.number="ed.cost_type_id"><option :value="0">–</option><option v-for="c in fin.data?.cost_types" :key="c.id" :value="c.id">{{ label(fin.data?.cost_types, c.id) }}</option></select></td>
            </template>
            <td class="act"><button class="primary" @click="saveEdit">{{ $t('OK') }}</button> <button @click="edit = null">×</button></td>
          </template>
          <template v-else>
            <td>{{ r.name }}</td><td>{{ r.funktion }}</td><td>{{ bossName(r.reports_to) || '–' }}</td><td>{{ r.max_units }}</td><td>{{ r.user_label }}</td>
            <template v-if="costs"><td>{{ eur(r.cost_rate ?? 0) }}</td><td>{{ label(fin.data?.cost_centers, r.cost_center_id) }}</td><td>{{ label(fin.data?.cost_types, r.cost_type_id) }}</td></template>
            <td class="act" v-if="!props.readonly"><button @click="startEdit(r)">{{ $t('Bearbeiten') }}</button> <button class="danger" @click="remove(r.id, r.name)">{{ $t('Löschen') }}</button></td>
            <td v-else />
          </template>
        </tr>
        <tr v-if="!d.resources.length"><td :colspan="costs ? 9 : 6" class="empty">{{ $t('Noch keine Ressourcen angelegt.') }}</td></tr>
        <tr v-if="!props.readonly" class="new">
          <td><input v-model="nr.name" :placeholder="$t('Neue Ressource …')" @keydown.enter="add" /></td>
          <td><input v-model="nr.funktion" maxlength="120" :placeholder="$t('z. B. Projektleiter')" @keydown.enter="add" /></td>
          <td><select v-model.number="nr.reports_to"><option :value="0">{{ $t('– Projektleitung –') }}</option><option v-for="x in d.resources" :key="x.id" :value="x.id">{{ x.name }}</option></select></td>
          <td><input v-model.number="nr.max_units" type="number" min="0" /></td>
          <td><UserLink :user-id="nr.user_id" :label="nrLabel" @pick="linkUser(nr, s => (nrLabel = s), $event)" /></td>
          <template v-if="costEdit">
            <td><input v-model.number="nr.cost_rate" type="number" min="0" step="0.01" /></td>
            <td><select v-model.number="nr.cost_center_id"><option :value="0">–</option><option v-for="c in fin.data?.cost_centers" :key="c.id" :value="c.id">{{ label(fin.data?.cost_centers, c.id) }}</option></select></td>
            <td><select v-model.number="nr.cost_type_id"><option :value="0">–</option><option v-for="c in fin.data?.cost_types" :key="c.id" :value="c.id">{{ label(fin.data?.cost_types, c.id) }}</option></select></td>
          </template>
          <td v-else-if="costs" colspan="3" />
          <td class="act"><button class="primary" @click="add">{{ $t('Hinzufügen') }}</button></td>
        </tr>
      </tbody>
    </table>

    <h3>{{ $t('Abwesenheiten') }} <small>{{ $t('(Urlaub, Schulung … – die Ressource steht an diesen Tagen nicht zur Verfügung)') }}</small></h3>
    <table class="tbl abs">
      <thead><tr><th>{{ $t('Ressource') }}</th><th>{{ $t('Von') }}</th><th>{{ $t('Bis') }}</th><th>{{ $t('Art') }}</th><th>{{ $t('Notiz') }}</th><th /></tr></thead>
      <tbody>
        <tr v-for="a in absences" :key="a.id" :class="{ editing: af.id === a.id }">
          <td>{{ resName(a.resource_id) }}</td><td>{{ fmt(a.start_date) }}</td><td>{{ fmt(a.end_date) }}</td>
          <td>{{ kindIcon(a.kind) }} {{ kindLabel(a.kind) }}</td><td>{{ a.note }}<small v-if="a.source === 'user'" class="dim" :title="$t('Persönlich eingetragen (Meine Abwesenheiten) – gilt in allen Projekten')"> 👤 {{ $t('persönlich') }}</small></td>
          <td class="act"><template v-if="a.source !== 'user' && resById(a.resource_id) && canAbsence(resById(a.resource_id)!)">
            <button @click="absEdit(a)">{{ $t('Bearbeiten') }}</button> <button class="danger" @click="absDelete(a.id)">{{ $t('Löschen') }}</button></template></td>
        </tr>
        <tr v-if="!absences.length"><td colspan="6" class="empty">{{ $t('Keine Abwesenheiten eingetragen.') }}</td></tr>
        <tr v-if="absRes.length" class="new">
          <td><select v-model.number="af.resource_id" :disabled="!!af.id" :aria-label="$t('Ressource')"><option v-for="r in absRes" :key="r.id" :value="r.id">{{ r.name }}</option></select></td>
          <td><input v-model="af.start" type="date" :aria-label="$t('Von')" /></td>
          <td><input v-model="af.end" type="date" :aria-label="$t('Bis')" /></td>
          <td><select v-model="af.kind" :aria-label="$t('Art')"><option v-for="k in ABSENCE_KINDS" :key="k" :value="k">{{ kindLabel(k) }}</option></select></td>
          <td><input v-model="af.note" maxlength="200" :placeholder="$t('Notiz (optional)')" @keydown.enter="absSave" /></td>
          <td class="act"><button class="primary" @click="absSave">{{ af.id ? $t('OK') : $t('Hinzufügen') }}</button> <button v-if="af.id" @click="absReset">×</button></td>
        </tr>
      </tbody>
    </table>

    <h3>{{ $t('Auslastung pro Woche') }} <small>{{ $t('(Spitzenwert; rot = überlastet)') }}</small></h3>
    <div class="loadwrap" v-if="d.resources.length && weeks.length">
      <table class="load">
        <thead><tr><th>{{ $t('Ressource') }}</th><th v-for="w in weeks" :key="w">{{ wl(w) }}</th></tr></thead>
        <tbody>
          <tr v-for="r in d.resources" :key="r.id">
            <th>{{ r.name }}</th>
            <td v-for="(v, i) in load[r.id]" :key="i"
                :class="{ over: v > r.max_units, ok: v > 0 && v <= r.max_units }">{{ v || '' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-else class="empty">{{ $t('Ressourcen anlegen und Vorgängen zuordnen (Doppelklick auf einen Vorgang → Ressourcen).') }}</p>
  </div>
</template>

<style scoped>
.rp { padding: 16px; max-width: 1100px; }
h3 small { font-weight: 400; color: var(--fg-dim); font-size: 12px; }
.tbl { border-collapse: collapse; width: 100%; max-width: 1100px; }
.tbl th, .tbl td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border); }
.tbl input { width: 100%; }
.act { white-space: nowrap; text-align: right !important; }
.empty { color: var(--fg-dim); }
.dim { color: var(--fg-dim); }
.abs tr.editing td { background: var(--row-sel); }
.loadwrap { overflow: auto; border: 1px solid var(--border); border-radius: 6px; }
.load { border-collapse: collapse; font-size: 12px; }
.load th, .load td { padding: 4px 8px; border: 1px solid var(--border); text-align: center; min-width: 44px; }
.load tbody th { text-align: left; position: sticky; left: 0; background: var(--bg-head); }
.load td.ok { background: color-mix(in srgb, var(--ok) 28%, transparent); }
.load td.over { background: color-mix(in srgb, var(--bar-critical) 45%, transparent); font-weight: 700; }
</style>
