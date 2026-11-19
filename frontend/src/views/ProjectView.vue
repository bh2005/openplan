<script setup lang="ts">
import { dfull, dname } from '../lib/people'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import GanttChart from '../components/GanttChart.vue'
import TaskGrid from '../components/TaskGrid.vue'
import UserPicker from '../components/UserPicker.vue'
import MobileTaskList from '../components/MobileTaskList.vue'
import { useMobile } from '../lib/mobile'
import TaskDialog from '../components/TaskDialog.vue'
import ResourcesPanel from '../components/ResourcesPanel.vue'
import OrgChart from '../components/OrgChart.vue'
import BudgetPanel from '../components/BudgetPanel.vue'
import CalendarView from '../components/CalendarView.vue'
import TeamPlanner from '../components/TeamPlanner.vue'
import LevelingDialog from '../components/LevelingDialog.vue'
import GanttExportDialog from '../components/GanttExportDialog.vue'
import HolidayLoader from '../components/HolidayLoader.vue'
import PackagesView from '../components/PackagesView.vue'
import DeviceMatrix from '../components/DeviceMatrix.vue'
import BoardView from '../components/BoardView.vue'
import { api, subscribeRevision } from '../lib/api'
import { dayDiff, fmt, parseDate, WorkCal } from '../lib/dates'
import { parsePreds } from '../lib/deps'
import { STATUS } from '../lib/status'
import { mutate, state, toast, ui } from '../lib/store'
import type { DirUser, JournalEntry, Task } from '../lib/types'
import { t as tr, weekdayLong } from '../lib/i18n'

const route = useRoute()
const router = useRouter()
const pid = Number(route.params.id)

const RH = 30
const HH = 44
const tab = ref<'gantt' | 'team' | 'board' | 'packages' | 'devices' | 'calendar' | 'resources' | 'org' | 'budget' | 'journal'>('gantt')
const zoom = ref<'day' | 'week' | 'month'>('day')
const showCritical = ref(true)
const showBaseline = ref(true)
const showFloat = ref(false)                        // Puffer-Spalten + Pufferlinien
const nearDays = ref(2)                             // „knapp kritisch“ bis zu so vielen Tagen Gesamtpuffer
const onlyCritical = ref(false)
const selectedId = ref<number | null>(null)
const selection = reactive(new Set<number>())        // Mehrfachauswahl (Strg/Umschalt-Klick)
const statusFilter = ref<'all' | 'active' | 'open' | 'in_progress' | 'blocked' | 'done'>('all')
const collapsed = reactive(new Set<number>())
const detailId = ref<number | null>(null)
const settings = ref(false)
const leveling = ref(false)
const exportDlg = ref(false)
const journal = ref<JournalEntry[]>([])
const scroller = ref<HTMLElement | null>(null)      // rechter Bereich (Zeitachse), scrollt in beide Richtungen
const leftPane = ref<HTMLElement | null>(null)       // linker Bereich (Tabelle), vertikal synchron zum rechten
const sbH = ref(0)                                   // Höhe der horizontalen Scrollleiste rechts (links als Abstand ausgleichen)
const gridW = computed(() => 800 + (hasBaseline.value && showBaseline.value ? 128 : 0) + (showFloat.value ? 128 : 0))
const widthPref = ref<number | null>(null)
try { const v = Number(localStorage.getItem('openplan.gridw')); if (v) widthPref.value = v } catch { /* privat */ }
const leftWidth = computed(() => (isMobile.value ? 150 : Math.min(Math.max(widthPref.value ?? gridW.value, 300), gridW.value)))
function measureSb() { if (scroller.value) sbH.value = scroller.value.offsetHeight - scroller.value.clientHeight }
function onRightScroll() {
  if (leftPane.value && scroller.value && Math.abs(leftPane.value.scrollTop - scroller.value.scrollTop) > 0.5) leftPane.value.scrollTop = scroller.value.scrollTop
}
function onLeftScroll() {   // z. B. wenn ein Eingabefeld per Fokus in den sichtbaren Bereich scrollt
  if (leftPane.value && scroller.value && Math.abs(leftPane.value.scrollTop - scroller.value.scrollTop) > 0.5) scroller.value.scrollTop = leftPane.value.scrollTop
}
function onLeftWheel(e: WheelEvent) {
  if (!scroller.value || !leftPane.value) return
  if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) leftPane.value.scrollLeft += e.deltaX
  else scroller.value.scrollTop += e.deltaY
}
function startResize(e: PointerEvent) {
  const el = e.currentTarget as HTMLElement
  el.setPointerCapture(e.pointerId)
  const x0 = e.clientX, w0 = leftWidth.value
  const move = (ev: PointerEvent) => { widthPref.value = Math.min(Math.max(w0 + ev.clientX - x0, 300), gridW.value) }
  const up = () => {
    el.removeEventListener('pointermove', move); el.removeEventListener('pointerup', up)
    try { localStorage.setItem('openplan.gridw', String(widthPref.value ?? '')) } catch { /* privat */ }
  }
  el.addEventListener('pointermove', move); el.addEventListener('pointerup', up)
}
function resetWidth() { widthPref.value = null; try { localStorage.removeItem('openplan.gridw') } catch { /* privat */ } }
const openPackages = computed(() => data.value?.tasks.filter(t => t.pool && !t.summary && !t.resource_ids.length && t.status !== 'done').length ?? 0)
const deviceCount = computed(() => data.value?.tasks.filter(t => t.ext_key).length ?? 0)
const gantt = ref<InstanceType<typeof GanttChart> | null>(null)
const loadError = ref('')
const hasBaseline = computed(() => !!data.value?.tasks.some(t => t.baseline_start))

watch(tab, t => (ui.tab = t), { immediate: true })
onBeforeUnmount(() => { ui.tab = 'gantt'; ui.sub = 'overview' })

const data = computed(() => state.data)
const isMobile = useMobile()
const mobileView = ref<'list' | 'chart'>('list')     // Smartphone: Karten-Liste oder Zeitachse
const toolOpen = ref(false)                          // Smartphone: Werkzeugleiste ein-/ausklappen
const readonly = computed(() => !data.value || data.value.access === 'view' || data.value.access === 'work')     // Planen: nur Bearbeiter/Verantwortliche
const worker = computed(() => data.value?.access === 'work')                                                       // Mitarbeiter: eigene Vorgänge (Status, Fortschritt, Kommentare, Dokumente)
const myRes = computed(() => new Set((data.value?.resources ?? []).filter(r => r.user_id === state.user?.id).map(r => r.id)))
const canWork = (t: Task) => !readonly.value || (worker.value && !t.summary && t.resource_ids.some(r => myRes.value.has(r)))
const isOwner = computed(() => data.value?.access === 'owner')
const cal = computed(() => new WorkCal(data.value?.project.work_days ?? [0, 1, 2, 3, 4], data.value?.project.holidays ?? []))
const wbsById = computed(() => Object.fromEntries((data.value?.tasks ?? []).map(t => [t.id, t.wbs])))
const resourceNames = computed(() => Object.fromEntries((data.value?.resources ?? []).map(r => [r.id, r.name])))
const byId = computed(() => new Map((data.value?.tasks ?? []).map(t => [t.id, t])))
const selected = computed(() => (selectedId.value != null ? byId.value.get(selectedId.value) ?? null : null))

const matchesFilter = (t: Task) =>
  (!onlyCritical.value || t.critical) &&
  (statusFilter.value === 'all' || (statusFilter.value === 'active' ? t.status !== 'done' : t.status === statusFilter.value))
const filtered = computed<Task[]>(() => {
  const all = data.value?.tasks ?? []
  if (statusFilter.value === 'all' && !onlyCritical.value) return all
  const keep = new Set<number>()
  const parents = new Map(all.map(t => [t.id, t.parent_id]))
  for (const t of all) {
    if (t.summary || !matchesFilter(t)) continue
    for (let cur: number | null = t.id; cur != null && !keep.has(cur); cur = parents.get(cur) ?? null) keep.add(cur)
  }
  return all.filter(t => keep.has(t.id))
})
const rows = computed(() => {
  const out: Task[] = []
  const hidden = new Set<number>()
  for (const t of filtered.value) {
    if (t.parent_id != null && (hidden.has(t.parent_id) || collapsed.has(t.parent_id))) { hidden.add(t.id); continue }
    out.push(t)
  }
  return out
})
const stats = computed(() => {
  const leaves = (data.value?.tasks ?? []).filter(t => !t.summary)
  const tot = leaves.reduce((a, t) => a + Math.max(t.duration, 0), 0)
  const done = leaves.reduce((a, t) => a + Math.max(t.duration, 0) * t.percent / 100, 0)
  return {
    tasks: leaves.length,
    critical: leaves.filter(t => t.critical).length,
    done: leaves.filter(t => t.status === 'done').length,
    blocked: leaves.filter(t => t.status === 'blocked').length,
    percent: tot ? Math.round(done / tot * 100) : 0,
  }
})

// Deep-Link aus Benachrichtigung/E-Mail: /project/12?task=34 öffnet die Details des Vorgangs
function openFromQuery() {
  const t = Number(route.query.task)
  if (t && data.value?.tasks.some(x => x.id === t)) {
    tab.value = 'gantt'
    onSelect(t, { ctrl: false, shift: false })
    detailId.value = t
  }
  if (route.query.task !== undefined) router.replace({ query: {} })
}
watch(() => route.query.task, v => { if (v !== undefined && data.value) openFromQuery() })

// ── Laden / Polling ──────────────────────────────────────────────────────
let timer: number | undefined
async function load() {
  try {
    state.data = await api.project(pid)
    loadError.value = ''
  } catch (e) { loadError.value = (e as Error).message }
}
async function poll() {
  if (document.hidden || state.busy || !data.value || detailId.value != null) return
  try {
    const r = await api.revision(pid)
    if (r.revision !== data.value.project.revision) await load()
  } catch { /* offline: ignorieren */ }
}
// Live-Updates per SSE; das Polling bleibt als langsamer Rückfallweg (z. B. Proxy ohne Streaming)
let stopStream: (() => void) | undefined
let live = false
let latestRev = 0
let retry: number | undefined
function onRevision(rev: number) {
  latestRev = rev
  if (!data.value || rev === data.value.project.revision) return
  if (state.busy || detailId.value != null) {          // später nachholen (laufende Änderung / offener Dialog)
    if (retry === undefined) retry = window.setTimeout(() => { retry = undefined; onRevision(latestRev) }, 1500)
    return
  }
  load()
}
let ticks = 0
onMounted(async () => {
  state.data = null
  await load()
  await nextTick()
  scrollToToday()
  openFromQuery()
  stopStream = subscribeRevision(pid, onRevision, v => { live = v })
  timer = window.setInterval(() => { if (!live || ++ticks % 8 === 0) poll() }, 8000)   // live: nur alle ~64 s als Sicherheitsnetz
  window.addEventListener('keydown', onKey)
  window.addEventListener('resize', measureSb)
  measureSb()
})
onBeforeUnmount(() => { stopStream?.(); window.clearTimeout(retry); window.clearInterval(timer); window.removeEventListener('keydown', onKey); window.removeEventListener('resize', measureSb) })
watch([() => rows.value.length, zoom, tab], async () => { await nextTick(); measureSb() })
watch(tab, async t => { if (t === 'journal') journal.value = await api.journal(pid).catch(() => []) })

function onSelect(id: number, mods: { ctrl: boolean; shift: boolean }) {
  if (mods.shift && selectedId.value != null) {
    const ids = rows.value.map(r => r.id)
    const a = ids.indexOf(selectedId.value), b = ids.indexOf(id)
    if (a >= 0 && b >= 0) { selection.clear(); ids.slice(Math.min(a, b), Math.max(a, b) + 1).forEach(i => selection.add(i)); return }
  }
  if (mods.ctrl) {
    if (!selection.size && selectedId.value != null) selection.add(selectedId.value)
    selection.has(id) ? selection.delete(id) : selection.add(id)
    selectedId.value = id
    return
  }
  selection.clear()
  selectedId.value = id
}
const targetIds = computed(() => (selection.size ? [...selection] : selectedId.value != null ? [selectedId.value] : []))

async function setStatus(ids: number[], status: string) {
  if (!ids.length) return
  const sums = ids.filter(i => byId.value.get(i)?.summary)
  const label = STATUS.find(s => s.value === status)?.label
  if (sums.length && !confirm(tr('Status „{1}“ für alle Teilvorgänge der gewählten Sammelvorgänge setzen?', { 1: label }))) return
  await mutate(() => api.bulkStatus(pid, ids, status))
}
function onBulkStatus(e: Event) {
  const el = e.target as HTMLSelectElement
  const v = el.value
  el.value = ''
  if (v) setStatus(targetIds.value, v)
}

function scrollToToday() {
  const x = gantt.value?.todayX as number | undefined
  if (scroller.value && x != null) scroller.value.scrollLeft = Math.max(0, x - 140)
}

// ── Aktionen ─────────────────────────────────────────────────────────────
const siblings = (parent: number | null) => (data.value?.tasks ?? []).filter(t => t.parent_id === parent)

async function addTask(milestone = false) {
  const sel = selected.value
  const name = milestone ? tr('Neuer Meilenstein') : tr('Neuer Vorgang')
  const body: Record<string, unknown> = { name, duration: milestone ? 0 : 1 }
  if (sel) body.after_id = sel.id
  if (await mutate(() => api.addTask(pid, body))) {
    const ids = data.value!.tasks.map(t => t.id)
    selectedId.value = Math.max(...ids)
  }
}
async function removeTask() {
  const t = selected.value
  if (!t) return
  const msg = t.summary ? tr('„{1}" samt allen Teilvorgängen löschen?', { 1: t.name }) : tr('„{1}" löschen?', { 1: t.name })
  if (!confirm(msg)) return
  if (await mutate(() => api.deleteTask(t.id))) selectedId.value = null
}
async function indent() {
  const t = selected.value
  if (!t) return
  const sib = siblings(t.parent_id)
  const i = sib.findIndex(s => s.id === t.id)
  if (i <= 0) return toast(tr('Einrücken nicht möglich: kein Vorgänger auf gleicher Ebene'))
  const newParent = sib[i - 1]
  collapsed.delete(newParent.id)
  await mutate(() => api.moveTask(t.id, newParent.id, siblings(newParent.id).length))
}
async function outdent() {
  const t = selected.value
  if (!t || t.parent_id == null) return
  const parent = byId.value.get(t.parent_id)!
  const idx = siblings(parent.parent_id).findIndex(s => s.id === parent.id)
  await mutate(() => api.moveTask(t.id, parent.parent_id, idx + 1))
}
async function shift(dir: -1 | 1) {
  const t = selected.value
  if (!t) return
  const sib = siblings(t.parent_id)
  const i = sib.findIndex(s => s.id === t.id)
  const j = i + dir
  if (j < 0 || j >= sib.length) return
  await mutate(() => api.moveTask(t.id, t.parent_id, j))
}

async function setStart(t: Task, newStart: string) {
  if (t.summary) {   // ganze Phase verschieben
    const days = dayDiff(t.start, newStart)
    if (days) await mutate(() => api.shiftTask(t.id, days))
    return
  }
  const type = t.constraint_type === 'MSO' ? 'MSO' : 'SNET'
  const ok = await mutate(() => api.patchTask(t.id, { constraint_type: type, constraint_date: newStart }))
  if (ok) {
    const nt = byId.value.get(t.id)
    if (nt && nt.start !== newStart && !t.milestone) toast(tr('Beginn durch Vorgänger/Kalender begrenzt – ggf. „Manuell: Beginn am" im Detaildialog wählen'))
  }
}
async function onGridEdit(id: number, field: string, value: string) {
  const t = byId.value.get(id)
  if (!t) return
  const v = value.trim()
  if (field === 'name') {
    if (v && v !== t.name) await mutate(() => api.patchTask(id, { name: v }))
  } else if (field === 'duration') {
    const n = Math.round(Number(v))
    if (!Number.isFinite(n) || n < 0) return toast(tr('Dauer ungültig'), 'error')
    if (n !== t.duration) await mutate(() => api.patchTask(id, { duration: n }))
  } else if (field === 'percent') {
    const n = Number(v)
    if (!Number.isFinite(n) || n < 0 || n > 100) return toast(tr('Prozent ungültig (0–100)'), 'error')
    if (n !== t.percent) await mutate(() => api.patchTask(id, { percent: n }))
  } else if (field === 'start') {
    const d = parseDate(v)
    if (!d) return toast(tr('Datum ungültig (TT.MM.JJ)'), 'error')
    if (d !== t.start) await setStart(t, d)
  } else if (field === 'preds') {
    try { await mutate(() => api.setPreds(id, parsePreds(v, data.value!.tasks))) }
    catch (e) { toast((e as Error).message, 'error') }
  }
}
async function onLink(pred: number, succ: number) {
  const existing = data.value!.deps.filter(d => d.succ_id === succ).map(d => ({ pred_id: d.pred_id, type: d.type, lag: d.lag }))
  if (existing.some(d => d.pred_id === pred)) return toast(tr('Verknüpfung existiert bereits'))
  await mutate(() => api.setPreds(succ, [...existing, { pred_id: pred, type: 'FS', lag: 0 }]))
}

/** Umplanen im Teamplaner: Zuordnung von Ressource `from` auf `to` verschieben (Prozent bleibt erhalten). */
async function reassign(taskId: number, from: number | null, to: number | null) {
  const cur = data.value!.assignments.filter(a => a.task_id === taskId).map(a => ({ resource_id: a.resource_id, units: a.units }))
  const moved = from == null ? { resource_id: to as number, units: 100 } : cur.find(a => a.resource_id === from)
  let next = cur.filter(a => a.resource_id !== from)
  if (to != null && moved && !next.some(a => a.resource_id === to)) next = [...next, { resource_id: to, units: moved.units }]
  await mutate(() => api.setAssignments(taskId, next))
}

async function baseline(clear = false) {
  if (clear) { if (confirm(tr('Basisplan löschen?'))) await mutate(() => api.clearBaseline(pid)) }
  else if (await mutate(() => api.setBaseline(pid))) toast(tr('Basisplan gespeichert'))
}
async function download(fmtName: string) {
  if (fmtName === 'image') { exportDlg.value = true; return }
  try {
    const blob = await api.exportFile(pid, fmtName)
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `${data.value!.project.name.replace(/[^\w-]+/g, '_')}.${fmtName}`
    a.click()
    URL.revokeObjectURL(a.href)
  } catch (e) { toast((e as Error).message, 'error') }
}
const undo = () => mutate(() => api.undo(pid))
const redo = () => mutate(() => api.redo(pid))
function onKey(e: KeyboardEvent) {
  const tag = (e.target as HTMLElement)?.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || detailId.value != null || settings.value) return
  if (readonly.value) return
  if ((e.ctrlKey || e.metaKey) && !e.altKey && ['z', 'y'].includes(e.key.toLowerCase()) && ['gantt', 'team', 'packages', 'resources'].includes(tab.value)) {
    e.preventDefault()
    if (e.key.toLowerCase() === 'y' || e.shiftKey) { if (data.value?.history?.redo) redo() } else if (data.value?.history?.undo) undo()
    return
  }
  if (tab.value !== 'gantt') return
  if (e.key === 'Delete') removeTask()
  else if (e.key === 'Insert') addTask()
  else if (e.altKey && e.key === 'ArrowRight') { e.preventDefault(); indent() }
  else if (e.altKey && e.key === 'ArrowLeft') { e.preventDefault(); outdent() }
  else if (e.altKey && e.key === 'ArrowUp') { e.preventDefault(); shift(-1) }
  else if (e.altKey && e.key === 'ArrowDown') { e.preventDefault(); shift(1) }
}
function toggle(id: number) { collapsed.has(id) ? collapsed.delete(id) : collapsed.add(id) }

// ── Projekteinstellungen ─────────────────────────────────────────────────
const sf = reactive({ name: '', description: '', start: '', days: [] as number[], holidays: '', holidayState: '', ownerId: 0,
  members: [] as { user_id: number; role: 'editor' | 'viewer' }[],
  report_enabled: false, report_weekday: 0, report_hour: 7, report_to: 'owner' as 'owner' | 'members' })
const names = reactive<Record<number, string>>({})                       // id -> Benutzername (aus Mitgliedern/Suche; keine ganze Benutzerliste laden)
const uname = (id: number) => names[id] ?? '#' + id
function pickOwner(u: DirUser) { names[u.id] = dname(u); sf.ownerId = u.id }
function addMember(u: DirUser) {
  names[u.id] = dname(u)
  if (u.id !== sf.ownerId && !sf.members.some(m => m.user_id === u.id)) sf.members.push({ user_id: u.id, role: 'editor' })
}
async function openSettings() {
  const p = data.value!.project
  sf.ownerId = p.owner_id ?? 0
  if (p.owner_id && p.owner) names[p.owner_id] = dname(p.owner)
  for (const m of data.value!.members) names[m.user_id] = dname(m)
  sf.members = data.value!.members.map(m => ({ user_id: m.user_id, role: m.role }))
  Object.assign(sf, { report_enabled: !!p.report_enabled, report_weekday: p.report_weekday ?? 0, report_hour: p.report_hour ?? 7, report_to: p.report_to ?? 'owner' })
  Object.assign(sf, { name: p.name, description: p.description, start: p.start_date.split('-').reverse().join('.'), days: [...p.work_days],
    holidays: p.holidays.map(h => h.split('-').reverse().join('.')).join('\n'), holidayState: p.holiday_state ?? '' })
  settings.value = true
}
async function saveSettings() {
  const hol: string[] = []
  for (const line of sf.holidays.split(/\n|,|;/).map(s => s.trim()).filter(Boolean)) {
    const d = parseDate(line)
    if (!d) return toast(tr('Feiertag ungültig: {1}', { 1: line }), 'error')
    hol.push(d)
  }
  const start = parseDate(sf.start) ?? sf.start
  if (!/^\d{4}-\d{2}-\d{2}$/.test(start)) return toast(tr('Projektstart ungültig'), 'error')
  if (!sf.days.length) return toast(tr('Mindestens ein Arbeitstag nötig'), 'error')
  const oldOwner = data.value!.project.owner_id
  const ownerChanged = sf.ownerId && sf.ownerId !== oldOwner
  // Mitglieder zuerst (der neue Verantwortliche darf nicht gleichzeitig Mitglied sein)
  const members = sf.members.filter(m => m.user_id !== sf.ownerId)
  const ok = await mutate(async () => {
    await api.patchProject(pid, { name: sf.name, description: sf.description, start_date: start, work_days: sf.days, holidays: hol, holiday_state: sf.holidayState,
      report_enabled: sf.report_enabled, report_weekday: sf.report_weekday, report_hour: sf.report_hour, report_to: sf.report_to })
    return api.setMembers(pid, members)
  })
  if (!ok) return
  settings.value = false
  if (ownerChanged) {
    if (!confirm(tr('Verantwortung an „{1}" übertragen? Du verlierst ggf. die Verwaltungsrechte.', { 1: uname(sf.ownerId) }))) return
    state.busy = true
    try {
      const r = await api.patchProject(pid, { owner_id: sf.ownerId })
      if ('transferred' in r) { toast(tr('Verantwortung übertragen')); router.push('/'); return }
      state.data = r
    } catch (e) { toast((e as Error).message, 'error') } finally { state.busy = false }
  }
}
const DAYNAMES = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
const WEEKDAYS = () => [0, 1, 2, 3, 4, 5, 6].map(weekdayLong)
const reportView = ref<{ html: string; recipients: { username: string; email: string }[] } | null>(null)
async function previewReport() {
  try { reportView.value = await api.reportPreview(pid) } catch (e) { toast((e as Error).message, 'error') }
}
async function sendReportNow() {
  if (!confirm(tr('Report jetzt an alle Empfänger verschicken?'))) return
  try { const r = await api.reportSend(pid); toast(tr('Report verschickt: {1} Empfänger, {2} E-Mail(s)', { 1: r.notified, 2: r.mails }) + (r.without_email ? tr(', {1} ohne E-Mail-Adresse', { 1: r.without_email }) : '')) } catch (e) { toast((e as Error).message, 'error') }
}
const reportFrame = (h: string) => `<!doctype html><meta charset="utf-8"><body style="margin:12px;background:#fff">${h}</body>`
const tfmt = (s: string) => s.replace('T', ' ').slice(0, 16)
</script>

<template>
  <div class="pv">
    <div v-if="loadError" class="center err">{{ loadError }} <button @click="router.push('/')">{{ $t('Zur Projektliste') }}</button></div>
    <div v-else-if="!data" class="center">{{ $t('Lade …') }}</div>
    <template v-else>
      <header class="bar">
        <button class="ghost" @click="router.push('/')" :title="$t('Alle Projekte')">←</button>
        <h2 :title="data.project.description">{{ data.project.name }}</h2>
        <div class="chips">
        <span v-if="worker" class="rolechip" :title="$t('Du bist diesem Projekt über eine Zuordnung zugeordnet: Status, Fortschritt, Kommentare und Dokumente deiner Vorgänge kannst du pflegen, geplant wird vom Verantwortlichen.')">{{ $t('Mitarbeiter') }}</span>
        <span class="chip" :title="$t('Projekt-Verantwortlicher')">👤 <b>{{ dname(data.project.owner) || '—' }}</b></span>
        <span class="chip">{{ $t('Ende:') }} <b>{{ fmt(data.project.finish) }}</b></span>
        <span class="chip">{{ $t('{1} Vorgänge', { 1: stats.tasks }) }}</span>
        <span class="chip crit" v-if="stats.critical">{{ $t('{1} kritisch', { 1: stats.critical }) }}</span>
        <span class="chip blk" v-if="stats.blocked" @click="statusFilter = 'blocked'" :title="$t('Nur Blockierte anzeigen')">{{ $t('⛔ {1} blockiert', { 1: stats.blocked }) }}</span>
        <span class="chip">{{ $t('{1}/{2} erledigt', { 1: stats.done, 2: stats.tasks }) }}</span>
        <span class="chip">{{ $t('{1}% fertig', { 1: stats.percent }) }}</span>
        </div>
        <span class="spacer" />
        <nav class="tabs">
          <button :class="{ on: tab === 'gantt' }" @click="tab = 'gantt'">{{ $t('Gantt') }}</button>
          <button :class="{ on: tab === 'team' }" @click="tab = 'team'">{{ $t('Team') }}</button>
          <button :class="{ on: tab === 'board' }" @click="tab = 'board'">{{ $t('Board') }}</button>
          <button :class="{ on: tab === 'packages' }" @click="tab = 'packages'">{{ $t('Pakete') }}<span v-if="openPackages" class="badge">{{ openPackages }}</span></button>
          <button :class="{ on: tab === 'devices' }" @click="tab = 'devices'">{{ $t('Geräte') }}<span v-if="deviceCount" class="badge">{{ deviceCount }}</span></button>
          <button :class="{ on: tab === 'calendar' }" @click="tab = 'calendar'">{{ $t('Kalender') }}</button>
          <button :class="{ on: tab === 'resources' }" @click="tab = 'resources'">{{ $t('Ressourcen') }}</button>
          <button :class="{ on: tab === 'org' }" @click="tab = 'org'">{{ $t('Organigramm') }}</button>
          <button v-if="data.cost_access !== 'none'" :class="{ on: tab === 'budget' }" @click="tab = 'budget'">{{ $t('Budget') }}</button>
          <button :class="{ on: tab === 'journal' }" @click="tab = 'journal'">{{ $t('Verlauf') }}</button>
        </nav>
      </header>

      <div v-if="isMobile && tab === 'gantt'" class="mtool">
        <div class="seg">
          <button :class="{ on: mobileView === 'list' }" @click="mobileView = 'list'">{{ $t('Liste') }}</button>
          <button :class="{ on: mobileView === 'chart' }" @click="mobileView = 'chart'">{{ $t('Zeitachse') }}</button>
        </div>
        <button v-if="!readonly" class="primary" @click="addTask()">{{ $t('+ Vorgang') }}</button>
        <button :class="{ on: toolOpen }" @click="toolOpen = !toolOpen">{{ $t('Werkzeuge') }} {{ toolOpen ? '▴' : '▾' }}</button>
      </div>
      <div class="toolbar" :class="{ mopen: toolOpen }" v-if="tab === 'gantt'">
        <template v-if="!readonly">
          <button :disabled="!data.history?.undo" @click="undo" :title="data.history?.undo ? $t('Rückgängig') + ': ' + data.history.undo.label + ' (' + $t('Strg+Z') + ')' : $t('Nichts zum Rückgängigmachen')">↶</button>
          <button :disabled="!data.history?.redo" @click="redo" :title="data.history?.redo ? $t('Wiederholen') + ': ' + data.history.redo.label + ' (' + $t('Strg+Y') + ')' : $t('Nichts zum Wiederholen')">↷</button>
          <span class="sep" />
          <button class="primary" @click="addTask()" :title="$t('Einfügen (Einfg)')">{{ $t('+ Vorgang') }}</button>
          <button @click="addTask(true)">{{ $t('◆ Meilenstein') }}</button>
          <span class="sep" />
          <button :disabled="!selected" @click="outdent" :title="$t('Ausrücken (Alt+←)')">⇤</button>
          <button :disabled="!selected" @click="indent" :title="$t('Einrücken (Alt+→) – macht den Vorgang zum Teilvorgang')">⇥</button>
          <button :disabled="!selected" @click="shift(-1)" :title="$t('Nach oben (Alt+↑)')">↑</button>
          <button :disabled="!selected" @click="shift(1)" :title="$t('Nach unten (Alt+↓)')">↓</button>
          <button :disabled="!selected" @click="detailId = selectedId" :title="$t('Doppelklick auf Balken/Zeile')">{{ $t('Details') }}</button>
          <button :disabled="!targetIds.length" @click="setStatus(targetIds, 'done')" :title="$t('Auswahl auf Erledigt setzen (Strg/Umschalt-Klick für Mehrfachauswahl)')">{{ $t('✓ Erledigt') }}</button>
          <select :disabled="!targetIds.length" @change="onBulkStatus" :title="$t('Status der Auswahl setzen')">
            <option value="">{{ $t('Status setzen …') }}</option><option v-for="s in STATUS" :key="s.value" :value="s.value">{{ s.label }}</option>
          </select>
          <button :disabled="!selected" class="danger" @click="removeTask" :title="$t('Entf')">{{ $t('Löschen') }}</button>
          <span class="sep" />
        </template>
        <button @click="scrollToToday">{{ $t('Heute') }}</button>
        <select v-model="zoom" :title="$t('Zeitskala')"><option value="day">{{ $t('Tage') }}</option><option value="week">{{ $t('Wochen') }}</option><option value="month">{{ $t('Monate') }}</option></select>
        <select v-model="statusFilter" :title="$t('Vorgänge nach Status filtern')" :class="{ filt: statusFilter !== 'all' }">
          <option value="all">{{ $t('Alle Status') }}</option><option value="active">{{ $t('Nicht erledigt') }}</option><option value="open">{{ $t('Nur Offene') }}</option>
          <option value="in_progress">{{ $t('Nur In Arbeit') }}</option><option value="blocked">{{ $t('Nur Blockierte') }}</option><option value="done">{{ $t('Nur Erledigte') }}</option>
        </select>
        <label class="chk"><input type="checkbox" v-model="showCritical" /> {{ $t('Kritischer Pfad') }}</label>
        <label class="chk"><input type="checkbox" v-model="showBaseline" /> {{ $t('Basisplan') }}</label>
        <label class="chk" :title="$t('Spalten Gesamtpuffer und freier Puffer, Pufferlinien im Gantt, knapp kritische Vorgänge orange')"><input type="checkbox" v-model="showFloat" /> {{ $t('Puffer') }}</label>
        <label v-if="showFloat" class="chk" :title="$t('Vorgänge mit höchstens so vielen Tagen Gesamtpuffer gelten als knapp kritisch')">{{ $t('knapp ≤') }} <input v-model.number="nearDays" type="number" min="0" max="60" class="nd" /> {{ $t('T') }}</label>
        <label class="chk" :title="$t('Nur Vorgänge auf dem kritischen Pfad (mit ihren Phasen) anzeigen')"><input type="checkbox" v-model="onlyCritical" /> {{ $t('Nur kritische') }}</label>
        <span class="spacer" />
        <template v-if="isOwner">
          <button @click="baseline()" :title="$t('Aktuelle Termine als Basisplan speichern')">{{ $t('Basisplan setzen') }}</button>
          <button @click="baseline(true)" v-if="data.tasks.some(t => t.baseline_start)">×</button>
          <button @click="openSettings">{{ $t('Einstellungen') }}</button>
        </template>
        <select @change="e => { const v = (e.target as HTMLSelectElement).value; (e.target as HTMLSelectElement).value = ''; if (v) download(v) }">
          <option value="">{{ $t('Export …') }}</option><option value="image">{{ $t('Bild / PDF für Folien …') }}</option><option value="xml">{{ $t('MS Project (XML)') }}</option><option value="csv">{{ $t('CSV (Excel)') }}</option><option value="json">{{ $t('OpenPlan JSON') }}</option>
        </select>
      </div>

      <MobileTaskList v-if="tab === 'gantt' && isMobile && mobileView === 'list'" :rows="rows" :collapsed="collapsed" :selected-id="selectedId"
                      :resource-names="resourceNames" :readonly="readonly" :can-work="canWork" :tracking="hasBaseline && showBaseline"
                      @open="id => (detailId = id)" @toggle="toggle" @status="(id, s) => setStatus([id], s)" />
      <div v-show="tab === 'gantt' && !(isMobile && mobileView === 'list')" class="split">
        <div class="lpane" ref="leftPane" :style="{ width: leftWidth + 'px' }" @scroll="onLeftScroll" @wheel.prevent="onLeftWheel">
          <div class="lcontent" :style="{ '--grid-w': gridW + 'px', paddingBottom: sbH + 'px' }">
            <TaskGrid :rows="rows" :wbs-by-id="wbsById" :deps="data.deps" :collapsed="collapsed" :selected-id="selectedId" :selected-ids="selection"
                      :readonly="readonly" :can-work="canWork" :row-height="RH" :header-height="HH" :resource-names="resourceNames"
                      :cal="cal" :tracking="hasBaseline && showBaseline" :show-float="showFloat" :near-days="nearDays"
                      @select="onSelect" @status="(id, s) => setStatus([id], s)" @toggle="toggle" @open="id => (detailId = id)" @edit="onGridEdit" />
          </div>
        </div>
        <div class="gutter" :title="$t('Ziehen: Tabellenbreite ändern · Doppelklick: zurücksetzen')" @pointerdown="startResize" @dblclick="resetWidth" />
        <div class="rpane" ref="scroller" @scroll="onRightScroll">
          <GanttChart ref="gantt" :rows="rows" :deps="data.deps" :cal="cal" :zoom="zoom" :row-height="RH" :header-height="HH"
                      :show-critical="showCritical" :show-baseline="showBaseline" :show-float="showFloat" :near-days="nearDays" :selected-id="selectedId" :selected-ids="selection" :readonly="readonly"
                      :resource-names="resourceNames"
                      @select="id => onSelect(id, { ctrl: false, shift: false })" @open="id => (detailId = id)"
                      @move="(id, d) => setStart(byId.get(id)!, d)"
                      @resize="(id, n) => mutate(() => api.patchTask(id, { duration: n }))"
                      @link="onLink" />
          <div v-if="!rows.length" class="emptyhint">
            <p>{{ $t('Noch keine Vorgänge.') }}</p>
            <button v-if="!readonly" class="primary" @click="addTask()">{{ $t('Ersten Vorgang anlegen') }}</button>
          </div>
        </div>
      </div>

      <div v-if="tab === 'budget' && data.cost_access !== 'none'" class="panel"><BudgetPanel :pid="pid" /></div>

      <div v-if="tab === 'team'" class="panel nopad">
        <TeamPlanner :tasks="data.tasks" :resources="data.resources" :assignments="data.assignments" :absences="data.absences ?? []" :cal="cal" :readonly="readonly"
                     @open="id => (detailId = id)" @move="(id, d) => setStart(byId.get(id)!, d)" @reassign="reassign" @level="leveling = true" />
        <LevelingDialog v-if="leveling" :pid="pid" @close="leveling = false" />
      </div>
      <div v-if="tab === 'board'" class="panel nopad"><BoardView :readonly="readonly" :can-work="canWork" :pid="pid" @open="id => (detailId = id)" /></div>
      <div v-if="tab === 'packages'" class="panel"><PackagesView :readonly="readonly" :worker="worker" @open="id => (detailId = id)" /></div>
      <div v-if="tab === 'devices'" class="panel nopad"><DeviceMatrix :readonly="readonly" :pid="pid" @open="id => (detailId = id)" @reload="load" /></div>
      <div v-if="tab === 'calendar'" class="panel nopad">
        <CalendarView :tasks="data.tasks" :resources="data.resources" :assignments="data.assignments" :absences="data.absences ?? []" :cal="cal" @open="id => (detailId = id)" />
      </div>

      <div v-if="tab === 'resources'" class="panel"><ResourcesPanel :readonly="readonly" /></div>
      <div v-if="tab === 'org'" class="panel"><OrgChart :data="data" :editable="!readonly" @move="(rid, p) => mutate(() => api.setReportsTo(rid, p))" /></div>

      <div v-if="tab === 'journal'" class="panel">
        <table class="jt">
          <thead><tr><th>{{ $t('Zeit (UTC)') }}</th><th>{{ $t('Benutzer') }}</th><th>{{ $t('Aktion') }}</th><th>{{ $t('Details') }}</th></tr></thead>
          <tbody>
            <tr v-for="j in journal" :key="j.id"><td>{{ tfmt(j.ts) }}</td><td>{{ j.username }}</td><td>{{ j.action }}</td><td>{{ j.detail }}</td></tr>
            <tr v-if="!journal.length"><td colspan="4" class="empty">{{ $t('Keine Einträge.') }}</td></tr>
          </tbody>
        </table>
      </div>

      <TaskDialog v-if="detailId != null && byId.get(detailId)" :task="byId.get(detailId)!" :readonly="readonly" :worker="canWork(byId.get(detailId)!)" @close="detailId = null" />

      <div v-if="reportView" class="modal-back" @mousedown.self="reportView = null">
        <div class="modal" style="width:min(820px,96vw)">
          <h3>{{ $t('Report-Vorschau') }}</h3>
          <p class="dim">{{ $t('Empfänger') }}: {{ reportView.recipients.map(r => r.username + (r.email ? '' : ' (' + $t('keine E-Mail') + ')')).join(', ') }}</p>
          <iframe sandbox="allow-popups" :srcdoc="reportFrame(reportView.html)" style="width:100%;height:55vh;border:1px solid var(--border);border-radius:6px;background:#fff" />
          <div class="actions"><button type="button" @click="reportView = null">{{ $t('Schließen') }}</button></div>
        </div>
      </div>
      <GanttExportDialog v-if="exportDlg" :tasks="data.tasks" :deps="data.deps" :cal="cal" :resource-names="resourceNames" :project-name="data.project.name" :has-baseline="hasBaseline" @close="exportDlg = false" />
      <div v-if="settings" class="modal-back" @mousedown.self="settings = false">
        <form class="modal" @submit.prevent="saveSettings">
          <h3>{{ $t('Projekteinstellungen') }}</h3>
          <label>{{ $t('Name') }} <input v-model="sf.name" required /></label>
          <label>{{ $t('Beschreibung') }} <textarea v-model="sf.description" rows="2" /></label>
          <label>{{ $t('Projektstart') }} <input v-model="sf.start" :placeholder="$t('TT.MM.JJJJ')" /></label>
          <label>{{ $t('Verantwortlicher (Projektleiter)') }}
            <span class="curowner"><b>{{ uname(sf.ownerId) }}</b></span>
            <UserPicker :no-viewers="true" :placeholder="$t('Anderen Verantwortlichen suchen …')" @pick="pickOwner" />
          </label>
          <div class="members">
            <b>{{ $t('Mitglieder') }}</b> <small class="dim">{{ $t('Editor = darf planen · Leser = nur ansehen') }}</small>
            <div v-for="m in sf.members" :key="m.user_id" class="mrow">
              <span>{{ uname(m.user_id) }}</span>
              <select v-model="m.role"><option value="editor">{{ $t('Editor') }}</option><option value="viewer">{{ $t('Leser') }}</option></select>
              <button type="button" class="danger" @click="sf.members = sf.members.filter(x => x !== m)">×</button>
            </div>
            <div class="mrow">
              <UserPicker :exclude="[sf.ownerId, ...sf.members.map(m => m.user_id)]" :placeholder="$t('Mitglied hinzufügen (Name oder E-Mail suchen) …')" @pick="addMember" />
            </div>
          </div>
          <div class="days">
            <b>{{ $t('Arbeitstage') }}</b>
            <label v-for="(n, i) in DAYNAMES" :key="i" class="chk"><input type="checkbox" :value="i" v-model="sf.days" /> {{ n }}</label>
          </div>
          <label>{{ $t('Feiertage / freie Tage (ein Datum pro Zeile, TT.MM.JJJJ)') }}<textarea v-model="sf.holidays" rows="4" /></label>
          <HolidayLoader v-model:state="sf.holidayState" v-model:text="sf.holidays" :start="sf.start" />
          <fieldset class="rpt">
            <legend>{{ $t('Automatischer Report') }}</legend>
            <label class="chk"><input type="checkbox" v-model="sf.report_enabled" /> {{ $t('Projektreport automatisch per E-Mail und Glocke versenden') }}</label>
            <div v-if="sf.report_enabled" class="rptrow">
              <select v-model.number="sf.report_weekday"><option v-for="(n, i) in WEEKDAYS()" :key="i" :value="i">{{ n }}</option></select>
              {{ $t('ab') }} <input v-model.number="sf.report_hour" type="number" min="0" max="23" class="rn" /> {{ $t('Uhr an') }}
              <select v-model="sf.report_to"><option value="owner">{{ $t('den Verantwortlichen') }}</option><option value="members">{{ $t('alle Mitglieder') }}</option></select>
            </div>
            <div class="rptrow"><button type="button" @click="previewReport">{{ $t('Vorschau') }}</button><button type="button" @click="sendReportNow">{{ $t('Jetzt senden') }}</button></div>
            <small class="dim">{{ $t('Enthält Fortschritt, überfällige und blockierte Vorgänge, anstehende Termine, offene Pool-Pakete und je Empfänger die eigenen offenen Vorgänge – mit Links.') }}</small>
          </fieldset>
          <div class="actions"><button type="button" @click="settings = false">{{ $t('Abbrechen') }}</button><button class="primary" type="submit">{{ $t('Speichern') }}</button></div>
        </form>
      </div>
    </template>
  </div>
</template>

<style scoped>
.curowner { display: block; margin: 2px 0 4px; }
.chips { display: contents; }
.mtool { display: none; }
@media (max-width: 700px) {
  .pv .bar { gap: 6px 8px; padding: 8px 10px; }
  .pv .bar h2 { flex: 1; min-width: 0; font-size: 16px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .pv .bar .spacer { display: none; }
  .pv .chips { display: flex; gap: 6px; flex: 0 0 100%; overflow-x: auto; scrollbar-width: none; padding-bottom: 2px; }
  .pv .chips::-webkit-scrollbar { display: none; }
  .pv .chips .chip, .chips .rolechip { white-space: nowrap; flex: none; }
  .pv .tabs { flex: 0 0 100%; display: flex; overflow-x: auto; scrollbar-width: none; margin: 0 -10px; padding: 0 10px; }
  .pv .tabs::-webkit-scrollbar { display: none; }
  .pv .tabs button { white-space: nowrap; padding: 8px 12px; }
  .pv .mtool { display: flex; gap: 8px; align-items: center; padding: 6px 10px; border-bottom: 1px solid var(--border); background: var(--bg); }
  .pv .mtool .seg { display: inline-flex; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; margin-right: auto; }
  .pv .mtool .seg button { border: 0; border-radius: 0; padding: 6px 12px; }
  .pv .mtool button.on { background: var(--accent); border-color: var(--accent); color: #fff; }
  .pv .mtool > button { padding: 6px 12px; }
  .pv .toolbar { display: none; padding: 8px 10px; }
  .pv .toolbar.mopen { display: flex; }
  .pv .toolbar button, .toolbar select { padding: 6px 10px; }
  .pv .lpane { max-width: 90%; }
}
.rolechip { font-size: 11px; padding: 1px 8px; border-radius: 10px; background: var(--chip); color: var(--fg-dim); align-self: center; }
.pv { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.center { padding: 40px; text-align: center; color: var(--fg-dim); }
.err { color: var(--bar-critical); }
.nd { width: 44px; }
.bar { display: flex; align-items: center; gap: 10px; padding: 8px 14px; border-bottom: 1px solid var(--border); background: var(--bg-head); flex-wrap: wrap; }
.bar h2 { margin: 0; font-size: 17px; }
.chip { font-size: 12px; padding: 2px 8px; border-radius: 10px; background: var(--chip); color: var(--fg-dim); }
.chip.crit { color: var(--bar-critical); }
.chip.blk { color: #fff; background: var(--blocked); cursor: pointer; }
.spacer { flex: 1; }
.tabs button { border-radius: 0; border: 0; border-bottom: 2px solid transparent; background: none; padding: 6px 12px; }
.tabs button.on { border-bottom-color: var(--accent); font-weight: 600; }
.toolbar { display: flex; align-items: center; gap: 6px; padding: 6px 14px; border-bottom: 1px solid var(--border); flex-wrap: wrap; }
select.filt { border-color: var(--accent); background: var(--row-sel); }
.sep { width: 1px; height: 20px; background: var(--border); margin: 0 4px; }
.chk { display: inline-flex; align-items: center; gap: 4px; font-size: 13px; margin: 0 4px; }
.split { flex: 1; min-height: 0; display: flex; position: relative; }
.lpane { flex: none; max-width: 75%; overflow: auto; scrollbar-width: none; }
.lpane::-webkit-scrollbar { display: none; }
.lcontent { width: max-content; min-height: 100%; }
.gutter { flex: none; width: 6px; cursor: col-resize; background: var(--border); transition: background .15s; touch-action: none; }
.gutter:hover { background: var(--accent); }
.rpane { flex: 1; min-width: 0; overflow: auto; position: relative; }
.panel { flex: 1; overflow: auto; }
.badge { margin-left: 5px; padding: 0 6px; border-radius: 9px; background: var(--accent); color: #fff; font-size: 11px; }
.panel.nopad { overflow: hidden; display: flex; flex-direction: column; min-height: 0; }
.panel.nopad > :deep(*) { flex: 1; min-height: 0; }
.emptyhint { position: absolute; left: 20px; top: 70px; color: var(--fg-dim); }
.jt { border-collapse: collapse; width: 100%; font-size: 13px; }
.jt th, .jt td { padding: 6px 12px; border-bottom: 1px solid var(--border); text-align: left; }
.empty { color: var(--fg-dim); }
.members { margin: 8px 0 12px; }
.dim { color: var(--fg-dim); }
.mrow { display: flex; align-items: center; gap: 8px; margin-top: 6px; }
.mrow > span, .mrow > select:first-child { flex: 1; }
.rpt { border: 1px solid var(--border); border-radius: 8px; padding: 8px 12px; margin: 6px 0; display: flex; flex-direction: column; gap: 6px; }
.rptrow { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; } .rn { width: 60px; }
.days { display: flex; gap: 10px; align-items: center; margin: 8px 0; flex-wrap: wrap; }
</style>
