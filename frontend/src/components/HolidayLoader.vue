<script setup lang="ts">
// Bundesland wählen und gesetzliche Feiertage (api-feiertage.de, über das Backend) in die Feiertagsliste übernehmen.
import { onMounted, ref } from 'vue'
import { api } from '../lib/api'
import { parseDate } from '../lib/dates'
import { toast } from '../lib/store'
import { t as tr } from '../lib/i18n'

const props = defineProps<{ state: string; text: string; start: string }>()
const emit = defineEmits<{ 'update:state': [v: string]; 'update:text': [v: string] }>()
const states = ref<{ code: string; name: string }[]>([])
const busy = ref(false)

onMounted(async () => { try { states.value = await api.holidayStates() } catch { /* Auswahl bleibt leer */ } })

const show = (d: string) => d.split('-').reverse().join('.')

async function load() {
  if (!props.state) return toast(tr('Bitte zuerst ein Bundesland wählen.'), 'error')
  const y0 = Number((parseDate(props.start) ?? new Date().toISOString()).slice(0, 4))
  busy.value = true
  try {
    const r = await api.holidays(props.state, [y0, y0 + 1, y0 + 2])
    const have = new Set(props.text.split(/[\n;,]/).map(s => parseDate(s)).filter((d): d is string => !!d))
    const add = r.holidays.map(h => h.date).filter(d => !have.has(d))
    const all = [...have, ...add].sort()
    emit('update:text', all.map(show).join('\n'))
    let msg = tr('{1} Feiertage ergänzt', { 1: add.length })
    if (r.missing_years.length) msg += ' · ' + tr('keine Daten für {1}', { 1: r.missing_years.join(', ') })
    toast(msg, r.missing_years.length ? 'error' : undefined)
  } catch (e) { toast((e as Error).message, 'error') } finally { busy.value = false }
}
</script>

<template>
  <div class="hl">
    <select :value="state" :aria-label="$t('Bundesland')" @change="emit('update:state', ($event.target as HTMLSelectElement).value)">
      <option value="">{{ $t('Bundesland wählen …') }}</option>
      <option v-for="s in states" :key="s.code" :value="s.code">{{ s.name }}</option>
    </select>
    <button type="button" :disabled="busy || !state" @click="load">{{ busy ? $t('Lade …') : $t('Feiertage laden') }}</button>
    <small class="dim">{{ $t('Ergänzt die gesetzlichen Feiertage für Projektjahr und die zwei Folgejahre; eigene Einträge bleiben erhalten.') }}</small>
  </div>
</template>

<style scoped>
.hl { display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; margin: .3rem 0 }
.hl small { flex-basis: 100% }
</style>
