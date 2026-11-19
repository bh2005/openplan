<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api } from '../lib/api'
import { toast } from '../lib/store'
import { t as tr } from '../lib/i18n'

const f = reactive({ enabled: true, hour: 7, due_days: 2, escalate_days: 3, blocked_days: 3 })
const state = ref<{ date?: string; result?: Record<string, number> }>({})
const res = ref<Record<string, number> | null>(null)
const busy = ref(false)

function fill(s: typeof f & { state: typeof state.value }) { const { state: st, ...rest } = s; Object.assign(f, rest); state.value = st }
onMounted(async () => { try { fill(await api.reminderSettings()) } catch (e) { toast((e as Error).message, 'error') } })
async function save() { try { fill(await api.saveReminderSettings({ ...f })); toast(tr('Gespeichert')) } catch (e) { toast((e as Error).message, 'error') } }
async function run() {
  busy.value = true; res.value = null
  try { res.value = await api.runReminders() } catch (e) { toast((e as Error).message, 'error') } finally { busy.value = false }
}
</script>

<template>
  <form class="rem" @submit.prevent="save">
    <p class="dim">{{ $t('OpenPlan prüft täglich alle offenen Vorgänge und meldet automatisch per Glocke und E-Mail (jeweils nur einmal je Vorgang und Termin):') }}</p>
    <ul class="dim">
      <li><b>{{ $t('Fällig:') }}</b> {{ $t('der Bearbeiter, wenn das Ende in den nächsten Tagen liegt (bei Pool-Paketen ohne Bearbeiter der Verantwortliche).') }}</li>
      <li><b>{{ $t('Überfällig:') }}</b> {{ $t('der Bearbeiter; nach einigen Tagen zusätzlich als') }} <b>{{ $t('Eskalation') }}</b> {{ $t('der Projekt-Verantwortliche.') }}</li>
      <li><b>{{ $t('Blockiert:') }}</b> {{ $t('Verantwortlicher und Bearbeiter, wenn ein Vorgang zu lange blockiert ist.') }}</li>
    </ul>
    <label class="chk"><input type="checkbox" v-model="f.enabled" /> <b>{{ $t('Automatische Erinnerungen aktiv') }}</b></label>
    <div class="grid">
      <label>{{ $t('Prüfung täglich ab') }} <span><input v-model.number="f.hour" type="number" min="0" max="23" class="num" /> {{ $t('Uhr') }}</span></label>
      <label>{{ $t('„Fällig“ melden') }} <span><input v-model.number="f.due_days" type="number" min="0" max="14" class="num" /> {{ $t('Tage vorher') }}</span></label>
      <label>{{ $t('Eskalation nach') }} <span><input v-model.number="f.escalate_days" type="number" min="1" max="60" class="num" /> {{ $t('Tagen überfällig') }}</span></label>
      <label>{{ $t('Blockiert melden nach') }} <span><input v-model.number="f.blocked_days" type="number" min="1" max="60" class="num" /> {{ $t('Tagen') }}</span></label>
    </div>
    <div class="actions"><button class="primary">{{ $t('Speichern') }}</button><button type="button" :disabled="busy" @click="run">{{ $t('Jetzt prüfen') }}</button>
      <span v-if="state.date" class="dim">{{ $t('Letzter automatischer Lauf: {1}', { 1: state.date }) }}</span></div>
    <p v-if="res" class="okmsg">{{ $t('Neue Meldungen: {1} fällig, {2} überfällig, {3} Eskalationen, {4} blockiert.', { 1: res.due, 2: res.overdue, 3: res.escalation, 4: res.blocked }) }}</p>
  </form>
</template>

<style scoped>
.rem { display: flex; flex-direction: column; gap: 10px; } .dim { color: var(--fg-dim); font-size: 12px; margin: 0; } ul.dim { padding-left: 18px; }
label.chk { display: flex; align-items: center; gap: 6px; font-size: 13px; } input[type=checkbox] { width: auto; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 10px; } .grid label { display: flex; flex-direction: column; gap: 3px; font-size: 13px; } .num { width: 70px; }
.actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; } .okmsg { color: var(--ok); font-size: 13px; margin: 0; }
</style>
