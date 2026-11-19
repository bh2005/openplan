<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, type MyTask } from '../lib/api'
import { fmt } from '../lib/dates'
import { STATUS_LABEL } from '../lib/status'
import { state, toast } from '../lib/store'
import { t as tr } from '../lib/i18n'

const router = useRouter()
const items = ref<MyTask[]>([])
const pool = ref(0)
const loading = ref(true)
const flt = ref<'all' | 'overdue' | 'week' | 'later' | 'blocked'>('all')
const q = ref('')
let timer: number | undefined

async function load() {
  try { const r = await api.myTasks(); items.value = r.items; pool.value = r.pool }
  catch (e) { toast((e as Error).message, 'error') }
  loading.value = false
}
onMounted(() => { state.data = null; load(); timer = window.setInterval(() => { if (!document.hidden) load() }, 60000) })
onBeforeUnmount(() => window.clearInterval(timer))

const count = (b: string) => items.value.filter(i => (b === 'blocked' ? i.status === 'blocked' : i.bucket === b)).length
const norm = (s: string) => s.toLowerCase()
const shown = computed(() => {
  const words = norm(q.value).split(/\s+/).filter(Boolean)
  return items.value.filter(i => {
    const ok = flt.value === 'all' || (flt.value === 'blocked' ? i.status === 'blocked' : i.bucket === flt.value)
    return ok && words.every(w => norm(`${i.project} ${i.wbs} ${i.name} ${i.status_note}`).includes(w))
  })
})
const GROUPS: { key: 'overdue' | 'week' | 'later'; title: string }[] = [
  { key: 'overdue', title: 'Überfällig' }, { key: 'week', title: 'Diese Woche' }, { key: 'later', title: 'Später' },
]
const groups = computed(() => GROUPS.map(g => ({ ...g, rows: shown.value.filter(i => i.bucket === g.key) })).filter(g => g.rows.length))

const busy = ref(0)
async function done(i: MyTask) {
  busy.value = i.id
  try {
    await api.bulkStatus(i.pid, [i.id], 'done')
    items.value = items.value.filter(x => x.id !== i.id)
    toast(tr('„{1}“ erledigt', { 1: i.name }))
  } catch (e) { toast((e as Error).message, 'error') } finally { busy.value = 0 }
}
const open = (i: MyTask) => router.push(`/project/${i.pid}?task=${i.id}`)
const until = (i: MyTask) => fmt(i.deadline || i.finish)
</script>

<template>
  <div class="todo">
    <div class="head">
      <h2>{{ $t('Meine Aufgaben') }} <span class="cnt">{{ items.length }}</span></h2>
      <span class="spacer" />
      <input v-model="q" type="search" class="q" :placeholder="$t('Aufgaben suchen (Projekt, Vorgang) …')" :aria-label="$t('Aufgaben suchen')" />
    </div>
    <nav class="chips">
      <button :class="{ on: flt === 'all' }" @click="flt = 'all'">{{ $t('Alle') }} <span>{{ items.length }}</span></button>
      <button class="late" :class="{ on: flt === 'overdue' }" @click="flt = 'overdue'">{{ $t('Überfällig') }} <span>{{ count('overdue') }}</span></button>
      <button :class="{ on: flt === 'week' }" @click="flt = 'week'">{{ $t('Diese Woche') }} <span>{{ count('week') }}</span></button>
      <button :class="{ on: flt === 'later' }" @click="flt = 'later'">{{ $t('Später') }} <span>{{ count('later') }}</span></button>
      <button class="blk" :class="{ on: flt === 'blocked' }" @click="flt = 'blocked'">{{ $t('Blockiert') }} <span>{{ count('blocked') }}</span></button>
    </nav>
    <p v-if="loading" class="dim">{{ $t('Lade …') }}</p>
    <div v-else-if="!items.length" class="empty">
      <p><b>{{ $t('Keine offenen Aufgaben.') }}</b></p>
      <p class="dim">{{ $t('Hier erscheinen die Vorgänge, die dir zugeordnet sind – über alle Projekte. Voraussetzung: Deine Ressource ist mit deinem Benutzer verknüpft (Tab Ressourcen → Spalte Benutzer).') }}</p>
    </div>
    <p v-else-if="!shown.length" class="dim">{{ $t('Keine Aufgaben für diese Auswahl.') }}</p>
    <section v-for="g in groups" :key="g.key" class="grp" :class="g.key">
      <h3>{{ $t(g.title) }} <span class="cnt">{{ g.rows.length }}</span></h3>
      <ul>
        <li v-for="i in g.rows" :key="i.id" :class="{ blocked: i.status === 'blocked' }">
          <button class="chk" :disabled="busy === i.id" :title="$t('Als erledigt markieren')" :aria-label="$t('Als erledigt markieren')" @click="done(i)">✓</button>
          <div class="main" @click="open(i)">
            <div class="name"><span v-if="i.milestone">◆ </span>{{ i.name }}<span v-if="i.critical" class="crit" :title="$t('Kritischer Pfad')">●</span></div>
            <div class="meta">
              <router-link :to="'/project/' + i.pid" class="proj" @click.stop>{{ i.project }}</router-link>
              <span>{{ i.wbs }}</span>
              <span class="st" :class="i.status">{{ STATUS_LABEL[i.status] }}<template v-if="i.percent"> · {{ i.percent }} %</template></span>
              <span v-if="i.status_note" class="note">⛔ {{ i.status_note }}</span>
            </div>
          </div>
          <div class="due" :class="{ late: i.bucket === 'overdue' }" :title="i.deadline ? $t('Frist') : $t('Ende')">
            <small>{{ i.deadline ? $t('Frist') : $t('Ende') }}</small>{{ until(i) }}
          </div>
        </li>
      </ul>
    </section>
    <p v-if="pool" class="pool dim">📌 {{ $t('{1} offene Arbeitspakete im Pool deiner Projekte – du kannst sie im Tab „Pakete“ übernehmen.', { 1: pool }) }}</p>
  </div>
</template>

<style scoped>
.todo { padding: 18px 22px; overflow: auto; max-width: 900px; }
.head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
.spacer { flex: 1; }
.q { min-width: 240px; }
.cnt { font-size: 12px; font-weight: 400; color: var(--fg-dim); margin-left: 4px; }
.chips { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 14px; }
.chips button { border-radius: 14px; padding: 3px 12px; }
.chips button span { opacity: .7; margin-left: 4px; font-size: 12px; }
.chips button.on { background: var(--accent); border-color: var(--accent); color: #fff; }
.chips button.late:not(.on) { border-color: var(--bar-critical); color: var(--bar-critical); }
.chips button.blk:not(.on) { border-color: var(--blocked); color: var(--blocked); }
.grp { margin-bottom: 18px; }
.grp h3 { font-size: 13px; text-transform: uppercase; letter-spacing: .04em; color: var(--fg-dim); }
.grp.overdue h3 { color: var(--bar-critical); }
ul { list-style: none; margin: 0; padding: 0; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
li { display: flex; align-items: center; gap: 12px; padding: 8px 12px; border-top: 1px solid var(--border); }
li:first-child { border-top: 0; }
li:hover { background: var(--row-alt); }
li.blocked { border-left: 3px solid var(--blocked); }
.chk { width: 26px; height: 26px; padding: 0; border-radius: 50%; color: var(--fg-dim); flex: none; }
.chk:hover:not(:disabled) { background: var(--ok); border-color: var(--ok); color: #fff; }
.main { flex: 1; min-width: 0; cursor: pointer; }
.name { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.crit { color: var(--bar-critical); margin-left: 6px; font-size: 10px; }
.meta { display: flex; gap: 10px; flex-wrap: wrap; font-size: 12px; color: var(--fg-dim); margin-top: 2px; }
.proj { color: var(--accent); text-decoration: none; }
.st.in_progress { color: var(--accent); }
.st.blocked, .note { color: var(--blocked); }
.due { text-align: right; font-size: 13px; white-space: nowrap; flex: none; }
.due small { display: block; font-size: 10px; color: var(--fg-dim); text-transform: uppercase; }
.due.late { color: var(--bar-critical); font-weight: 600; }
.empty { border: 1px dashed var(--border); border-radius: 10px; padding: 18px 22px; max-width: 640px; }
.pool { margin-top: 12px; }
.dim { color: var(--fg-dim); }
@media (max-width: 600px) { .todo { padding: 12px; } .q { min-width: 0; flex: 1; } }
</style>
