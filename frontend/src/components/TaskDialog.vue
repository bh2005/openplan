<script setup lang="ts">
import { dfull, dname } from '../lib/people'
import { computed, reactive, watch } from 'vue'
import { api } from '../lib/api'
import { fmt, parseDate } from '../lib/dates'
import { depToText, parsePreds } from '../lib/deps'
import { mutate, state, toast } from '../lib/store'
import { STATUS } from '../lib/status'
import TaskDocs from './TaskDocs.vue'
import TaskRefs from './TaskRefs.vue'
import TaskComments from './TaskComments.vue'
import type { DirUser, Status, Task } from '../lib/types'
import { t as tr } from '../lib/i18n'

const props = defineProps<{ task: Task; readonly: boolean; worker?: boolean }>()
const limited = computed(() => props.readonly && !!props.worker)     // Mitarbeiter: nur Status, Fortschritt, Blockadegrund; Kommentare/Dokumente
const emit = defineEmits<{ (e: 'close'): void }>()

const d = state.data!
const wbs = (id: number) => d.tasks.find(t => t.id === id)?.wbs
const f = reactive({
  name: props.task.name,
  duration: props.task.duration,
  percent: props.task.percent,
  status: props.task.status as Status,
  status_note: props.task.status_note,
  constraint_type: props.task.constraint_type,
  constraint_date: props.task.constraint_date ? fmt(props.task.constraint_date) : '',
  deadline: props.task.deadline ? fmt(props.task.deadline) : '',
  notes: props.task.notes,
  pool: props.task.pool,
  preds: d.deps.filter(x => x.succ_id === props.task.id).map(x => depToText(x, wbs)).join(', '),
  assign: Object.fromEntries(d.resources.map(r => {
    const a = d.assignments.find(x => x.task_id === props.task.id && x.resource_id === r.id)
    return [r.id, { on: !!a, units: a?.units ?? 100 }]
  })) as Record<number, { on: boolean; units: number }>,
})
const needsDate = computed(() => f.constraint_type !== 'ASAP')

// Person zuordnen: Benutzersuche (Verzeichnis); die verknüpfte Ressource legt der Server bei Bedarf an
const pick = reactive({ q: '', hits: [] as DirUser[], added: [] as { id: number; username: string; units: number }[] })
const linked = new Set(d.resources.map(r => r.user_id).filter((x): x is number => !!x))
let pickTimer: number | undefined
watch(() => pick.q, q => {
  window.clearTimeout(pickTimer)
  if (q.trim().length < 2) { pick.hits = []; return }
  pickTimer = window.setTimeout(async () => {
    try { pick.hits = (await api.directory(q.trim(), 8)).filter(u => !linked.has(u.id) && !pick.added.some(a => a.id === u.id)) } catch { pick.hits = [] }
  }, 250)
})
function addUser(u: DirUser) { pick.added.push({ id: u.id, username: dname(u), units: 100 }); pick.q = ''; pick.hits = [] }

async function save() {
  if (limited.value) {                                   // Mitarbeiter: nur Status/Fortschritt/Blockadegrund
    const t = props.task
    const p: Record<string, unknown> = {}
    if (f.status !== t.status) p.status = f.status
    else if (f.percent !== t.percent) p.percent = Math.min(100, Math.max(0, f.percent))
    if (f.status === 'blocked' && f.status_note !== t.status_note) p.status_note = f.status_note
    if (Object.keys(p).length && !(await mutate(() => api.patchTask(t.id, p)))) return
    return emit('close')
  }
  let cdate: string | null = null
  if (needsDate.value) {
    cdate = parseDate(f.constraint_date)
    if (!cdate) return toast(tr('Constraint-Datum ungültig (TT.MM.JJ)'), 'error')
  }
  let dl: string | null = null
  if (f.deadline.trim()) {
    dl = parseDate(f.deadline)
    if (!dl) return toast(tr('Frist ungültig (TT.MM.JJ)'), 'error')
    if (f.constraint_type === 'SNET' && cdate && cdate > dl) return toast(tr('Erledigungszeitraum: „von“ liegt nach „bis“'), 'error')
  }
  let preds
  try { preds = parsePreds(f.preds, d.tasks) } catch (e) { return toast((e as Error).message, 'error') }
  const t = props.task
  const patch: Record<string, unknown> = {
    name: f.name.trim() || t.name, notes: f.notes, constraint_type: f.constraint_type,
  }
  if (!t.summary) patch.duration = Math.max(0, Math.round(f.duration))
  // Status und Fortschritt sind gekoppelt: ändert der Nutzer den Status, bestimmt dieser den Fortschritt
  if (f.status !== t.status) patch.status = f.status
  else if (!t.summary) patch.percent = Math.min(100, Math.max(0, f.percent))
  if (f.status === 'blocked') patch.status_note = f.status_note
  if (!t.summary && f.pool !== t.pool) patch.pool = f.pool
  if (cdate) patch.constraint_date = cdate
  if (!t.summary) { if (dl) patch.deadline = dl; else if (t.deadline) patch.clear_deadline = true }
  if (!(await mutate(() => api.patchTask(t.id, patch)))) return
  const oldPreds = d.deps.filter(x => x.succ_id === t.id).map(x => depToText(x, wbs)).join(', ')
  if (f.preds.trim() !== oldPreds.trim() && !(await mutate(() => api.setPreds(t.id, preds)))) return
  const items: { resource_id?: number; user_id?: number; units: number }[] = Object.entries(f.assign).filter(([, v]) => v.on).map(([id, v]) => ({ resource_id: Number(id), units: v.units }))
  for (const a of pick.added) items.push({ user_id: a.id, units: a.units })
  if (!(await mutate(() => api.setAssignments(t.id, items)))) return
  emit('close')
}
</script>

<template>
  <div class="modal-back" @mousedown.self="emit('close')">
    <form class="modal" @submit.prevent="save">
      <h3>{{ $t('Vorgang {1}', { 1: task.wbs }) }} <small v-if="task.critical && !task.summary" class="crit">{{ $t('kritisch') }}</small></h3>
      <fieldset :disabled="readonly && !limited" class="plain">
        <label>{{ $t('Name') }} <input v-model="f.name" required maxlength="300" :disabled="limited" /></label>
        <div class="row3">
          <label>{{ $t('Dauer (Arbeitstage)') }} <input v-model.number="f.duration" type="number" min="0" :disabled="task.summary || limited" /></label>
          <label>{{ $t('% fertig') }} <input v-model.number="f.percent" type="number" min="0" max="100" :disabled="task.summary" /></label>
          <label :title="$t('Gesamtpuffer / freier Puffer in Arbeitstagen')">{{ $t('Puffer (gesamt / frei)') }} <input :value="task.total_float == null ? '–' : task.total_float + ' / ' + (task.free_float ?? '–') + ' T'" disabled /></label>
        </div>
        <div class="row2s">
          <label>{{ $t('Status') }}
            <select v-model="f.status"><option v-for="s in STATUS" :key="s.value" :value="s.value">{{ s.label }}</option></select>
            <small v-if="task.summary" class="hint">{{ $t('Sammelvorgang: gilt für alle Teilvorgänge. Erledigt = 100 %, Offen = 0 %.') }}</small>
            <small v-else class="hint">{{ $t('Erledigt setzt den Fortschritt auf 100 %, Offen auf 0 %.') }}</small>
          </label>
          <label v-if="f.status === 'blocked'">{{ $t('Grund der Blockade') }} <input v-model="f.status_note" maxlength="300" :placeholder="$t('z. B. wartet auf Lieferant')" /></label>
        </div>
        <div class="row2" v-if="!task.summary">
          <label>{{ $t('Einschränkung') }}
            <select v-model="f.constraint_type" :disabled="limited">
              <option value="ASAP">{{ $t('So früh wie möglich') }}</option>
              <option value="SNET">{{ $t('Beginn frühestens am') }}</option>
              <option value="MSO">{{ $t('Manuell: Beginn am (fest)') }}</option>
              <option value="FNLT">{{ $t('Ende spätestens am') }}</option>
            </select>
          </label>
          <label>{{ $t('Datum') }} <input v-model="f.constraint_date" :disabled="!needsDate || limited" :placeholder="$t('TT.MM.JJ')" /></label>
        </div>
        <label v-if="!task.summary">{{ $t('Frist: spätestens erledigt bis') }} <input v-model="f.deadline" :disabled="limited" :placeholder="$t('TT.MM.JJ (leer = keine Frist)')" />
          <small class="hint">{{ $t('Zusammen mit „Beginn frühestens am“ ergibt das den') }} <b>{{ $t('Erledigungszeitraum') }}</b> {{ $t('(von – bis). Wird die Frist im Plan überschritten, erscheint ⚠; Erinnerungen und Eskalationen richten sich nach der Frist.') }}</small>
          <small v-if="task.deadline_missed" class="hint" style="color: var(--bar-critical)">{{ $t('⚠ Geplantes Ende {1} liegt nach der Frist.', { 1: fmt(task.finish) }) }}</small>
        </label>
        <label>{{ $t('Vorgänger') }} <input v-model="f.preds" :disabled="limited" :placeholder="$t('PSP-Nr., z. B. 2, 3AA+1T, 4EE-1T')" />
          <small class="hint">{{ $t('EA = Ende→Anfang (Standard) · AA = Anfang→Anfang · EE = Ende→Ende · AE = Anfang→Ende · +/- Verzögerung in Arbeitstagen (T)') }}</small>
        </label>
        <div v-if="!readonly" class="res pick">
          <b>{{ $t('Person zuordnen') }}</b>
          <input v-model="pick.q" type="search" :placeholder="$t('Benutzer suchen (Name oder E-Mail) …')" autocomplete="off" />
          <ul v-if="pick.hits.length" class="hits">
            <li v-for="u in pick.hits" :key="u.id"><button type="button" @click="addUser(u)">+ {{ dfull(u) }}</button></li>
          </ul>
          <small class="hint">{{ $t('Die Person bekommt dadurch automatisch Zugriff auf dieses Projekt (Mitarbeiter: eigene Vorgänge bearbeiten) und sieht die Aufgabe unter „Meine Aufgaben“.') }}</small>
          <div v-for="a in pick.added" :key="a.id" class="resrow">
            <label class="chk">{{ a.username }}</label>
            <input v-model.number="a.units" type="number" min="0" max="1000" class="units" /> %
            <button type="button" class="ghost" :title="$t('Entfernen')" @click="pick.added = pick.added.filter(x => x.id !== a.id)">×</button>
          </div>
        </div>
        <div v-if="d.resources.length" class="res">
          <b>{{ $t('Ressourcen') }}</b>
          <div v-for="r in d.resources" :key="r.id" class="resrow">
            <label class="chk"><input type="checkbox" v-model="f.assign[r.id].on" :disabled="limited" /> {{ r.name }}</label>
            <input v-model.number="f.assign[r.id].units" type="number" min="0" max="1000" :disabled="!f.assign[r.id].on || limited" class="units" /> %
          </div>
        </div>
        <label v-if="!task.summary" class="chk"><input type="checkbox" v-model="f.pool" :disabled="limited" /> {{ $t('Arbeitspaket zur Selbstübernahme (Mitglieder können es im Tab „Pakete“ übernehmen, solange keine Ressource zugeordnet ist)') }}</label>
        <label>{{ $t('Notizen') }} <textarea v-model="f.notes" rows="3" :disabled="limited" /></label>
      </fieldset>
      <TaskRefs :task-id="task.id" :project-id="d.project.id" :can-edit="!readonly" />
      <TaskDocs :task-id="task.id" :project-id="d.project.id" :can-edit="!readonly || limited" />
      <TaskComments :task-id="task.id" :can-edit="!readonly || limited" />
      <div class="actions">
        <button type="button" @click="emit('close')">{{ readonly && !limited ? $t('Schließen') : $t('Abbrechen') }}</button>
        <button v-if="!readonly || limited" class="primary" type="submit">{{ $t('Speichern') }}</button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.row3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.row2 { display: grid; grid-template-columns: 2fr 1fr; gap: 10px; }
.row2s { display: grid; grid-template-columns: 1fr 1.6fr; gap: 10px; align-items: start; }
.res { margin: 10px 0; }
.resrow { display: flex; align-items: center; gap: 8px; margin-top: 4px; }
.chk { flex: 1; display: flex; align-items: center; gap: 6px; margin: 0; }
.pick input[type=search] { width: 100%; margin: 4px 0; }
.hits { list-style: none; margin: 0 0 4px; padding: 0; display: flex; flex-wrap: wrap; gap: 4px; }
.hits button { padding: 2px 8px; }
.units { width: 70px; }
.hint { display: block; color: var(--fg-dim); font-size: 11px; margin-top: 3px; }
.crit { color: var(--bar-critical); font-weight: 600; margin-left: 8px; }
fieldset.plain { border: 0; padding: 0; margin: 0; }
</style>
