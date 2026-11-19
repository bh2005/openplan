<script setup lang="ts">
// Überlastungs-Vorschlag: Verschiebungen innerhalb des freien Puffers, die Überlast und Einsatz während Abwesenheit auflösen.
import { computed, onMounted, ref } from 'vue'
import { api, type LevelingProposal } from '../lib/api'
import { fmt } from '../lib/dates'
import { mutate, toast } from '../lib/store'
import { t as tr } from '../lib/i18n'

const props = defineProps<{ pid: number }>()
const emit = defineEmits<{ (e: 'close'): void }>()
const p = ref<LevelingProposal | null>(null)
const picked = ref<Set<number>>(new Set())
const busy = ref(false)

onMounted(async () => {
  try { p.value = await api.leveling(props.pid); picked.value = new Set(p.value.moves.map(m => m.task_id)) }
  catch (e) { toast((e as Error).message, 'error'); emit('close') }
})
const chosen = computed(() => p.value?.moves.filter(m => picked.value.has(m.task_id)) ?? [])
function toggle(id: number) { const s = new Set(picked.value); s.has(id) ? s.delete(id) : s.add(id); picked.value = s }
async function apply() {
  if (!chosen.value.length) return
  busy.value = true
  const ok = await mutate(() => api.applyLeveling(props.pid, chosen.value.map(m => ({ task_id: m.task_id, new_start: m.new_start }))))
  busy.value = false
  if (ok) { toast(tr('{1} Vorgänge verschoben – mit Strg+Z rückgängig', { 1: chosen.value.length })); emit('close') }
}
</script>

<template>
  <div class="modal-back" @mousedown.self="emit('close')">
    <div class="modal lv" role="dialog" :aria-label="$t('Überlastung auflösen')">
      <h3>{{ $t('Überlastung auflösen') }}</h3>
      <p v-if="!p" class="dim">{{ $t('Lade …') }}</p>
      <template v-else>
        <p class="dim">{{ $t('Vorgeschlagen werden nur Verschiebungen innerhalb des freien Puffers: Nachfolger und Projektende bleiben unverändert. Übernommen wird als „Beginn frühestens“. Begonnene, erledigte und manuell geplante Vorgänge werden nicht angefasst.') }}</p>
        <p v-if="!p.conflicts_before" class="ok">✓ {{ $t('Keine Überlastung und kein Einsatz während Abwesenheiten.') }}</p>
        <p v-else class="sum">
          {{ $t('{1} überlastete Ressourcen-Tage', { 1: p.conflicts_before }) }} →
          <b :class="p.conflicts_after ? 'bad' : 'ok'">{{ $t('{1} nach den Verschiebungen', { 1: p.conflicts_after }) }}</b>
        </p>
        <template v-if="p.moves.length">
          <h4>{{ $t('Vorgeschlagene Verschiebungen') }}</h4>
          <table class="mt">
            <thead><tr><th /><th>{{ $t('Vorgang') }}</th><th>{{ $t('Ressource') }}</th><th>{{ $t('Beginn') }}</th><th>{{ $t('Ende') }}</th><th class="n">{{ $t('Versatz') }}</th></tr></thead>
            <tbody>
              <tr v-for="m in p.moves" :key="m.task_id">
                <td><input type="checkbox" :checked="picked.has(m.task_id)" :aria-label="m.name" @change="toggle(m.task_id)" /></td>
                <td>{{ m.name }}</td><td>{{ m.resources.join(', ') }}</td>
                <td>{{ fmt(m.old_start) }} → <b>{{ fmt(m.new_start) }}</b></td><td>{{ fmt(m.old_finish) }} → <b>{{ fmt(m.new_finish) }}</b></td>
                <td class="n">+{{ m.shift }} {{ $t('T') }}</td>
              </tr>
            </tbody>
          </table>
        </template>
        <template v-if="p.unresolved.length">
          <h4>{{ $t('Nicht im Puffer lösbar – braucht eine Entscheidung') }}</h4>
          <ul class="un">
            <li v-for="(u, i) in p.unresolved" :key="i">
              <b>{{ fmt(u.date) }}</b> · {{ u.resource }}: {{ u.load }} % {{ $t('eingeplant bei') }} {{ u.capacity }} % {{ $t('verfügbar') }}
              <small class="dim">({{ u.tasks.map(t => t.name).join(', ') }})</small>
            </li>
          </ul>
          <p class="dim">{{ $t('Optionen: Vorgang einer anderen Person zuordnen, Termin bewusst verschieben (dann rücken Nachfolger nach) oder Kapazität anpassen.') }}</p>
        </template>
      </template>
      <div class="actions">
        <button type="button" @click="emit('close')">{{ $t('Schließen') }}</button>
        <button v-if="p?.moves.length" type="button" class="primary" :disabled="busy || !chosen.length" @click="apply">{{ $t('{1} Verschiebungen übernehmen', { 1: chosen.length }) }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.lv { width: min(860px, 96vw); }
.dim { color: var(--fg-dim); } .ok { color: var(--ok); } .bad { color: var(--bar-critical); } .sum { font-size: 14px; }
h4 { margin: 14px 0 6px; font-size: 13px; text-transform: uppercase; letter-spacing: .04em; color: var(--fg-dim); }
.mt { border-collapse: collapse; width: 100%; font-size: 13px; }
.mt th, .mt td { text-align: left; padding: 5px 8px; border-bottom: 1px solid var(--border); white-space: nowrap; } .mt td:nth-child(2) { white-space: normal; } .mt .n { text-align: right; }
.un { margin: 0; padding-left: 18px; font-size: 13px; } .un li { margin: 3px 0; }
</style>
