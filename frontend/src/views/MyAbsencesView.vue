<script setup lang="ts">
// Persönliche Abwesenheiten: einmal eintragen, gelten in allen Projekten, in denen du als Ressource geführt wirst.
import { computed, onMounted, reactive, ref } from 'vue'
import { api, type MyAbsence } from '../lib/api'
import { ABSENCE_KINDS, kindIcon, kindLabel } from '../lib/absence'
import { fmt, todayIso } from '../lib/dates'
import { state, toast } from '../lib/store'
import { t as tr } from '../lib/i18n'

const items = ref<MyAbsence[]>([])
const loading = ref(true)
const blank = () => ({ id: 0, start: todayIso(), end: todayIso(), kind: 'vacation' as MyAbsence['kind'], note: '' })
const f = reactive(blank())

async function run(fn: () => Promise<MyAbsence[]>) {
  try { items.value = await fn(); return true } catch (e) { toast((e as Error).message, 'error'); return false }
}
onMounted(async () => { state.data = null; await run(() => api.myAbsences()); loading.value = false })

async function save() {
  if (!f.start || !f.end) return toast(tr('Beginn und Ende angeben.'), 'error')
  if (f.end < f.start) return toast(tr('Das Ende liegt vor dem Beginn'), 'error')
  const body = { start_date: f.start, end_date: f.end, kind: f.kind, note: f.note }
  if (await run(() => (f.id ? api.updateMyAbsence(f.id, body) : api.addMyAbsence(body)))) Object.assign(f, blank())
}
function edit(a: MyAbsence) { Object.assign(f, { id: a.id, start: a.start_date, end: a.end_date, kind: a.kind, note: a.note }) }
async function remove(a: MyAbsence) { if (confirm(tr('Abwesenheit löschen?'))) await run(() => api.deleteMyAbsence(a.id)) }
const today = todayIso()
const upcoming = computed(() => items.value.filter(a => a.end_date >= today))
const past = computed(() => items.value.filter(a => a.end_date < today).reverse())
</script>

<template>
  <div class="ma">
    <h2>{{ $t('Meine Abwesenheiten') }}</h2>
    <p class="dim">{{ $t('Trage Urlaub, Schulungen usw. einmal hier ein. Sie gelten in allen Projekten, in denen du als Ressource geführt wirst (Tab Ressourcen → Spalte Benutzer): Dort hast du an diesen Tagen keine Kapazität. „Krank“ sehen andere nur als „Sonstiges“, Notizen bleiben privat.') }}</p>
    <form class="frm" @submit.prevent="save">
      <label>{{ $t('Von') }} <input v-model="f.start" type="date" required /></label>
      <label>{{ $t('Bis') }} <input v-model="f.end" type="date" required /></label>
      <label>{{ $t('Art') }} <select v-model="f.kind"><option v-for="k in ABSENCE_KINDS" :key="k" :value="k">{{ kindLabel(k) }}</option></select></label>
      <label class="grow">{{ $t('Notiz') }} <input v-model="f.note" maxlength="200" :placeholder="$t('Notiz (optional)')" /></label>
      <button class="primary" type="submit">{{ f.id ? $t('OK') : $t('Hinzufügen') }}</button>
      <button v-if="f.id" type="button" @click="Object.assign(f, blank())">×</button>
    </form>
    <p v-if="loading" class="dim">{{ $t('Lade …') }}</p>
    <template v-else>
      <h3>{{ $t('Anstehend') }} <span class="cnt">{{ upcoming.length }}</span></h3>
      <p v-if="!upcoming.length" class="dim">{{ $t('Keine Abwesenheiten eingetragen.') }}</p>
      <ul v-else>
        <li v-for="a in upcoming" :key="a.id" :class="{ editing: f.id === a.id }">
          <span class="ico">{{ kindIcon(a.kind) }}</span>
          <span class="when">{{ fmt(a.start_date) }} – {{ fmt(a.end_date) }}</span>
          <span class="kind">{{ kindLabel(a.kind) }}</span><span class="note">{{ a.note }}</span>
          <span class="act"><button @click="edit(a)">{{ $t('Bearbeiten') }}</button> <button class="danger" @click="remove(a)">{{ $t('Löschen') }}</button></span>
        </li>
      </ul>
      <template v-if="past.length">
        <h3>{{ $t('Vergangen') }} <span class="cnt">{{ past.length }}</span></h3>
        <ul class="old">
          <li v-for="a in past" :key="a.id">
            <span class="ico">{{ kindIcon(a.kind) }}</span><span class="when">{{ fmt(a.start_date) }} – {{ fmt(a.end_date) }}</span>
            <span class="kind">{{ kindLabel(a.kind) }}</span><span class="note">{{ a.note }}</span>
            <span class="act"><button class="danger" @click="remove(a)">{{ $t('Löschen') }}</button></span>
          </li>
        </ul>
      </template>
    </template>
  </div>
</template>

<style scoped>
.ma { padding: 18px 22px; overflow: auto; max-width: 900px; }
.dim { color: var(--fg-dim); } .cnt { font-size: 12px; font-weight: 400; color: var(--fg-dim); margin-left: 4px; }
.frm { display: flex; gap: 10px; align-items: flex-end; flex-wrap: wrap; margin: 12px 0 18px; }
.frm label { display: flex; flex-direction: column; gap: 3px; font-size: 12px; color: var(--fg-dim); } .frm .grow { flex: 1; min-width: 160px; }
ul { list-style: none; margin: 0; padding: 0; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
li { display: flex; align-items: center; gap: 12px; padding: 8px 12px; border-top: 1px solid var(--border); } li:first-child { border-top: 0; }
li.editing { background: var(--row-sel); } .old { opacity: .7; }
.when { font-variant-numeric: tabular-nums; min-width: 150px; } .kind { min-width: 70px; } .note { flex: 1; color: var(--fg-dim); min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.act { white-space: nowrap; }
@media (max-width: 600px) { .ma { padding: 12px; } li { flex-wrap: wrap; gap: 6px 10px; } .note { flex-basis: 100%; } }
</style>
