<script setup lang="ts">
import { dfull, dname } from '../lib/people'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api, type DemoKind } from '../lib/api'
import UserPicker from '../components/UserPicker.vue'
import NewProjectWizard from '../components/NewProjectWizard.vue'
import { fmt, parseDate, todayIso } from '../lib/dates'
import { canEdit, isAdmin, state, toast } from '../lib/store'
import type { DirUser } from '../lib/types'
import type { Project } from '../lib/types'
import { t as tr, locale } from '../lib/i18n'

const router = useRouter()
const projects = ref<Project[]>([])
const loading = ref(true)
const creating = ref(false)
const wizard = ref(false)                 // Assistent „Neues Projekt“
function quickCreate() { wizard.value = false; openCreate() }
const ownerName = ref('')
function pickOwner(u: DirUser) { f.owner = u.id; ownerName.value = dname(u) }
const f = reactive({ owner: 0, name: '', description: '', start: todayIso().split('-').reverse().join('.') })
const fileEl = ref<HTMLInputElement | null>(null)

async function load() {
  try { projects.value = await api.projects() } catch (e) { toast((e as Error).message, 'error') }
  loading.value = false
}
onMounted(() => { state.data = null; load() })

// ── Suchen & Filtern (im Browser; Auswahl wird pro Browser gemerkt) ──
type Sort = 'updated' | 'name' | 'start' | 'finish'
const flt = reactive({ q: '', who: 'all' as 'all' | 'mine' | 'other', owner: '', sort: 'updated' as Sort })
try { Object.assign(flt, JSON.parse(localStorage.getItem('openplan.projfilter') ?? '{}'), { q: '' }) } catch { /* privat */ }
watch(() => [flt.who, flt.owner, flt.sort], () => { try { localStorage.setItem('openplan.projfilter', JSON.stringify({ who: flt.who, owner: flt.owner, sort: flt.sort })) } catch { /* privat */ } })
const norm = (s: string) => s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
const owners = computed(() => [...new Set(projects.value.map(p => p.owner_name).filter((x): x is string => !!x))].sort((a, b) => a.localeCompare(b, locale())))
const shown = computed(() => {
  const words = norm(flt.q).split(/\s+/).filter(Boolean)
  const me = state.user?.id
  const list = projects.value.filter(p => {
    const hay = norm(`${p.name} ${p.description} ${p.owner_name ?? ''}`)
    return words.every(w => hay.includes(w))
      && (flt.who === 'all' || (flt.who === 'mine') === (p.owner_id === me))
      && (!flt.owner || p.owner_name === flt.owner)
  })
  const by: Record<Sort, (a: Project, b: Project) => number> = {
    updated: (a, b) => b.updated_at.localeCompare(a.updated_at),
    name: (a, b) => a.name.localeCompare(b.name, locale(), { numeric: true }),
    start: (a, b) => a.start_date.localeCompare(b.start_date),
    finish: (a, b) => (a.finish ?? '9999').localeCompare(b.finish ?? '9999'),
  }
  return [...list].sort(by[flt.sort])
})
const filtered = computed(() => !!(flt.q.trim() || flt.who !== 'all' || flt.owner))
function resetFilter() { Object.assign(flt, { q: '', who: 'all', owner: '' }) }
async function openCreate() {
  f.owner = state.user!.id
  ownerName.value = dname(state.user!)
  creating.value = true
}

async function create() {
  const d = parseDate(f.start)
  if (!d) return toast(tr('Startdatum ungültig (TT.MM.JJJJ)'), 'error')
  try {
    const r = await api.createProject({ name: f.name.trim(), description: f.description, start_date: d, owner_id: f.owner })
    router.push('/project/' + r.project.id)
  } catch (e) { toast((e as Error).message, 'error') }
}
const demoBusy = ref(false)
const demoMenu = ref(false)
const DEMOS: { kind: DemoKind; title: string; text: string }[] = [
  { kind: 'network', title: 'Netzwerk-Rollout Cisco → Extreme', text: '3 Mitarbeiter · 4 Standorte · 60 Geräte – mit Gantt, Abhängigkeiten, Team-Auslastung, Budget und Ist-Kosten.' },
  { kind: 'migration', title: 'Server-Migration Hypervisor → neues Cluster', text: '120 VMs in vier Wellen auf ein neues 4-Node-Cluster – mit Aufbau, Pilot, Wellenplanung, Rückbau, Budget und Ist-Kosten.' },
  { kind: 'release', title: 'Transition Release-Wechsel (ERP 12 → 13)', text: 'Bewertung, Test und Abnahme, Schulung, Cutover, Hypercare und Übergabe in den Betrieb – mit drei Freigabe-Gates.' },
]
async function createDemo(kind: DemoKind = 'network') {
  demoBusy.value = true
  demoMenu.value = false
  try {
    const r = await api.createDemo(kind)
    toast(tr('Beispielprojekt angelegt – du bist Verantwortlicher'))
    router.push('/project/' + r.project.id)
  } catch (e) { toast((e as Error).message, 'error') } finally { demoBusy.value = false }
}
async function onImport(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  ;(e.target as HTMLInputElement).value = ''
  if (!file) return
  try {
    const r = await api.importFile(file)
    toast(tr('Importiert: {1} Vorgänge', { 1: r.tasks.length }))
    router.push('/project/' + r.project.id)
  } catch (err) { toast((err as Error).message, 'error') }
}
async function remove(p: Project) {
  if (!confirm(tr('Projekt „{1}" endgültig löschen?', { 1: p.name }))) return
  try { await api.deleteProject(p.id); await load() } catch (e) { toast((e as Error).message, 'error') }
}
</script>

<template>
  <div class="pl">
    <div class="head">
      <h2>{{ $t('Projekte') }}</h2>
      <span class="spacer" />
      <template v-if="canEdit">
        <input ref="fileEl" type="file" accept=".xml,.json" hidden @change="onImport" />
        <span class="demo-wrap">
          <button :disabled="demoBusy" @click="demoMenu = !demoMenu" :title="$t('Beispielprojekte mit Plan, Basisplan, Kosten und Ist-Buchungen')">{{ $t('Beispielprojekt anlegen') }} ▾</button>
          <div v-if="demoMenu" class="demo-menu" @mouseleave="demoMenu = false">
            <button v-for="d in DEMOS" :key="d.kind" class="demo-item" @click="createDemo(d.kind)"><b>{{ $t(d.title) }}</b><small>{{ $t(d.text) }}</small></button>
          </div>
        </span>
        <button @click="fileEl?.click()" :title="$t('MS-Project-XML (MSPDI) oder OpenPlan-JSON')">{{ $t('Importieren …') }}</button>
        <button class="primary" @click="wizard = true">{{ $t('+ Neues Projekt') }}</button>
      </template>
    </div>

    <div v-if="!loading && projects.length" class="filters">
      <input v-model="flt.q" type="search" class="q" :placeholder="$t('Projekte suchen (Name, Beschreibung, Verantwortlicher) …')" :aria-label="$t('Projekte suchen')" />
      <select v-model="flt.who" :title="$t('Verantwortung')"><option value="all">{{ $t('Alle Projekte') }}</option><option value="mine">{{ $t('Meine (ich bin Verantwortlicher)') }}</option><option value="other">{{ $t('Von anderen') }}</option></select>
      <select v-model="flt.owner" :title="$t('Nach Verantwortlichem filtern')"><option value="">{{ $t('Alle Verantwortlichen') }}</option><option v-for="o in owners" :key="o" :value="o">{{ o }}</option></select>
      <select v-model="flt.sort" :title="$t('Sortierung')"><option value="updated">{{ $t('Zuletzt geändert') }}</option><option value="name">{{ $t('Name A–Z') }}</option><option value="start">{{ $t('Projektstart') }}</option><option value="finish">{{ $t('Projektende') }}</option></select>
      <span class="fcount dim">{{ $t('{1} von {2}', { 1: shown.length, 2: projects.length }) }}</span>
      <button v-if="filtered" class="ghost" @click="resetFilter">{{ $t('Zurücksetzen') }}</button>
    </div>
    <p v-if="loading" class="dim">{{ $t('Lade …') }}</p>
    <div v-else-if="!projects.length && canEdit" class="empty">
      <p>{{ $t('Noch keine Projekte. Am schnellsten siehst du, was OpenPlan kann, mit dem Beispielprojekt:') }}</p>
      <div v-for="d in DEMOS" :key="d.kind" class="demo-card">
        <button class="primary" :disabled="demoBusy" @click="createDemo(d.kind)">{{ $t('Beispielprojekt „{1}“ anlegen', { 1: $t(d.title) }) }}</button>
        <p class="dim">{{ $t(d.text) }}</p>
      </div>
    </div>
    <p v-else-if="!projects.length" class="dim">{{ $t('Keine Projekte sichtbar. Lege ein neues an, importiere eine MS-Project-XML-Datei oder lass dich von einem Projekt-Verantwortlichen hinzufügen.') }}</p>
    <p v-if="!loading && projects.length && !shown.length" class="dim">{{ $t('Keine Projekte passen zu „{1}“.', { 1: flt.q.trim() || $t('dieser Auswahl') }) }} <button class="ghost" @click="resetFilter">{{ $t('Filter zurücksetzen') }}</button></p>
    <div class="grid">
      <router-link v-for="p in shown" :key="p.id" :to="'/project/' + p.id" class="card">
        <h3>{{ p.name }}</h3>
        <p class="desc">{{ p.description || '—' }}</p>
        <div class="meta"><span>👤 {{ p.owner_name ?? '—' }}</span><span>{{ $t('{1} Vorgänge', { 1: p.task_count }) }}</span><span>{{ $t('Start {1}', { 1: fmt(p.start_date) }) }}</span></div>
        <button v-if="p.access === 'owner'" class="danger del" @click.prevent="remove(p)">{{ $t('Löschen') }}</button>
      </router-link>
    </div>

    <NewProjectWizard v-if="wizard" @close="wizard = false" @quick="quickCreate" @created="pid => router.push('/project/' + pid)" />
    <div v-if="creating" class="modal-back" @mousedown.self="creating = false">
      <form class="modal" @submit.prevent="create">
        <h3>{{ $t('Neues Projekt') }}</h3>
        <label>{{ $t('Name') }} <input v-model="f.name" required autofocus maxlength="200" /></label>
        <label>{{ $t('Beschreibung') }} <textarea v-model="f.description" rows="2" /></label>
        <label>{{ $t('Projektstart') }} <input v-model="f.start" :placeholder="$t('TT.MM.JJJJ')" required /></label>
        <label v-if="isAdmin">{{ $t('Verantwortlicher') }}
          <span class="curowner"><b>{{ ownerName }}</b></span>
          <UserPicker :no-viewers="true" :placeholder="$t('Anderen Verantwortlichen suchen …')" @pick="pickOwner" />
        </label>
        <p v-else class="dim">{{ $t('Du wirst Verantwortlicher (Projektleiter) dieses Projekts.') }}</p>
        <div class="actions"><button type="button" @click="creating = false">{{ $t('Abbrechen') }}</button><button class="primary" type="submit">{{ $t('Anlegen') }}</button></div>
      </form>
    </div>
  </div>
</template>

<style scoped>
.curowner { display: block; margin: 2px 0 4px; }
.pl { padding: 18px 22px; overflow: auto; }
.head { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
.spacer { flex: 1; }
@media (max-width: 700px) {
  .head { flex-wrap: wrap; row-gap: 8px; }
  .head h2 { flex: 0 0 100%; margin: 0; }
  .head .spacer { display: none; }
  .head > button, .head .demo-wrap { flex: 1 1 auto; }
  .head .demo-wrap > button { width: 100%; }
  .demo-menu { left: 0; right: auto; width: 100%; max-width: 100vw; }
  .filters .q { min-width: 0; flex: 1 1 100%; max-width: none; }
  .filters select { flex: 1 1 45%; min-width: 0; }
  .grid { grid-template-columns: 1fr; }
  .card h3 { padding-right: 70px; }
}
.demo-wrap { position: relative; }
.demo-menu { position: absolute; right: 0; top: 100%; z-index: 20; margin-top: 4px; width: 380px; max-width: 90vw; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; box-shadow: 0 6px 20px rgba(0, 0, 0, .25); padding: 4px; }
.demo-item { display: block; width: 100%; text-align: left; border: 0; background: none; padding: 8px 10px; border-radius: 6px; }
.demo-item:hover { background: var(--row-sel); }
.demo-item small { display: block; color: var(--fg-dim); margin-top: 2px; }
.demo-card { margin-bottom: 10px; }
.demo-card p { margin: 4px 0 0; }
.dim { color: var(--fg-dim); }
.empty { border: 1px dashed var(--border); border-radius: 10px; padding: 18px 22px; max-width: 640px; }
.filters { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 14px; }
.filters .q { flex: 1; min-width: 240px; max-width: 460px; }
.fcount { font-size: 12px; white-space: nowrap; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }
.card { position: relative; display: block; text-decoration: none; color: var(--fg); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; background: var(--bg-head); }
.card:hover { border-color: var(--accent); }
.card h3 { margin: 0 0 4px; }
.desc { color: var(--fg-dim); margin: 0 0 10px; min-height: 20px; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.meta { display: flex; justify-content: space-between; font-size: 12px; color: var(--fg-dim); }
.del { position: absolute; top: 10px; right: 10px; font-size: 12px; padding: 2px 8px; }
</style>
