<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api } from '../lib/api'
import { fmt } from '../lib/dates'
import { mutate, state, toast } from '../lib/store'
import { STATUS, STATUS_LABEL } from '../lib/status'
import type { Status, Task } from '../lib/types'
import { t as tr } from '../lib/i18n'

/**
 * Kanban-Board: reine Sicht auf die vorhandenen Vorgänge (Blätter). Spalten = Status,
 * Ziehen/Auswahlfeld = Status ändern (gleicher Endpunkt wie im Gantt). Keine eigenen Daten.
 */
const props = defineProps<{ readonly: boolean; canWork: (t: Task) => boolean; pid: number }>()
const emit = defineEmits<{ (e: 'open', id: number): void }>()
const d = computed(() => state.data!)

type Lane = 'none' | 'phase' | 'person'
const LS = 'openplan.boardlane'
const lane = ref<Lane>((() => { try { const v = localStorage.getItem(LS); return v === 'phase' || v === 'person' ? v : 'none' } catch { return 'none' } })())
watch(lane, v => { try { localStorage.setItem(LS, v) } catch { /* ohne Speicher */ } })

const q = ref('')
const onlyMine = ref(false)
const onlyPool = ref(false)
const onlyCrit = ref(false)
const hideDone = ref(false)

const byId = computed(() => new Map(d.value.tasks.map(t => [t.id, t])))
const resName = computed(() => new Map(d.value.resources.map(r => [r.id, r.name])))
const myRes = computed(() => new Set(d.value.resources.filter(r => r.user_id != null && r.user_id === state.user?.id).map(r => r.id)))
const hasMine = computed(() => myRes.value.size > 0)

const ICON: Record<Status, string> = { open: '○', in_progress: '◐', blocked: '⛔', done: '✓' }
const today = computed(() => { const n = new Date(); return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, '0')}-${String(n.getDate()).padStart(2, '0')}` })

// Wartende Vorgänger je Vorgang (nicht erledigte Vorgänger des Vorgangs und seiner Sammelvorgänge)
const waitingOn = computed(() => {
  const m = new Map<number, number>()
  for (const dep of d.value.deps) {
    const p = byId.value.get(dep.pred_id)
    if (p && p.status !== 'done') m.set(dep.succ_id, (m.get(dep.succ_id) ?? 0) + 1)
  }
  return m
})
function waiting(t: Task): number {
  let n = 0
  for (let cur: Task | undefined = t; cur; cur = cur.parent_id != null ? byId.value.get(cur.parent_id) : undefined) n += waitingOn.value.get(cur.id) ?? 0
  return n
}
const phaseOf = (t: Task) => {
  let cur: Task | undefined = t
  while (cur && cur.parent_id != null) cur = byId.value.get(cur.parent_id)
  return cur && cur.id !== t.id ? cur.name : ''
}
const people = (t: Task) => t.resource_ids.map(id => resName.value.get(id)).filter((x): x is string => !!x)
const laneKey = (t: Task) => lane.value === 'phase' ? (phaseOf(t) || tr('Ohne Phase')) : lane.value === 'person' ? (people(t)[0] ?? (t.pool ? tr('Pool (Selbstübernahme)') : tr('Nicht zugeordnet'))) : ''

const cards = computed(() => {
  const words = q.value.toLowerCase().split(/\s+/).filter(Boolean)
  return d.value.tasks.filter(t => {
    if (t.summary) return false
    if (hideDone.value && t.status === 'done') return false
    if (onlyMine.value && !t.resource_ids.some(r => myRes.value.has(r))) return false
    if (onlyPool.value && !(t.pool && !t.resource_ids.length)) return false
    if (onlyCrit.value && !isCrit(t)) return false
    if (words.length) {
      const hay = `${t.wbs} ${t.name} ${t.status_note} ${people(t).join(' ')} ${phaseOf(t)}`.toLowerCase()
      if (!words.every(w => hay.includes(w))) return false
    }
    return true
  })
})
const total = computed(() => d.value.tasks.filter(t => !t.summary).length)

interface Group { key: string; cols: { status: Status; list: Task[] }[]; n: number; done: number }
const groups = computed<Group[]>(() => {
  const m = new Map<string, Task[]>()
  for (const t of cards.value) { const k = laneKey(t); m.set(k, [...(m.get(k) ?? []), t]) }
  let keys = [...m.keys()]
  if (lane.value === 'none' && !keys.length) keys = ['']
  keys.sort((a, b) => lane.value === 'person' ? a.localeCompare(b) : 0)
  return keys.map(key => {
    const list = m.get(key) ?? []
    return { key, n: list.length, done: list.filter(t => t.status === 'done').length,
      cols: STATUS.map(s => ({ status: s.value, list: list.filter(t => t.status === s.value) })) }
  })
})
const colCount = (s: Status) => cards.value.filter(t => t.status === s).length

/** Kritischer Pfad nur für noch nicht erledigte Vorgänge – ein erledigter Vorgang kann nichts mehr verzögern. */
const isCrit = (t: Task) => t.critical && t.status !== 'done'
const can = (t: Task) => !props.readonly || props.canWork(t)
const late = (t: Task) => t.status !== 'done' && (t.deadline_missed || t.finish < today.value)
const period = (t: Task) => (t.milestone ? fmt(t.finish) : `${fmt(t.start)} – ${fmt(t.finish)}`)

// ── Status ändern ──
const busy = ref(false)
async function move(t: Task, status: Status) {
  if (busy.value || t.status === status || !can(t)) return
  const w = waiting(t)
  if ((status === 'in_progress' || status === 'done') && w > 0 &&
      !confirm(tr('„{1}“ hängt von {2} noch nicht erledigten Vorgängern ab. Status trotzdem setzen?', { 1: t.name, 2: w }))) return
  let note = ''
  if (status === 'blocked') {
    const r = prompt(tr('Grund der Blockade (optional)'), t.status_note || '')
    if (r === null) return
    note = r.trim()
  }
  busy.value = true
  try {
    const ok = await mutate(() => note ? api.patchTask(t.id, { status, status_note: note }) : api.bulkStatus(props.pid, [t.id], status))
    if (ok) toast(tr('„{1}“ → {2}', { 1: t.name, 2: STATUS_LABEL[status] }))
  } finally { busy.value = false }
}
function onSelect(e: Event, t: Task) {
  const el = e.target as HTMLSelectElement
  const v = el.value as Status
  el.value = t.status                              // Anzeige zurücksetzen; der Plan liefert den neuen Wert
  move(t, v)
}

// ── Ziehen ──
const dragId = ref<number | null>(null)
const over = ref('')
function dragStart(e: DragEvent, t: Task) {
  if (!can(t)) { e.preventDefault(); return }
  dragId.value = t.id
  if (e.dataTransfer) { e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', String(t.id)) }
}
function dragEnd() { dragId.value = null; over.value = '' }
function dropOn(status: Status) {
  const t = dragId.value != null ? byId.value.get(dragId.value) : undefined
  dragEnd()
  if (t) move(t, status)
}
</script>

<template>
  <div class="board">
    <div class="bar">
      <input v-model="q" class="q" type="search" :placeholder="$t('Suchen: Name, PSP, Person …')" />
      <label class="chk" :title="hasMine ? '' : $t('Du bist in diesem Projekt keiner Ressource zugeordnet')"><input v-model="onlyMine" type="checkbox" :disabled="!hasMine" /> {{ $t('Nur meine') }}</label>
      <label class="chk"><input v-model="onlyPool" type="checkbox" /> {{ $t('Nur Pool') }}</label>
      <label class="chk"><input v-model="onlyCrit" type="checkbox" /> {{ $t('Nur kritische') }}</label>
      <label class="chk"><input v-model="hideDone" type="checkbox" /> {{ $t('Erledigte ausblenden') }}</label>
      <label class="lane">{{ $t('Bahnen') }}
        <select v-model="lane">
          <option value="none">{{ $t('Keine') }}</option>
          <option value="phase">{{ $t('Nach Phase') }}</option>
          <option value="person">{{ $t('Nach Person') }}</option>
        </select>
      </label>
      <span class="cnt">{{ $t('{1} von {2} Vorgängen', { 1: cards.length, 2: total }) }}</span>
    </div>

    <p v-if="!total" class="empty">{{ $t('Noch keine Vorgänge. Das Board zeigt die Vorgänge (ohne Sammelvorgänge) nach Status.') }}</p>
    <template v-else>
      <div class="heads">
        <div v-for="s in STATUS" :key="s.value" class="head" :class="'s-' + s.value">
          <span class="ic">{{ ICON[s.value] }}</span> {{ s.label }} <span class="n">{{ colCount(s.value) }}</span>
        </div>
      </div>

      <section v-for="g in groups" :key="g.key" class="grp">
        <h3 v-if="lane !== 'none'" class="gt">{{ g.key }} <span class="n">{{ $t('{1} von {2} erledigt', { 1: g.done, 2: g.n }) }}</span></h3>
        <div class="cols">
          <div v-for="c in g.cols" :key="c.status" class="col" :class="['s-' + c.status, { over: over === g.key + '|' + c.status }]"
               @dragover.prevent="over = g.key + '|' + c.status" @dragleave="over === g.key + '|' + c.status && (over = '')" @drop.prevent="dropOn(c.status)">
            <div class="mhead" :class="'s-' + c.status">{{ ICON[c.status] }} {{ STATUS_LABEL[c.status] }} <span class="n">{{ c.list.length }}</span></div>
            <article v-for="t in c.list" :key="t.id" class="card" :class="{ crit: isCrit(t), drag: dragId === t.id, late: late(t), locked: !can(t) }"
                     :draggable="can(t)" tabindex="0" :data-task="t.id" :data-status="t.status"
                     @dragstart="dragStart($event, t)" @dragend="dragEnd" @click="emit('open', t.id)" @keydown.enter.self="emit('open', t.id)">
              <div class="top">
                <span class="wbs">{{ t.wbs }}</span>
                <span v-if="t.milestone" class="tag" :title="$t('Meilenstein')">◆</span>
                <span v-if="t.pool && !t.resource_ids.length" class="tag" :title="$t('Im Pool (Selbstübernahme)')">◌</span>
                <span v-if="isCrit(t)" class="tag crit" :title="$t('Kritischer Pfad')">!</span>
                <span v-if="t.comment_count" class="tag" :title="$t('Kommentare')">💬 {{ t.comment_count }}</span>
              </div>
              <div class="nm">{{ t.name }}</div>
              <div v-if="t.status === 'blocked' && t.status_note" class="note">⛔ {{ t.status_note }}</div>
              <div class="meta">
                <span :class="{ miss: late(t) }" :title="t.deadline ? $t('Frist') + ' ' + fmt(t.deadline) : ''">{{ period(t) }}<span v-if="late(t)"> ⚠</span></span>
                <span v-if="t.percent > 0 && t.status !== 'done'" class="pct">{{ Math.round(t.percent) }} %</span>
              </div>
              <div v-if="waiting(t) > 0 && t.status !== 'done'" class="wait" :title="$t('Nicht erledigte Vorgänger')">⛓ {{ $t('wartet auf {1}', { 1: waiting(t) }) }}</div>
              <div class="foot">
                <span class="who">{{ people(t).join(', ') || (t.pool ? $t('Pool') : '–') }}</span>
                <select v-if="can(t)" :value="t.status" class="st" :aria-label="$t('Status ändern')" @click.stop @change="onSelect($event, t)">
                  <option v-for="s in STATUS" :key="s.value" :value="s.value">{{ s.label }}</option>
                </select>
              </div>
            </article>
            <p v-if="!c.list.length" class="none">–</p>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.board { padding: 10px 12px 16px; overflow: auto; }     /* der Tab-Bereich (panel.nopad) scrollt nicht selbst */
.bar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 10px; }
.q { min-width: 220px; flex: 1 1 220px; max-width: 360px; }
.chk, .lane { display: inline-flex; gap: 5px; align-items: center; font-size: 13px; white-space: nowrap; }
.cnt { margin-left: auto; color: var(--fg-dim); font-size: 12.5px; }
.empty { color: var(--fg-dim); padding: 24px 4px; }
.heads { display: none; }
.grp { margin-bottom: 18px; }
.gt { margin: 6px 0 8px; font-size: 14px; display: flex; gap: 8px; align-items: baseline; }
.n { color: var(--fg-dim); font-weight: 400; font-size: 12px; }
.cols { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; align-items: start; }
.col { min-width: 0; background: var(--bg-head); border: 1px solid var(--border); border-top: 3px solid var(--border); border-radius: 8px; padding: 6px; min-height: 90px; transition: background .12s, border-color .12s; }
.col.s-open { border-top-color: var(--fg-dim); }
.col.s-in_progress { border-top-color: var(--accent); }
.col.s-blocked { border-top-color: var(--blocked); }
.col.s-done { border-top-color: var(--ok); }
.col.over { background: color-mix(in srgb, var(--accent) 12%, var(--bg-head)); border-color: var(--accent); }
.mhead { font-size: 12.5px; font-weight: 600; padding: 2px 4px 6px; display: flex; gap: 6px; align-items: baseline; }
.card { background: var(--bg-input); border: 1px solid var(--border); border-left: 4px solid var(--border); border-radius: 7px; padding: 7px 9px; margin-bottom: 7px; cursor: pointer; font-size: 13px; outline: none; }
.card:hover, .card:focus-visible { border-color: var(--accent); box-shadow: 0 1px 6px rgba(0, 0, 0, .12); }
.card[draggable='true'] { cursor: grab; }
.card.drag { opacity: .45; }
.card.locked { cursor: pointer; }
.card.crit { border-left-color: var(--bar-critical); }
.top { display: flex; gap: 6px; align-items: center; color: var(--fg-dim); font-size: 11.5px; }
.wbs { font-variant-numeric: tabular-nums; }
.tag { padding: 0 4px; border-radius: 4px; background: var(--chip); }
.tag.crit { background: var(--bar-critical); color: #fff; font-weight: 700; }
.nm { font-weight: 600; margin: 3px 0; overflow-wrap: anywhere; }
.note { font-size: 12px; color: var(--blocked); margin-bottom: 3px; overflow-wrap: anywhere; }
.meta { display: flex; justify-content: space-between; gap: 8px; font-size: 12px; color: var(--fg-dim); }
.meta .miss { color: var(--bar-critical); font-weight: 600; }
.wait { font-size: 12px; color: var(--blocked); margin-top: 3px; }
.foot { display: flex; justify-content: space-between; align-items: center; gap: 6px; margin-top: 5px; min-height: 22px; }
.who { font-size: 12px; color: var(--fg-dim); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; flex: 1 1 auto; }
.st { font-size: 11.5px; padding: 1px 2px; max-width: 96px; opacity: .55; }
.card:hover .st, .card:focus-within .st { opacity: 1; }
.none { color: var(--fg-dim); text-align: center; margin: 14px 0; }

/* Schmale Fenster / Touch: Spalten nebeneinander wischen; Auswahlfeld immer deutlich sichtbar (Ziehen geht auf Touch nicht) */
@media (max-width: 900px) {
  .cols { display: flex; overflow-x: auto; scroll-snap-type: x mandatory; gap: 10px; padding-bottom: 6px; }
  .col { flex: 0 0 82%; max-width: 82%; scroll-snap-align: start; }
}
@media (hover: none) { .st { opacity: 1; } .card[draggable='true'] { cursor: pointer; } }
</style>
