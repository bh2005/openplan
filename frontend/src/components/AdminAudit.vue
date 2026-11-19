<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { api } from '../lib/api'
import { toast } from '../lib/store'
import { locale } from '../lib/i18n'

const items = ref<{ id: number; ts: string; username: string; action: string; detail: string; ip: string }[]>([])
const actions = ref<string[]>([])
const total = ref(0)
const q = ref('')
const action = ref('')
const page = ref(0)
const SIZE = 50
let timer: number | undefined

async function load() {
  try { const r = await api.audit(q.value, action.value, SIZE, page.value * SIZE); items.value = r.items; total.value = r.total; actions.value = r.actions } catch (e) { toast((e as Error).message, 'error') }
}
onMounted(load)
watch([action], () => { page.value = 0; load() })
watch(q, () => { window.clearTimeout(timer); timer = window.setTimeout(() => { page.value = 0; load() }, 300) })
async function exportCsv() {
  try {
    const blob = await api.auditCsv(q.value, action.value)
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'openplan-audit.csv'; a.click(); URL.revokeObjectURL(a.href)
  } catch (e) { toast((e as Error).message, 'error') }
}
const when = (s: string) => { const d = new Date(s.replace(' ', 'T') + 'Z'); return isNaN(+d) ? s : d.toLocaleString(locale()) }
const bad = (a: string) => a.includes('fail')
const pages = () => Math.max(1, Math.ceil(total.value / SIZE))
</script>

<template>
  <div class="aud">
    <p class="dim">{{ $t('Protokoll sicherheitsrelevanter Aktionen: Anmeldungen (auch fehlgeschlagene, mit IP), Benutzer- und Rechteänderungen, Einstellungen, Datensicherung, Löschen von Projekten. Einträge werden 365 Tage aufbewahrt.') }}</p>
    <div class="bar">
      <input v-model="q" :placeholder="$t('Suchen (Benutzer, Details, IP) …')" class="grow" />
      <select v-model="action"><option value="">{{ $t('alle Aktionen') }}</option><option v-for="a in actions" :key="a" :value="a">{{ a }}</option></select>
      <button @click="load">{{ $t('Aktualisieren') }}</button><button @click="exportCsv">{{ $t('CSV-Export') }}</button>
    </div>
    <table class="tbl">
      <thead><tr><th>{{ $t('Zeit') }}</th><th>{{ $t('Benutzer') }}</th><th>{{ $t('Aktion') }}</th><th>{{ $t('Details') }}</th><th>{{ $t('IP') }}</th></tr></thead>
      <tbody>
        <tr v-for="i in items" :key="i.id" :class="{ bad: bad(i.action) }"><td class="nw">{{ when(i.ts) }}</td><td>{{ i.username }}</td><td class="nw"><code>{{ i.action }}</code></td><td>{{ i.detail }}</td><td class="nw">{{ i.ip }}</td></tr>
        <tr v-if="!items.length"><td colspan="5" class="dim">{{ $t('Keine Einträge.') }}</td></tr>
      </tbody>
    </table>
    <div class="pg"><button :disabled="page === 0" @click="page--; load()">‹</button> {{ $t('Seite {1} / {2} ({3} Einträge)', { 1: page + 1, 2: pages(), 3: total }) }} <button :disabled="page + 1 >= pages()" @click="page++; load()">›</button></div>
  </div>
</template>

<style scoped>
.aud { display: flex; flex-direction: column; gap: 10px; } .dim { color: var(--fg-dim); font-size: 12px; margin: 0; }
.bar { display: flex; gap: 8px; flex-wrap: wrap; } .grow { flex: 1; min-width: 200px; }
.tbl { border-collapse: collapse; width: 100%; font-size: 12px; } .tbl th, .tbl td { text-align: left; padding: 4px 8px; border-bottom: 1px solid var(--border); vertical-align: top; }
.nw { white-space: nowrap; } tr.bad td { color: var(--bar-critical); } code { font-size: 11px; }
.pg { display: flex; gap: 10px; align-items: center; font-size: 12px; color: var(--fg-dim); }
</style>
