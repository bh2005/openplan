<script setup lang="ts">
import { computed, reactive } from 'vue'
import { api } from '../lib/api'
import { fmt } from '../lib/dates'
import { mutate, state, toast } from '../lib/store'
import { STATUS_LABEL } from '../lib/status'
import type { Task } from '../lib/types'
import { t as tr } from '../lib/i18n'

defineProps<{ readonly: boolean; worker?: boolean }>()
const emit = defineEmits<{ (e: 'open', id: number): void }>()
const d = computed(() => state.data!)
const me = computed(() => state.user?.id ?? -1)
const isOwner = computed(() => d.value.access === 'owner')

const pkgs = computed(() => d.value.tasks.filter(t => t.pool && !t.summary))
const resName = (id: number) => d.value.resources.find(r => r.id === id)?.name ?? '?'
const takenBy = (t: Task) => d.value.assignments.filter(a => a.task_id === t.id).map(a => d.value.resources.find(r => r.id === a.resource_id))
const open = computed(() => pkgs.value.filter(t => !t.resource_ids.length && t.status !== 'done'))
const mine = computed(() => pkgs.value.filter(t => takenBy(t).some(r => r?.user_id === me.value)))
const others = computed(() => pkgs.value.filter(t => t.resource_ids.length && !mine.value.includes(t)))

async function claim(t: Task) { await mutate(() => api.claimTask(t.id)) }
async function release(t: Task) { if (confirm(tr('„{1}" zurück in den Pool geben?', { 1: t.name }))) await mutate(() => api.releaseTask(t.id)) }

// Neues Arbeitspaket: direkt zuordnen oder in den Pool stellen
const nw = reactive({ name: '', duration: 3, target: 0, from: '', to: '', parent: 0 })      // target 0 = Pool, sonst Ressourcen-ID; from/to = Erledigungszeitraum (ISO)
const parents = computed(() => d.value.tasks.filter(t => !t.pool && !t.milestone).map(t => ({ id: t.id, label: '\u00a0\u00a0'.repeat(Math.min(t.level, 4)) + t.wbs + ' ' + t.name })))
const badRange = computed(() => !!nw.from && !!nw.to && nw.from > nw.to)
// Erledigungszeitraum: von = „Beginn frühestens“, bis = Frist
const period = (t: Task) => {
  const von = t.constraint_type === 'SNET' && t.constraint_date ? fmt(t.constraint_date) : ''
  const bis = t.deadline ? fmt(t.deadline) : ''
  return von || bis ? `${von || '…'} – ${bis || '…'}` : '–'
}
async function add() {
  const name = nw.name.trim()
  if (!name) return
  if (badRange.value) return toast(tr('Erledigungszeitraum: „von“ liegt nach „bis“'), 'error')
  const before = new Set(d.value.tasks.map(t => t.id))
  if (!(await mutate(() => api.addTask(d.value.project.id, {
    name, duration: Math.max(1, Math.round(nw.duration)), pool: true, ...(nw.parent ? { parent_id: nw.parent } : {}),
    ...(nw.from ? { constraint_type: 'SNET', constraint_date: nw.from } : {}), ...(nw.to ? { deadline: nw.to } : {}),
  })))) return
  const created = d.value.tasks.find(t => !before.has(t.id))
  if (created && nw.target) await mutate(() => api.setAssignments(created.id, [{ resource_id: nw.target, units: 100 }]))
  nw.name = ''; nw.from = ''; nw.to = ''
}
</script>

<template>
  <div class="pk">
    <div v-if="!readonly" class="new">
      <b>{{ $t('Neues Arbeitspaket') }}</b>
      <input v-model="nw.name" :placeholder="$t('Name …')" @keydown.enter="add" />
      <label>{{ $t('Dauer') }} <input v-model.number="nw.duration" type="number" min="1" class="dur" /> T</label>
      <label :title="$t('Das Paket wird unter diesen Vorgang bzw. diese Phase eingeordnet')">{{ $t('gehört zu') }} <select v-model.number="nw.parent"><option :value="0">{{ $t('Oberste Ebene') }}</option><option v-for="p in parents" :key="p.id" :value="p.id">{{ p.label }}</option></select></label>
      <select v-model.number="nw.target" :title="$t('Direkt zuordnen oder in den Pool stellen')">
        <option :value="0">{{ $t('Offen im Pool (Selbstübernahme)') }}</option>
        <option v-for="r in d.resources" :key="r.id" :value="r.id">{{ $t('Zuordnen: {1}', { 1: r.name }) }}</option>
      </select>
      <label :title="$t('Frühester Beginn („von“) und Frist („bis“) des Erledigungszeitraums')">{{ $t('Erledigen von') }} <input v-model="nw.from" type="date" /></label>
      <label>{{ $t('bis') }} <input v-model="nw.to" type="date" :min="nw.from || undefined" /></label>
      <button class="primary" :disabled="badRange" @click="add">{{ $t('Anlegen') }}</button>
      <span v-if="badRange" class="bad">{{ $t('„von“ liegt nach „bis“') }}</span>
    </div>

    <h3>{{ $t('Offen im Pool') }} <span class="n">{{ open.length }}</span></h3>
    <table v-if="open.length" class="tbl">
      <thead><tr><th>{{ $t('PSP') }}</th><th>{{ $t('Arbeitspaket') }}</th><th :title="$t('von = Beginn frühestens, bis = Frist')">{{ $t('Erledigungszeitraum') }}</th><th>{{ $t('Geplant') }}</th><th>{{ $t('Aufwand') }}</th><th /></tr></thead>
      <tbody>
        <tr v-for="t in open" :key="t.id">
          <td>{{ t.wbs }}</td><td><a href="#" @click.prevent="emit('open', t.id)">{{ t.name }}</a></td>
          <td :class="{ miss: t.deadline_missed }">{{ period(t) }}<span v-if="t.deadline_missed" :title="$t('Geplantes Ende liegt nach der Frist')"> ⚠</span></td><td>{{ fmt(t.start) }} – {{ fmt(t.finish) }}</td><td>{{ t.duration }} T</td>
          <td class="act"><button v-if="!readonly || worker" class="primary" @click="claim(t)">{{ $t('Übernehmen') }}</button></td>
        </tr>
      </tbody>
    </table>
    <p v-else class="empty">{{ $t('Keine offenen Arbeitspakete. {1}', { 1: readonly ? '' : $t('Oben anlegen oder im Vorgangsdialog „Arbeitspaket zur Selbstübernahme" aktivieren.') }) }}</p>

    <h3>{{ $t('Von mir übernommen') }} <span class="n">{{ mine.length }}</span></h3>
    <table v-if="mine.length" class="tbl">
      <thead><tr><th>{{ $t('PSP') }}</th><th>{{ $t('Arbeitspaket') }}</th><th>{{ $t('Erledigungszeitraum') }}</th><th>{{ $t('Geplantes Ende') }}</th><th>{{ $t('Status') }}</th><th>%</th><th /></tr></thead>
      <tbody>
        <tr v-for="t in mine" :key="t.id">
          <td>{{ t.wbs }}</td><td><a href="#" @click.prevent="emit('open', t.id)">{{ t.name }}</a></td>
          <td :class="{ miss: t.deadline_missed }">{{ period(t) }}<span v-if="t.deadline_missed"> ⚠</span></td><td>{{ fmt(t.finish) }}</td><td>{{ STATUS_LABEL[t.status] }}</td><td>{{ Math.round(t.percent) }}</td>
          <td class="act"><button v-if="(!readonly || worker) && t.status !== 'done'" @click="release(t)">{{ $t('Zurückgeben') }}</button></td>
        </tr>
      </tbody>
    </table>
    <p v-else class="empty">{{ $t('Du hast noch kein Paket übernommen.') }}</p>

    <template v-if="others.length">
      <h3>{{ $t('Übernommen / zugeordnet') }} <span class="n">{{ others.length }}</span></h3>
      <table class="tbl">
        <thead><tr><th>{{ $t('PSP') }}</th><th>{{ $t('Arbeitspaket') }}</th><th>{{ $t('Bearbeiter') }}</th><th>{{ $t('Erledigungszeitraum') }}</th><th>{{ $t('Geplantes Ende') }}</th><th>{{ $t('Status') }}</th><th /></tr></thead>
        <tbody>
          <tr v-for="t in others" :key="t.id">
            <td>{{ t.wbs }}</td><td><a href="#" @click.prevent="emit('open', t.id)">{{ t.name }}</a></td>
            <td>{{ t.resource_ids.map(resName).join(', ') }}</td><td :class="{ miss: t.deadline_missed }">{{ period(t) }}<span v-if="t.deadline_missed"> ⚠</span></td><td>{{ fmt(t.finish) }}</td><td>{{ STATUS_LABEL[t.status] }}</td>
            <td class="act"><button v-if="isOwner && t.status !== 'done'" @click="release(t)">{{ $t('In den Pool') }}</button></td>
          </tr>
        </tbody>
      </table>
    </template>
  </div>
</template>

<style scoped>
.pk { padding: 16px; max-width: 1100px; }
.new { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--bg-head); }
.new > input:first-of-type { flex: 1; min-width: 180px; } .new label { display: inline-flex; gap: 4px; align-items: center; font-size: 13px; } .dur { width: 60px; }
h3 { margin: 18px 0 6px; } .n { font-size: 12px; font-weight: 400; color: var(--fg-dim); margin-left: 4px; }
.tbl { border-collapse: collapse; width: 100%; font-size: 13px; }
.tbl th, .tbl td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border); }
.miss { color: var(--bar-critical); font-weight: 600; } .bad { color: var(--bar-critical); font-size: 12px; }
.new input[type=date] { width: auto; }
.act { text-align: right !important; white-space: nowrap; } .empty { color: var(--fg-dim); font-size: 13px; }
@media (max-width: 700px) { .new select, .new input:not([type=checkbox]) { max-width: 100%; min-width: 0; } .new select { flex: 1 1 100%; } .new > input:first-of-type { flex: 1 1 100%; } .pk { padding: 10px; } .tbl th:nth-child(1), .tbl td:nth-child(1) { display: none; } }
</style>
