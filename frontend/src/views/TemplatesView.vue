<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { api, downloadDeviceSample } from '../lib/api'
import { canEdit, toast } from '../lib/store'
import type { Template } from '../lib/types'
import { t as tr } from '../lib/i18n'

interface EStep { uid: number; name: string; role: string; duration: number; wait_days: number; pred_uid: number | null; books_price: boolean; uses_window: boolean; takes_lead: boolean }
const list = ref<Template[]>([])
const sel = ref<number | 'new' | null>(null)
const f = reactive({ name: '', category: 'Netzwerk', description: '', steps: [] as EStep[] })
let uidc = 1
const busy = ref(false)

const roles = computed(() => [...new Set(list.value.flatMap(t => t.steps.map(s => s.role)).concat(f.steps.map(s => s.role)).filter(Boolean))].sort())
const groups = computed(() => {
  const m = new Map<string, Template[]>()
  for (const t of list.value) m.set(t.category || tr('Ohne Kategorie'), [...(m.get(t.category || tr('Ohne Kategorie')) ?? []), t])
  return [...m.entries()]
})

function load(t?: Template) {
  f.name = t?.name ?? ''; f.category = t?.category ?? 'Netzwerk'; f.description = t?.description ?? ''
  const uids = (t?.steps ?? []).map(() => uidc++)
  f.steps = (t?.steps ?? []).map((s, i) => ({ uid: uids[i], name: s.name, role: s.role, duration: s.duration, wait_days: s.wait_days, pred_uid: s.pred_pos ? uids[s.pred_pos - 1] ?? null : null,
    books_price: s.books_price, uses_window: s.uses_window, takes_lead: s.takes_lead }))
  if (!t) addStep()
}
async function refresh(keep?: number) {
  try { list.value = await api.templates() } catch (e) { toast((e as Error).message, 'error'); return }
  const t = list.value.find(x => x.id === (keep ?? (typeof sel.value === 'number' ? sel.value : -1))) ?? list.value[0]
  if (t) pick(t); else { sel.value = null }
}
function pick(t: Template) { sel.value = t.id; load(t) }
function newTpl() { sel.value = 'new'; load(undefined) }
function dup() { const t = list.value.find(x => x.id === sel.value); if (!t) return; sel.value = 'new'; load({ ...t, name: t.name + ' ' + tr('(Kopie)') }) }
onMounted(() => refresh())

function addStep() { f.steps.push({ uid: uidc++, name: '', role: '', duration: 1, wait_days: 0, pred_uid: f.steps.length ? f.steps[f.steps.length - 1].uid : null, books_price: false, uses_window: false, takes_lead: false }) }
function del(i: number) { const u = f.steps[i].uid; f.steps.splice(i, 1); for (const s of f.steps) if (s.pred_uid === u) s.pred_uid = null }
function move(i: number, d: -1 | 1) { const j = i + d; if (j < 0 || j >= f.steps.length) return; [f.steps[i], f.steps[j]] = [f.steps[j], f.steps[i]] }
const earlier = (i: number) => f.steps.slice(0, i)
const flagOnce = (key: 'books_price' | 'uses_window' | 'takes_lead', i: number) => { if (f.steps[i][key]) f.steps.forEach((s, k) => { if (k !== i) s[key] = false }) }

async function save() {
  const steps = f.steps.map((s, i) => {
    const pi = s.pred_uid == null ? -1 : f.steps.findIndex(x => x.uid === s.pred_uid)
    return { position: i + 1, name: s.name.trim(), role: s.role.trim(), duration: Math.max(0, Math.round(s.duration)), wait_days: Math.max(0, Math.round(s.wait_days)),
      pred_pos: pi >= 0 && pi < i ? pi + 1 : null, books_price: s.books_price, uses_window: s.uses_window, takes_lead: s.takes_lead }
  })
  if (steps.some(s => !s.name)) return toast(tr('Jeder Schritt braucht einen Namen'), 'error')
  busy.value = true
  try {
    const r = await api.saveTemplate({ name: f.name.trim(), category: f.category.trim(), description: f.description.trim(), steps }, typeof sel.value === 'number' ? sel.value : undefined)
    toast(tr('Vorlage gespeichert')); await refresh(r.id)
  } catch (e) { toast((e as Error).message, 'error') } finally { busy.value = false }
}
async function sample() { try { await downloadDeviceSample() } catch (e) { toast((e as Error).message, 'error') } }
async function remove() {
  if (typeof sel.value !== 'number' || !confirm(tr('Vorlage „{1}“ löschen? Bereits angelegte Vorgänge bleiben bestehen.', { 1: f.name }))) return
  try { await api.deleteTemplate(sel.value); toast(tr('Vorlage gelöscht')); sel.value = null; await refresh() } catch (e) { toast((e as Error).message, 'error') }
}
</script>

<template>
  <div class="tv">
    <aside class="side">
      <div class="sh"><h3>{{ $t('Vorlagen') }}</h3><button v-if="canEdit" class="primary sm" @click="newTpl">{{ $t('+ Neu') }}</button></div>
      <p v-if="!list.length" class="dim">{{ $t('Keine Vorlagen.') }}</p>
      <button class="sample" :title="$t('Excel-Muster für den Geräteliste-Import, passend zu den aktuellen Vorlagen')" @click="sample">{{ $t('⬇ Muster-Excel herunterladen') }}</button>
      <template v-for="[cat, ts] in groups" :key="cat">
        <div class="cat">{{ cat }}</div>
        <button v-for="t in ts" :key="t.id" class="item" :class="{ on: sel === t.id }" @click="pick(t)">{{ t.name }} <small>{{ $t('{1} Schritte', { 1: t.steps.length }) }}</small></button>
      </template>
    </aside>

    <section v-if="sel !== null" class="main">
      <p class="dim">{{ $t('Eine Vorlage beschreibt die Arbeitsschritte eines Gerätetyps.') }} <b>{{ $t('Der Name ist der Wert der Spalte „Gerätetyp“') }}</b> {{ $t('in der Geräteliste. Beim Import entsteht pro Gerät ein Vorgang mit diesen Schritten, verkettet nach „Vorgänger“.') }}</p>
      <fieldset :disabled="!canEdit" class="plain">
        <div class="row">
          <label class="grow">{{ $t('Name (= Gerätetyp)') }} <input v-model="f.name" maxlength="80" /></label>
          <label>{{ $t('Kategorie') }} <input v-model="f.category" maxlength="60" list="cats" /><datalist id="cats"><option v-for="[c] in groups" :key="c" :value="c" /></datalist></label>
        </div>
        <label>{{ $t('Beschreibung') }} <input v-model="f.description" maxlength="500" /></label>

        <table class="steps">
          <thead><tr><th>{{ $t('Nr') }}</th><th>{{ $t('Schritt') }}</th><th>{{ $t('Rolle') }}</th><th :title="$t('Arbeitstage')">{{ $t('Dauer') }}</th><th :title="$t('Wartezeit (Arbeitstage) bis der nächste Schritt starten darf, z. B. Lieferzeit')">{{ $t('Wartezeit danach') }}</th><th>{{ $t('Vorgänger') }}</th>
            <th :title="$t('Der Preis der Geräteliste wird als Plankosten an diesem Schritt gebucht')">{{ $t('Preis') }}</th><th :title="$t('Das Wartungsfenster der Geräteliste wird zum Erledigungszeitraum dieses Schritts')">{{ $t('Fenster') }}</th><th :title="$t('Die Spalte „Lieferzeit (Tage)“ überschreibt die Wartezeit dieses Schritts')">{{ $t('Lieferzeit') }}</th><th /></tr></thead>
          <tbody>
            <tr v-for="(s, i) in f.steps" :key="s.uid">
              <td class="n">{{ i + 1 }}</td>
              <td><input v-model="s.name" maxlength="200" :placeholder="$t('Schrittname')" /></td>
              <td><input v-model="s.role" maxlength="60" list="roles" :placeholder="$t('z. B. Einkauf')" /></td>
              <td><input v-model.number="s.duration" type="number" min="0" class="num" /></td>
              <td><input v-model.number="s.wait_days" type="number" min="0" class="num" /></td>
              <td><select v-model="s.pred_uid"><option :value="null">–</option><option v-for="(p, k) in earlier(i)" :key="p.uid" :value="p.uid">{{ k + 1 }} {{ p.name.slice(0, 22) }}</option></select></td>
              <td class="c"><input type="checkbox" v-model="s.books_price" @change="flagOnce('books_price', i)" /></td>
              <td class="c"><input type="checkbox" v-model="s.uses_window" @change="flagOnce('uses_window', i)" /></td>
              <td class="c"><input type="checkbox" v-model="s.takes_lead" @change="flagOnce('takes_lead', i)" /></td>
              <td class="act"><button type="button" :title="$t('nach oben')" @click="move(i, -1)">↑</button><button type="button" :title="$t('nach unten')" @click="move(i, 1)">↓</button><button type="button" class="danger" :title="$t('Schritt entfernen')" @click="del(i)">×</button></td>
            </tr>
          </tbody>
        </table>
        <datalist id="roles"><option v-for="r in roles" :key="r" :value="r" /></datalist>
        <div class="bar"><button type="button" @click="addStep">{{ $t('+ Schritt') }}</button></div>
      </fieldset>
      <div class="bar" v-if="canEdit">
        <button class="primary" :disabled="busy || !f.name.trim()" @click="save">{{ $t('Speichern') }}</button>
        <button v-if="typeof sel === 'number'" @click="dup">{{ $t('Duplizieren') }}</button>
        <button v-if="typeof sel === 'number'" class="danger" @click="remove">{{ $t('Löschen') }}</button>
      </div>
      <p v-else class="dim">{{ $t('Du hast Leserechte – Vorlagen können nur Bearbeiter ändern.') }}</p>
    </section>
    <section v-else class="main"><p class="dim">{{ $t('Wähle links eine Vorlage oder lege eine neue an.') }}</p></section>
  </div>
</template>

<style scoped>
.tv { display: flex; gap: 18px; padding: 16px 20px; height: 100%; min-height: 0; overflow: auto; align-items: flex-start; }
.sample { margin-top: .6rem; font-size: .85rem; }
.side { flex: none; width: 230px; display: flex; flex-direction: column; gap: 3px; }
.sh { display: flex; justify-content: space-between; align-items: center; } .sh h3 { margin: 0; }
.sm { padding: 2px 10px; font-size: 12px; }
.cat { font-size: 11px; text-transform: uppercase; letter-spacing: .04em; color: var(--fg-dim); margin: 10px 0 2px; }
.item { text-align: left; background: none; border: 1px solid transparent; border-radius: 6px; padding: 6px 10px; cursor: pointer; color: inherit; display: flex; justify-content: space-between; gap: 6px; }
.item:hover { background: var(--row-sel); } .item.on { border-color: var(--accent); background: var(--row-sel); font-weight: 600; } .item small { color: var(--fg-dim); font-weight: 400; }
.main { flex: 1; min-width: 0; max-width: 1050px; }
.dim { color: var(--fg-dim); font-size: 12px; margin: 0 0 10px; }
.plain { border: 0; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 10px; min-width: 0; }
label { display: flex; flex-direction: column; gap: 3px; font-size: 13px; } .row { display: flex; gap: 12px; flex-wrap: wrap; } .grow { flex: 1; min-width: 220px; }
.steps { border-collapse: collapse; width: 100%; font-size: 13px; } .steps th, .steps td { padding: 4px 5px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: middle; }
.steps th { font-size: 11px; color: var(--fg-dim); font-weight: 600; } .steps input:not([type=checkbox]), .steps select { width: 100%; } .num { width: 64px !important; }
.n { color: var(--fg-dim); text-align: right !important; width: 26px; } .c { text-align: center !important; } input[type=checkbox] { width: auto; }
.act { white-space: nowrap; } .act button { padding: 1px 7px; margin-left: 2px; }
.bar { display: flex; gap: 8px; margin-top: 4px; flex-wrap: wrap; }
@media (max-width: 800px) { .tv { flex-direction: column; } .side { width: 100%; } }
@media (max-width: 700px) {
  .tv { padding: 12px; gap: 12px; width: 100%; }
  .main { width: 100%; }
  .grow { min-width: 0; flex: 1 1 100%; }
  .steps { display: block; overflow-x: auto; white-space: nowrap; }
  .steps input:not([type=checkbox]), .steps select { min-width: 110px; }
  .steps .num { min-width: 64px; }
}
</style>
