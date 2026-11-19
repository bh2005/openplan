<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { api } from '../lib/api'
import { eur0, fin, finMutate, label, parseNum } from '../lib/finance'
import { toast } from '../lib/store'
import type { Master } from '../lib/types'
import { t as tr } from '../lib/i18n'

const props = defineProps<{ pid: number; canEdit: boolean }>()
const kinds = [
  { kind: 'cost-centers', title: 'Kostenstellen', key: 'cost_centers' as const, hint: 'z. B. 100200 – IT Betrieb' },
  { kind: 'cost-types', title: 'Kostenarten', key: 'cost_types' as const, hint: 'z. B. 400000 – Fremdleistungen' },
]
const nw = reactive<Record<string, { code: string; name: string }>>({ 'cost-centers': { code: '', name: '' }, 'cost-types': { code: '', name: '' } })
const edit = ref<{ kind: string; id: number; code: string; name: string } | null>(null)
const bulk = reactive<Record<string, { open: boolean; text: string }>>({ 'cost-centers': { open: false, text: '' }, 'cost-types': { open: false, text: '' } })

async function add(kind: string) {
  const v = nw[kind]
  if (!v.code.trim()) return
  if (await finMutate(props.pid, () => api.masterAdd(props.pid, kind, { code: v.code.trim(), name: v.name.trim() }))) { v.code = ''; v.name = '' }
}
async function saveEdit() {
  const e = edit.value
  if (!e || !e.code.trim()) return
  edit.value = null
  await finMutate(props.pid, () => api.masterUpdate(e.kind, e.id, { code: e.code.trim(), name: e.name.trim() }))
}
async function del(kind: string, m: Master) {
  if (confirm(tr('„{1} {2}" löschen?', { 1: m.code, 2: m.name }))) await finMutate(props.pid, () => api.masterDelete(kind, m.id))
}
async function importBulk(kind: string) {
  if (await finMutate(props.pid, () => api.masterImport(props.pid, kind, bulk[kind].text))) { bulk[kind].open = false; bulk[kind].text = ''; toast(tr('Importiert')) }
}

// ── Budgetzeilen ────────────────────────────────────────────────────────
type Line = { cc: number; ct: number; amount: string }
const lines = ref<Line[]>([])
const toText = (v: number) => v.toFixed(2).replace('.', ',')
function reset() {
  lines.value = fin.data!.budget_lines.map(l => ({ cc: l.cost_center_id ?? 0, ct: l.cost_type_id ?? 0, amount: toText(l.amount) }))
}
reset()
watch(() => fin.data?.budget_lines, reset)
const total = computed(() => lines.value.find(l => !l.cc && !l.ct))
async function saveLines() {
  const out: { cost_center_id: number | null; cost_type_id: number | null; amount: number }[] = []
  for (const l of lines.value) {
    const a = parseNum(l.amount)
    if (!Number.isFinite(a) || a < 0) return toast(tr('Budgetbetrag ungültig'), 'error')
    out.push({ cost_center_id: l.cc || null, cost_type_id: l.ct || null, amount: a })
  }
  if (await finMutate(props.pid, () => api.setBudgetLines(props.pid, out))) toast(tr('Budget gespeichert'))
}
const dirty = computed(() => JSON.stringify(lines.value) !== JSON.stringify(fin.data!.budget_lines.map(l => ({ cc: l.cost_center_id ?? 0, ct: l.cost_type_id ?? 0, amount: toText(l.amount) }))))

async function toggleSee(e: Event) { await finMutate(props.pid, () => api.setCostSettings(props.pid, (e.target as HTMLInputElement).checked)) }
</script>

<template>
  <div class="bm">
    <section>
      <h3>{{ $t('Budget') }}</h3>
      <p class="hint">{{ $t('Eine Zeile ohne Kostenstelle/Kostenart ist das') }} <b>{{ $t('Gesamtbudget') }}</b>{{ $t('. Zeilen mit Kostenstelle und/oder Kostenart sind Teilbudgets (nur EUR).') }}</p>
      <table class="dt">
        <thead><tr><th>{{ $t('Kostenstelle') }}</th><th>{{ $t('Kostenart') }}</th><th class="n">{{ $t('Budget (EUR)') }}</th><th /></tr></thead>
        <tbody>
          <tr v-for="(l, i) in lines" :key="i">
            <td><select v-model.number="l.cc" :disabled="!canEdit"><option :value="0">{{ $t('alle / Gesamt') }}</option><option v-for="c in fin.data!.cost_centers" :key="c.id" :value="c.id">{{ label(fin.data!.cost_centers, c.id) }}</option></select></td>
            <td><select v-model.number="l.ct" :disabled="!canEdit"><option :value="0">{{ $t('alle / Gesamt') }}</option><option v-for="c in fin.data!.cost_types" :key="c.id" :value="c.id">{{ label(fin.data!.cost_types, c.id) }}</option></select></td>
            <td class="n"><input v-model="l.amount" class="amt" :disabled="!canEdit" /></td>
            <td class="n"><button v-if="canEdit" class="danger" @click="lines.splice(i, 1)">×</button></td>
          </tr>
          <tr v-if="!lines.length"><td colspan="4" class="dim">{{ $t('Noch kein Budget hinterlegt.') }}</td></tr>
        </tbody>
      </table>
      <div v-if="canEdit" class="row">
        <button @click="lines.push({ cc: 0, ct: 0, amount: '0,00' })">{{ $t('+ Zeile') }}</button>
        <button class="primary" :disabled="!dirty" @click="saveLines">{{ $t('Budget speichern') }}</button>
        <span v-if="total" class="dim">{{ $t('Gesamtbudget: {1}', { 1: eur0(parseNum(total.amount)) }) }}</span>
      </div>
    </section>

    <div class="two">
      <section v-for="k in kinds" :key="k.kind">
        <h3>{{ $t(k.title) }}</h3>
        <table class="dt">
          <thead><tr><th>{{ $t('Nummer') }}</th><th>{{ $t('Bezeichnung') }}</th><th /></tr></thead>
          <tbody>
            <tr v-for="m in fin.data![k.key]" :key="m.id">
              <template v-if="edit && edit.kind === k.kind && edit.id === m.id">
                <td><input v-model="edit.code" @keydown.enter="saveEdit" /></td><td><input v-model="edit.name" @keydown.enter="saveEdit" /></td>
                <td class="n"><button class="primary" @click="saveEdit">{{ $t('OK') }}</button> <button @click="edit = null">×</button></td>
              </template>
              <template v-else>
                <td>{{ m.code }}</td><td>{{ m.name }}</td>
                <td class="n"><template v-if="canEdit"><button @click="edit = { kind: k.kind, ...m }">✎</button> <button class="danger" @click="del(k.kind, m)">×</button></template></td>
              </template>
            </tr>
            <tr v-if="canEdit" class="new">
              <td><input v-model="nw[k.kind].code" :placeholder="$t('Nummer')" @keydown.enter="add(k.kind)" /></td>
              <td><input v-model="nw[k.kind].name" :placeholder="$t(k.hint)" @keydown.enter="add(k.kind)" /></td>
              <td class="n"><button class="primary" @click="add(k.kind)">+</button></td>
            </tr>
          </tbody>
        </table>
        <template v-if="canEdit">
          <button class="link" @click="bulk[k.kind].open = !bulk[k.kind].open">{{ $t('Liste einfügen / aus SAP importieren') }}</button>
          <div v-if="bulk[k.kind].open" class="bulk">
            <textarea v-model="bulk[k.kind].text" rows="5" :placeholder="$t('Eine Zeile je Eintrag: Nummer;Bezeichnung (auch aus Excel kopiert). Vorhandene Nummern werden aktualisiert.')" />
            <button class="primary" :disabled="!bulk[k.kind].text.trim()" @click="importBulk(k.kind)">{{ $t('Importieren') }}</button>
          </div>
        </template>
      </section>
    </div>

    <section v-if="canEdit">
      <h3>{{ $t('Sichtbarkeit') }}</h3>
      <label class="chk"><input type="checkbox" :checked="fin.data!.members_see_costs" @change="toggleSee" />
        {{ $t('Projektmitglieder dürfen Kosten und Budget') }} <b>{{ $t('sehen') }}</b> {{ $t('(ändern darf sie weiterhin nur der Verantwortliche)') }}</label>
    </section>
  </div>
</template>

<style scoped>
.bm { padding: 14px 18px 40px; max-width: 1200px; }
section { margin-bottom: 24px; }
h3 { margin: 0 0 8px; font-size: 15px; }
.hint, .dim { color: var(--fg-dim); font-size: 12px; margin: 0 0 8px; }
.two { display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 22px; }
.dt { border-collapse: collapse; width: 100%; font-size: 13px; }
.dt th, .dt td { text-align: left; padding: 4px 8px; border-bottom: 1px solid var(--border); }
.dt .n { text-align: right; white-space: nowrap; }
.dt input, .dt select { width: 100%; } .dt input.amt { width: 140px; text-align: right; }
.row { display: flex; gap: 8px; align-items: center; margin-top: 8px; }
.link { background: none; border: 0; color: var(--accent); padding: 6px 0; text-decoration: underline; }
.bulk { display: flex; flex-direction: column; gap: 6px; align-items: flex-start; } .bulk textarea { width: 100%; }
.chk { display: flex; gap: 8px; align-items: center; }
</style>
