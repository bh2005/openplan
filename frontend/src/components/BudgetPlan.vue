<script setup lang="ts">
import { computed, reactive } from 'vue'
import { api } from '../lib/api'
import { eur, eur0, finMutate, fin, label, parseNum } from '../lib/finance'
import { state, toast } from '../lib/store'
import { t as tr } from '../lib/i18n'

const props = defineProps<{ pid: number; canEdit: boolean }>()
const tasks = computed(() => state.data?.tasks ?? [])
const leaves = computed(() => tasks.value.filter(t => !t.summary))
const items = computed(() => fin.data!.cost_items)
const tname = (id: number) => { const t = tasks.value.find(x => x.id === id); return t ? `${t.wbs} ${t.name}` : '#' + id }

const nw = reactive({ task: 0, cc: 0, ct: 0, amount: '', desc: '' })
async function add() {
  const a = parseNum(nw.amount)
  if (!nw.task || !Number.isFinite(a)) return toast(tr('Vorgang und gültigen Betrag angeben'), 'error')
  if (await finMutate(props.pid, () => api.itemAdd(nw.task, { amount: a, cost_center_id: nw.cc || null, cost_type_id: nw.ct || null, description: nw.desc }))) {
    nw.amount = ''; nw.desc = ''
  }
}
async function patch(i: (typeof items.value)[number], field: string, v: string) {
  const body: Record<string, unknown> = { amount: i.amount, cost_center_id: i.cost_center_id, cost_type_id: i.cost_type_id, description: i.description }
  if (field === 'amount') { const a = parseNum(v); if (!Number.isFinite(a)) return toast(tr('Betrag ungültig'), 'error'); body.amount = a }
  else if (field === 'description') body.description = v
  else body[field] = v ? Number(v) : null
  await finMutate(props.pid, () => api.itemUpdate(i.id, body))
}
async function del(id: number) { if (confirm(tr('Planposten löschen?'))) await finMutate(props.pid, () => api.itemDelete(id)) }

const perTask = computed(() => leaves.value.map(t => {
  const v = fin.budget!.per_task[String(t.id)] ?? { plan: 0 }
  const fixed = items.value.filter(i => i.task_id === t.id).reduce((a, i) => a + i.amount, 0)
  return { t, labor: v.plan - fixed, fixed, total: v.plan, assigned: t.resource_ids.length }
}).filter(r => r.total || r.assigned))
const noRate = computed(() => (state.data?.resources ?? []).filter(r => !r.cost_rate).map(r => r.name))
</script>

<template>
  <div class="pl">
    <p class="hint">{{ $t('Plankosten =') }} <b>{{ $t('Personalkosten') }}</b> {{ $t('(Dauer × Tagessatz × Zuordnung, aus den Ressourcen) +') }} <b>{{ $t('feste Kosten') }}</b> {{ $t('(Material, Lizenzen, Fremdleistungen …). Tagessätze, Kostenstelle und Kostenart einer Ressource pflegst du im Tab „Ressourcen".') }}</p>
    <p v-if="noRate.length" class="warn">{{ $t('Ressourcen ohne Tagessatz (ergeben 0 € Personalkosten): {1}', { 1: noRate.join(', ') }) }}</p>

    <h3>{{ $t('Feste Kosten je Vorgang') }}</h3>
    <table class="dt">
      <thead><tr><th>{{ $t('Vorgang') }}</th><th>{{ $t('Beschreibung') }}</th><th>{{ $t('Kostenstelle') }}</th><th>{{ $t('Kostenart') }}</th><th class="n">{{ $t('Betrag (EUR)') }}</th><th /></tr></thead>
      <tbody>
        <tr v-for="i in items" :key="i.id">
          <td>{{ tname(i.task_id) }}</td>
          <td><input :value="i.description" :disabled="!canEdit" @change="patch(i, 'description', ($event.target as HTMLInputElement).value)" /></td>
          <td><select :value="i.cost_center_id ?? ''" :disabled="!canEdit" @change="patch(i, 'cost_center_id', ($event.target as HTMLSelectElement).value)">
            <option value="">–</option><option v-for="c in fin.data!.cost_centers" :key="c.id" :value="c.id">{{ label(fin.data!.cost_centers, c.id) }}</option></select></td>
          <td><select :value="i.cost_type_id ?? ''" :disabled="!canEdit" @change="patch(i, 'cost_type_id', ($event.target as HTMLSelectElement).value)">
            <option value="">–</option><option v-for="c in fin.data!.cost_types" :key="c.id" :value="c.id">{{ label(fin.data!.cost_types, c.id) }}</option></select></td>
          <td class="n"><input class="amt" :value="i.amount.toFixed(2).replace('.', ',')" :disabled="!canEdit" @change="patch(i, 'amount', ($event.target as HTMLInputElement).value)" /></td>
          <td class="n"><button v-if="canEdit" class="danger" @click="del(i.id)">×</button></td>
        </tr>
        <tr v-if="canEdit" class="new">
          <td><select v-model.number="nw.task"><option :value="0">{{ $t('Vorgang wählen …') }}</option>
            <option v-for="t in leaves" :key="t.id" :value="t.id">{{ t.wbs }} {{ t.name }}</option></select></td>
          <td><input v-model="nw.desc" :placeholder="$t('z. B. Lizenzen')" @keydown.enter="add" /></td>
          <td><select v-model.number="nw.cc"><option :value="0">–</option><option v-for="c in fin.data!.cost_centers" :key="c.id" :value="c.id">{{ label(fin.data!.cost_centers, c.id) }}</option></select></td>
          <td><select v-model.number="nw.ct"><option :value="0">–</option><option v-for="c in fin.data!.cost_types" :key="c.id" :value="c.id">{{ label(fin.data!.cost_types, c.id) }}</option></select></td>
          <td class="n"><input v-model="nw.amount" class="amt" placeholder="0,00" @keydown.enter="add" /></td>
          <td class="n"><button class="primary" @click="add">+</button></td>
        </tr>
        <tr v-if="!items.length && !canEdit"><td colspan="6" class="dim">{{ $t('Keine festen Kosten erfasst.') }}</td></tr>
      </tbody>
    </table>

    <h3>{{ $t('Plankosten je Vorgang') }}</h3>
    <table class="dt">
      <thead><tr><th>{{ $t('PSP') }}</th><th>{{ $t('Vorgang') }}</th><th class="n">{{ $t('Personal') }}</th><th class="n">{{ $t('Feste Kosten') }}</th><th class="n">{{ $t('Summe') }}</th></tr></thead>
      <tbody>
        <tr v-for="r in perTask" :key="r.t.id">
          <td>{{ r.t.wbs }}</td><td>{{ r.t.name }}</td><td class="n">{{ eur(r.labor) }}</td><td class="n">{{ eur(r.fixed) }}</td><td class="n"><b>{{ eur(r.total) }}</b></td>
        </tr>
        <tr v-if="!perTask.length"><td colspan="5" class="dim">{{ $t('Noch keine Plankosten.') }}</td></tr>
        <tr v-else class="tot"><td colspan="4">{{ $t('Gesamt (aktueller Plan)') }}</td><td class="n"><b>{{ eur0(fin.budget!.summary.plan) }}</b></td></tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.pl { padding: 14px 18px 40px; max-width: 1200px; }
.hint { color: var(--fg-dim); margin: 0 0 8px; }
.warn { background: color-mix(in srgb, #d29922 18%, transparent); border: 1px solid #d29922; border-radius: 6px; padding: 5px 10px; }
h3 { margin: 18px 0 8px; font-size: 15px; }
.dim { color: var(--fg-dim); }
.dt { border-collapse: collapse; width: 100%; font-size: 13px; }
.dt th, .dt td { text-align: left; padding: 4px 8px; border-bottom: 1px solid var(--border); }
.dt .n { text-align: right; white-space: nowrap; }
.dt input, .dt select { width: 100%; }
.dt input.amt { width: 120px; text-align: right; }
.tot td { border-top: 2px solid var(--border); }
</style>
