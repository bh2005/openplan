<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../lib/api'
import { fmt } from '../lib/dates'
import { mutate, state, toast } from '../lib/store'
import { STATUS, STATUS_LABEL } from '../lib/status'
import type { Task, Template } from '../lib/types'
import DeviceImport from './DeviceImport.vue'
import { t as tr } from '../lib/i18n'

const props = defineProps<{ readonly: boolean; pid: number }>()
const emit = defineEmits<{ (e: 'open', id: number): void; (e: 'reload'): void }>()
const d = computed(() => state.data!)

const templates = ref<Template[]>([])
const tplId = ref(0)
const site = ref('')
const q = ref('')
const onlyOpen = ref(false)
const details = ref(false)
const sel = reactive(new Set<number>())
const importing = ref(false)
const adding = ref(false)
const nd = reactive({ template_id: 0, hostname: '', standort: '', modell: '', von: '', bis: '', lieferzeit: '' as number | '' })

onMounted(async () => { try { templates.value = await api.templates() } catch { /* ohne Namen */ } })

const devices = computed(() => d.value.tasks.filter(t => t.ext_key))
const byId = computed(() => new Map(d.value.tasks.map(t => [t.id, t])))
const kids = computed(() => {
  const m = new Map<number, Map<number, Task>>()
  for (const t of d.value.tasks) if (t.tpl_step && t.parent_id != null) { if (!m.has(t.parent_id)) m.set(t.parent_id, new Map()); m.get(t.parent_id)!.set(t.tpl_step, t) }
  return m
})
const usedTpls = computed(() => [...new Set(devices.value.map(t => t.tpl_id).filter((x): x is number => x != null))])
watch(usedTpls, v => { if (!v.includes(tplId.value)) tplId.value = v[0] ?? 0 }, { immediate: true })     // Auswahl immer auf eine vorhandene Vorlage setzen
const tplName = (id: number) => templates.value.find(t => t.id === id)?.name ?? (tr('Vorlage') + ' ' + id)
const curTpl = computed(() => templates.value.find(t => t.id === (tplId.value || usedTpls.value[0])))
const activeTpl = computed(() => tplId.value || usedTpls.value[0] || 0)
const steps = computed(() => curTpl.value?.steps ?? [])
const siteOf = (t: Task) => (t.parent_id != null ? byId.value.get(t.parent_id)?.name ?? '' : '')
const sites = computed(() => [...new Set(devices.value.filter(t => t.tpl_id === activeTpl.value).map(siteOf))])

const rows = computed(() => devices.value.filter(t => {
  if (t.tpl_id !== activeTpl.value) return false
  if (site.value && siteOf(t) !== site.value) return false
  const w = q.value.toLowerCase().split(/\s+/).filter(Boolean)
  if (w.length) { const hay = (t.name + ' ' + Object.values(t.attrs ?? {}).join(' ')).toLowerCase(); if (!w.every(x => hay.includes(x))) return false }
  if (onlyOpen.value && [...(kids.value.get(t.id)?.values() ?? [])].every(k => k.status === 'done')) return false
  return true
}))
const groups = computed(() => {
  const g = new Map<string, Task[]>()
  for (const t of rows.value) g.set(siteOf(t), [...(g.get(siteOf(t)) ?? []), t])
  return [...g.entries()].map(([name, list]) => ({ name, list, done: pct(list) }))
})
function pct(list: Task[]) {
  let n = 0, done = 0
  for (const dev of list) for (const k of kids.value.get(dev.id)?.values() ?? []) { n++; if (k.status === 'done') done++ }
  return n ? Math.round(100 * done / n) : 0
}
const total = computed(() => pct(rows.value))
const cell = (dev: Task, pos: number) => kids.value.get(dev.id)?.get(pos)
const ICON: Record<string, string> = { open: '○', in_progress: '◐', blocked: '⛔', done: '✓' }
const who = (t: Task) => t.resource_ids.map(id => d.value.resources.find(r => r.id === id)?.name).filter(Boolean).join(', ')
const tip = (t: Task) => `${t.name}\n${STATUS_LABEL[t.status]}${t.status_note ? ' – ' + t.status_note : ''}\n${fmt(t.start)} – ${fmt(t.finish)}${t.deadline ? ' · ' + tr('Frist') + ' ' + fmt(t.deadline) : ''}${who(t) ? '\n' + who(t) : '\n' + tr('Im Pool (Selbstübernahme)')}`

// ── Auswahl ──
function click(t: Task, e: MouseEvent) {
  if (e.ctrlKey || e.metaKey || e.shiftKey) { sel.has(t.id) ? sel.delete(t.id) : sel.add(t.id) }
  else { const only = sel.size === 1 && sel.has(t.id); sel.clear(); if (!only) sel.add(t.id) }
}
function selectColumn(pos: number) {
  const ids = rows.value.map(r => cell(r, pos)?.id).filter((x): x is number => x != null)
  const all = ids.length > 0 && ids.every(i => sel.has(i)); for (const i of ids) all ? sel.delete(i) : sel.add(i)
}
function selectRow(dev: Task) {
  const ids = [...(kids.value.get(dev.id)?.values() ?? [])].map(k => k.id)
  const all = ids.every(i => sel.has(i)); for (const i of ids) all ? sel.delete(i) : sel.add(i)
}
function selectGroup(list: Task[]) { for (const dev of list) for (const k of kids.value.get(dev.id)?.values() ?? []) sel.add(k.id) }
async function setStatus(status: string) {
  if (!sel.size || !status) return
  const ids = [...sel]
  if (await mutate(() => api.bulkStatus(props.pid, ids, status))) { toast(tr('{1} Schritt(e) → {2}', { 1: ids.length, 2: STATUS_LABEL[status as keyof typeof STATUS_LABEL] })); sel.clear() }
}

// ── Gerät aus Vorlage ──
async function openAdd() { nd.template_id = activeTpl.value || templates.value[0]?.id || 0; Object.assign(nd, { hostname: '', standort: site.value, modell: '', von: '', bis: '', lieferzeit: '' }); adding.value = true }
async function addDevice() {
  if (!nd.hostname.trim() || !nd.template_id) return
  if (nd.von && nd.bis && nd.von > nd.bis) return toast(tr('Wartungsfenster: „von“ liegt nach „bis“'), 'error')
  if (await mutate(() => api.addDevice(props.pid, { template_id: nd.template_id, hostname: nd.hostname.trim(), standort: nd.standort.trim(), modell: nd.modell,
    fenster_von: nd.von || null, fenster_bis: nd.bis || null, lieferzeit: nd.lieferzeit === '' ? null : nd.lieferzeit }))) { adding.value = false; tplId.value = nd.template_id }
}
function exportCsv() {
  const head = [tr('Standort'), 'Hostname', tr('Modell'), 'IP', ...steps.value.map(s => s.name)]
  const lines = [head]
  for (const g of groups.value) for (const dev of g.list) lines.push([g.name, dev.name, dev.attrs?.modell ?? '', dev.attrs?.ip ?? '', ...steps.value.map(s => { const c = cell(dev, s.position); return c ? STATUS_LABEL[c.status] : '' })])
  const csv = '﻿' + lines.map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(';')).join('\r\n')
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' })); a.download = `geraete-${curTpl.value?.name ?? 'liste'}.csv`; a.click(); URL.revokeObjectURL(a.href)
}
const siteList = computed(() => [...new Set(d.value.tasks.filter(t => t.summary && !t.ext_key && devices.value.some(x => x.parent_id === t.id)).map(t => t.name))])
</script>

<template>
  <div class="dm">
    <div class="bar">
      <template v-if="usedTpls.length">
        <label class="inl">{{ $t('Vorlage') }} <select v-model.number="tplId"><option v-for="id in usedTpls" :key="id" :value="id">{{ tplName(id) }}</option></select></label>
        <select v-model="site" :title="$t('Standort')"><option value="">{{ $t('Alle Standorte') }}</option><option v-for="s in sites" :key="s" :value="s">{{ s }}</option></select>
        <input v-model="q" type="search" :placeholder="$t('Gerät suchen (Hostname, Modell, IP …)')" class="q" :aria-label="$t('Geräte suchen')" />
        <label class="chk"><input type="checkbox" v-model="onlyOpen" /> {{ $t('nur unfertige') }}</label>
        <label class="chk"><input type="checkbox" v-model="details" /> {{ $t('Details') }}</label>
      </template>
      <span class="spacer" />
      <template v-if="!readonly">
        <button @click="importing = true">{{ $t('Geräteliste importieren …') }}</button>
        <button @click="openAdd">{{ $t('+ Gerät aus Vorlage') }}</button>
      </template>
      <button v-if="rows.length" @click="exportCsv">{{ $t('CSV-Export') }}</button>
    </div>

    <div v-if="!devices.length" class="empty">
      <p><b>{{ $t('Noch keine Geräte.') }}</b> {{ $t('Lade eine Geräteliste (Excel/CSV) hoch – aus jeder Zeile entstehen die Arbeitsschritte des Gerätetyps (bestellen, liefern, konfigurieren, austauschen, testen …) mit Zuordnung, Terminen und Kosten.') }}</p>
      <p v-if="!readonly"><button class="primary" @click="importing = true">{{ $t('Geräteliste importieren …') }}</button> <button @click="openAdd">{{ $t('Einzelnes Gerät anlegen') }}</button></p>
      <p class="dim">{{ $t('Die Schritte je Gerätetyp pflegst du unter') }} <router-link to="/templates">{{ $t('Vorlagen') }}</router-link>.</p>
    </div>

    <template v-else>
      <div class="sbar" v-if="!readonly">
        <b>{{ sel.size }}</b> {{ $t('Schritt(e) gewählt') }}
        <button v-for="s in STATUS" :key="s.value" :disabled="!sel.size" @click="setStatus(s.value)">{{ ICON[s.value] }} {{ s.label }}</button>
        <button :disabled="!sel.size" @click="sel.clear()">{{ $t('Auswahl aufheben') }}</button>
        <span class="dim">{{ $t('Klick = wählen · Strg-Klick = ergänzen · Kopf-/Zeilen-Klick = Spalte/Zeile · Doppelklick = Details') }}</span>
        <span class="spacer" /><span class="dim">{{ $t('{1} Geräte · {2} % der Schritte erledigt', { 1: rows.length, 2: total }) }}</span>
      </div>
      <div class="scroll">
        <table class="mx">
          <thead><tr>
            <th class="host">{{ $t('Gerät') }}</th><th v-if="details" class="det">{{ $t('Modell') }}</th><th v-if="details" class="det">{{ $t('IP') }}</th><th class="pc">%</th>
            <th v-for="s in steps" :key="s.position" class="st" :title="s.name + (s.role ? ' · ' + s.role : '') + ' – ' + $t('Klick wählt die Spalte')" @click="selectColumn(s.position)"><span>{{ s.position }}. {{ s.name }}</span><small>{{ s.role }}</small></th>
          </tr></thead>
          <tbody v-for="g in groups" :key="g.name">
            <tr class="grp"><td :colspan="(details ? 4 : 2) + steps.length" @click="selectGroup(g.list)" :title="$t('Klick wählt alle Schritte dieses Standorts')"><b>{{ g.name || $t('Ohne Standort') }}</b> <span class="dim">{{ $t('{1} Geräte · {2} % erledigt', { 1: g.list.length, 2: g.done }) }}</span></td></tr>
            <tr v-for="dev in g.list" :key="dev.id">
              <td class="host" @click="selectRow(dev)" @dblclick="emit('open', dev.id)" :title="$t('Klick wählt alle Schritte des Geräts, Doppelklick öffnet die Details')"><span class="hn">{{ dev.name }}</span><small v-if="dev.attrs?.modell && !details">{{ dev.attrs.modell }}</small></td>
              <td v-if="details" class="det">{{ dev.attrs?.modell }}</td><td v-if="details" class="det">{{ dev.attrs?.ip }}</td>
              <td class="pc">{{ Math.round(dev.percent) }}</td>
              <td v-for="s in steps" :key="s.position" class="c">
                <button v-if="cell(dev, s.position)" class="cell" :class="['s-' + cell(dev, s.position)!.status, { pool: cell(dev, s.position)!.pool && !cell(dev, s.position)!.resource_ids.length, sel: sel.has(cell(dev, s.position)!.id), miss: cell(dev, s.position)!.deadline_missed }]"
                        :title="tip(cell(dev, s.position)!)" @click="click(cell(dev, s.position)!, $event)" @dblclick="emit('open', cell(dev, s.position)!.id)">{{ ICON[cell(dev, s.position)!.status] }}<i v-if="cell(dev, s.position)!.deadline_missed">⚠</i></button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="!rows.length" class="dim pad">{{ $t('Keine Geräte für diese Auswahl.') }}</p>
      </div>
      <p class="legend dim">{{ $t('○ offen · ◐ in Arbeit · ✓ erledigt · ⛔ blockiert · ⚠ Frist überschritten · gestrichelter Rand = im Pool (noch niemandem zugeordnet)') }}</p>
    </template>

    <DeviceImport v-if="importing" :pid="pid" @close="importing = false" @done="emit('reload')" />

    <div v-if="adding" class="modal-back" @mousedown.self="adding = false">
      <form class="modal" @submit.prevent="addDevice">
        <h3>{{ $t('Gerät aus Vorlage anlegen') }}</h3>
        <label>{{ $t('Vorlage (Gerätetyp)') }} <select v-model.number="nd.template_id"><option v-for="t in templates" :key="t.id" :value="t.id">{{ $t('{1} ({2} Schritte)', { 1: t.name, 2: t.steps.length }) }}</option></select></label>
        <label>{{ $t('Hostname') }} <input v-model="nd.hostname" required maxlength="120" autofocus :placeholder="$t('z. B. sw-kas-z-04')" /></label>
        <label>{{ $t('Standort') }} <input v-model="nd.standort" maxlength="120" list="sitelist" :placeholder="$t('Phase, unter der das Gerät angelegt wird')" /><datalist id="sitelist"><option v-for="s in siteList" :key="s" :value="s" /></datalist></label>
        <label>{{ $t('Neues Modell') }} <input v-model="nd.modell" maxlength="200" /></label>
        <div class="two"><label>{{ $t('Wartungsfenster von') }} <input v-model="nd.von" type="date" /></label><label>{{ $t('bis') }} <input v-model="nd.bis" type="date" :min="nd.von || undefined" /></label></div>
        <label>{{ $t('Lieferzeit (Arbeitstage, leer = Vorlage)') }} <input v-model.number="nd.lieferzeit" type="number" min="0" max="365" /></label>
        <p class="dim">{{ $t('Schritte werden nach den Rollenzuordnung des Projekts zugeordnet, sonst liegen sie im Pool.') }}</p>
        <div class="actions"><button type="button" @click="adding = false">{{ $t('Abbrechen') }}</button><button class="primary" type="submit">{{ $t('Anlegen') }}</button></div>
      </form>
    </div>
  </div>
</template>

<style scoped>
.dm { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.bar { display: flex; gap: 8px; align-items: center; padding: 8px 14px; border-bottom: 1px solid var(--border); flex-wrap: wrap; } .spacer { flex: 1; } .q { min-width: 240px; }
.inl { display: inline-flex; gap: 6px; align-items: center; font-size: 13px; } .chk { display: inline-flex; gap: 4px; align-items: center; font-size: 13px; } input[type=checkbox] { width: auto; }
.empty { padding: 28px; max-width: 700px; } .dim { color: var(--fg-dim); font-size: 12px; } .pad { padding: 14px; }
.sbar { display: flex; gap: 6px; align-items: center; padding: 6px 14px; border-bottom: 1px solid var(--border); flex-wrap: wrap; font-size: 13px; background: var(--bg-head); }
.scroll { flex: 1; overflow: auto; min-height: 0; }
.mx { border-collapse: separate; border-spacing: 0; font-size: 13px; min-width: 100%; }
.mx th, .mx td { border-bottom: 1px solid var(--border); border-right: 1px solid var(--border); padding: 3px 6px; }
.mx thead th { position: sticky; top: 0; z-index: 3; background: var(--bg-head); text-align: left; font-weight: 600; vertical-align: bottom; }
.st { cursor: pointer; min-width: 96px; max-width: 130px; } .st span { display: block; font-size: 12px; line-height: 1.2; } .st small { color: var(--fg-dim); font-weight: 400; font-size: 10px; } .st:hover { background: var(--row-sel); }
.host { position: sticky; left: 0; z-index: 2; background: var(--bg); min-width: 150px; cursor: pointer; } thead .host { z-index: 4; background: var(--bg-head); }
.host small { display: block; color: var(--fg-dim); font-size: 11px; } .hn { font-weight: 600; } .det { color: var(--fg-dim); white-space: nowrap; } .pc { text-align: right; width: 38px; color: var(--fg-dim); }
.grp td { background: var(--bg-head); cursor: pointer; position: sticky; left: 0; } .grp td:hover { background: var(--row-sel); }
.c { text-align: center; padding: 2px; }
.cell { width: 36px; height: 26px; border-radius: 5px; border: 1px solid var(--border); background: var(--bg); cursor: pointer; font-size: 14px; line-height: 1; padding: 0; position: relative; color: var(--fg-dim); }
.cell i { position: absolute; top: -4px; right: -2px; font-size: 10px; font-style: normal; color: var(--bar-critical); }
.cell.s-in_progress { background: color-mix(in srgb, var(--bar) 25%, transparent); color: var(--bar); border-color: var(--bar); }
.cell.s-done { background: color-mix(in srgb, var(--ok) 30%, transparent); color: var(--ok); border-color: var(--ok); }
.cell.s-blocked { background: color-mix(in srgb, var(--blocked) 30%, transparent); border-color: var(--blocked); }
.cell.pool { border-style: dashed; }
.cell.miss { border-color: var(--bar-critical); } .cell.sel { outline: 2px solid var(--accent); outline-offset: 1px; }
.legend { padding: 4px 14px; margin: 0; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; } label { display: flex; flex-direction: column; gap: 3px; font-size: 13px; }
.actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 8px; }
</style>
