<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { api, downloadDeviceSample } from '../lib/api'
import { state, toast } from '../lib/store'
import type { DeviceParse, DeviceReport } from '../lib/types'
import { lang, t as tr } from '../lib/i18n'
import { translateApi } from '../locales/en.api'

const tm = (m: string) => (lang.value === 'en' ? translateApi(m) : m)       // Server-Meldungen im Bericht in der Benutzersprache

const props = defineProps<{ pid: number }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'done', r: DeviceReport): void }>()
const d = computed(() => state.data!)

const file = ref<File | null>(null)
const parsed = ref<DeviceParse | null>(null)
const mapping = reactive<Record<string, number | ''>>({})
const roles = ref<string[]>([])
const roleMap = reactive<Record<string, number | 0>>({})
const o = reactive({ parent_id: 0, create_missing: false, partial: false })
const report = ref<DeviceReport | null>(null)
const busy = ref(false)
const step = computed(() => (report.value && !report.value.dry_run && report.value.imported > 0 ? 3 : parsed.value ? 2 : 1))
const dragover = ref(false)

onMounted(async () => {
  try { const r = await api.roleMap(props.pid); roles.value = r.roles; Object.assign(roleMap, r.map) } catch { /* ohne Rollen */ }
})
async function pickFile(f: File | undefined) {
  if (!f) return
  busy.value = true; report.value = null
  try {
    file.value = f
    const p = await api.parseDevices(props.pid, f)
    parsed.value = p
    for (const k of Object.keys(mapping)) delete mapping[k]
    for (const fld of p.fields) mapping[fld.key] = p.mapping[fld.key] ?? ''
  } catch (e) { toast((e as Error).message, 'error'); file.value = null; parsed.value = null } finally { busy.value = false }
}
const isMapped = (k: string) => mapping[k] !== '' && mapping[k] !== undefined
const mapOk = computed(() => !!parsed.value && parsed.value.fields.filter(f => f.required).every(f => isMapped(f.key)) && (isMapped('standort') || isMapped('loc')))
const parents = computed(() => d.value.tasks.filter(t => t.summary || !t.pool).map(t => ({ id: t.id, label: `${t.wbs} ${t.name}` })))

async function run(dry: boolean) {
  if (!file.value || !parsed.value) return
  busy.value = true
  try {
    const map: Record<string, number> = {}
    for (const [k, v] of Object.entries(mapping)) if (v !== '' && v !== undefined) map[k] = Number(v)
    const rm: Record<string, number> = {}
    for (const [k, v] of Object.entries(roleMap)) if (v) rm[k] = Number(v)
    const r = await api.importDevices(props.pid, file.value, { mapping: map, dry_run: dry, partial: o.partial, create_missing: o.create_missing, parent_id: o.parent_id || null, role_map: rm })
    report.value = r
    if (!dry && r.imported) { toast(tr('Geräteliste importiert: {1} neu, {2} aktualisiert', { 1: r.new, 2: r.updated })); emit('done', r) }
  } catch (e) { toast((e as Error).message, 'error') } finally { busy.value = false }
}
const canImport = computed(() => !!report.value && report.value.dry_run && (report.value.error_count === 0 || o.partial) && (report.value.new + report.value.updated > 0))
async function sample() { try { await downloadDeviceSample() } catch (e) { toast((e as Error).message, 'error') } }
function onDrop(e: DragEvent) { dragover.value = false; pickFile(e.dataTransfer?.files?.[0]) }
</script>

<template>
  <div class="modal-back" @mousedown.self="emit('close')">
    <div class="modal big">
      <h3>{{ $t('Geräteliste importieren') }} <small class="dim">{{ $t('Excel (.xlsx) oder CSV') }}</small></h3>

      <!-- 1 Datei -->
      <div v-if="step === 1" class="drop" :class="{ over: dragover }" @dragover.prevent="dragover = true" @dragleave="dragover = false" @drop.prevent="onDrop">
        <p>{{ $t('Geräteliste hierher ziehen oder auswählen.') }}</p>
        <input type="file" accept=".xlsx,.xlsm,.csv,.txt" :disabled="busy" @change="pickFile(($event.target as HTMLInputElement).files?.[0])" />
        <p><button type="button" @click="sample">{{ $t('⬇ Muster-Excel herunterladen') }}</button></p>
        <p class="dim">{{ $t('Das Muster enthält alle Spalten, Auswahllisten und deine aktuellen Vorlagen. Pflicht sind Hostname, Standort und Gerätetyp. Der Gerätetyp wählt die Vorlage (Arbeitsschritte).') }}</p>
      </div>

      <!-- 2 Zuordnung + Vorschau -->
      <template v-if="step === 2 && parsed">
        <p class="dim">{{ $t('{1} · Blatt „{2}“ · {3} Zeilen · vorhandene Vorlagen: {4}', { 1: file?.name, 2: parsed.sheet, 3: parsed.rows_total, 4: parsed.templates.join(', ') }) }}</p>
        <div class="cols">
          <section>
            <h4>{{ $t('Spalten zuordnen') }}</h4>
            <table class="map">
              <tr v-for="f in parsed.fields" :key="f.key">
                <td>{{ $t(f.label) }}<span v-if="f.required" class="req"> *</span></td>
                <td><select v-model="mapping[f.key]" :class="{ miss: f.required && mapping[f.key] === '' }">
                  <option value="">{{ $t('– nicht importieren –') }}</option><option v-for="c in parsed.columns" :key="c.index" :value="c.index">{{ c.name || '(' + $t('Spalte') + ' ' + (c.index + 1) + ')' }}</option></select></td>
              </tr>
            </table>
          </section>
          <section>
            <h4>{{ $t('Optionen') }}</h4>
            <label>{{ $t('Einfügen unter') }} <select v-model.number="o.parent_id"><option :value="0">{{ $t('Oberste Ebene des Plans') }}</option><option v-for="p in parents" :key="p.id" :value="p.id">{{ p.label }}</option></select></label>
            <label class="chk"><input type="checkbox" v-model="o.create_missing" /> {{ $t('unbekannte Kostenstellen/-arten anlegen') }}</label>
            <label class="chk"><input type="checkbox" v-model="o.partial" /> {{ $t('fehlerhafte Zeilen überspringen (sonst alles oder nichts)') }}</label>
            <h4>{{ $t('Rollen → Ressourcen') }}</h4>
            <p class="dim">{{ $t('Schritte einer Rolle werden dieser Ressource zugeordnet. Ohne Zuordnung gehen sie an „Verantwortlich“ der Zeile, sonst liegen sie im Pool zur Selbstübernahme.') }}</p>
            <table class="map" v-if="roles.length">
              <tr v-for="r in roles" :key="r"><td>{{ r }}</td>
                <td><select v-model.number="roleMap[r]"><option :value="0">{{ $t('– Pool / Verantwortlich –') }}</option><option v-for="res in d.resources" :key="res.id" :value="res.id">{{ res.name }}</option></select></td></tr>
            </table>
            <p v-else class="dim">{{ $t('Keine Rollen in den Vorlagen.') }}</p>
            <p v-if="!d.resources.length" class="dim">{{ $t('Im Projekt gibt es noch keine Ressourcen (Tab „Ressourcen“).') }}</p>
          </section>
        </div>
        <details class="sample"><summary>{{ $t('Beispielzeilen der Datei') }}</summary>
          <table><tr><th v-for="c in parsed.columns" :key="c.index">{{ c.name }}</th></tr><tr v-for="(r, i) in parsed.sample" :key="i"><td v-for="(c, j) in r" :key="j">{{ c }}</td></tr></table></details>

        <!-- Bericht -->
        <div v-if="report" class="rep" :class="{ bad: report.error_count }">
          <b>{{ report.dry_run ? 'Vorschau' : 'Ergebnis' }}:</b> {{ $t('{1} neue Geräte · {2} aktualisiert · {3} Schritte · {4} neue Standorte', { 1: report.new, 2: report.updated, 3: report.steps, 4: report.sites_new }) }}
          <span v-if="report.new_cost_centers.length"> {{ $t('· neue Kostenstellen: {1}', { 1: report.new_cost_centers.join(', ') }) }}</span>
          <span v-if="report.new_cost_types.length"> {{ $t('· neue Kostenarten: {1}', { 1: report.new_cost_types.join(', ') }) }}</span>
          <ul v-if="report.warnings.length" class="warns"><li v-for="w in report.warnings" :key="w">⚠ {{ tm(w) }}</li></ul>
          <div v-if="report.error_count" class="errs"><b>{{ $t('{1} Fehler', { 1: report.error_count }) }}</b> <span v-if="!o.partial">{{ $t('(ohne „Zeilen überspringen“ wird nichts importiert)') }}</span>
            <ul><li v-for="e in report.errors.slice(0, 30)" :key="e.row + e.message">{{ $t('Zeile {1}', { 1: e.row }) }}<span v-if="e.hostname"> ({{ e.hostname }})</span>: {{ tm(e.message) }}</li></ul>
            <small v-if="report.errors.length > 30">{{ $t('… und {1} weitere', { 1: report.errors.length - 30 }) }}</small></div>
          <table v-if="report.items.length" class="prev"><tr><th>{{ $t('Zeile') }}</th><th>{{ $t('Hostname') }}</th><th>{{ $t('Standort') }}</th><th>{{ $t('Vorlage') }}</th><th>{{ $t('Aktion') }}</th><th>{{ $t('Schritte') }}</th></tr>
            <tr v-for="i in report.items" :key="i.row"><td>{{ i.row }}</td><td>{{ i.hostname }}</td><td>{{ i.loc ? i.loc + ' · ' : '' }}{{ i.standort }}</td><td>{{ i.typ }}</td><td>{{ i.action }}</td><td>{{ i.steps }}</td></tr></table>
        </div>
        <div class="actions">
          <button @click="emit('close')">{{ $t('Abbrechen') }}</button>
          <button @click="parsed = null; report = null; file = null">{{ $t('Andere Datei') }}</button>
          <button :disabled="busy || !mapOk" @click="run(true)">{{ $t('Vorschau prüfen') }}</button>
          <button class="primary" :disabled="busy || !canImport" @click="run(false)">{{ $t('Importieren') }}</button>
        </div>
      </template>

      <!-- 3 Ergebnis -->
      <template v-if="step === 3 && report">
        <div class="rep ok"><b>{{ $t('Import abgeschlossen.') }}</b> {{ $t('{1} neue Geräte, {2} aktualisiert, {3} Schritte angelegt.', { 1: report.new, 2: report.updated, 3: report.steps }) }}
          <span v-if="report.error_count">{{ $t('{1} Zeilen übersprungen.', { 1: report.error_count }) }}</span></div>
        <p class="dim">{{ $t('Der Import lässt sich mit „Rückgängig“ (↶ / Strg+Z) in einem Schritt zurücknehmen. Die Geräte und ihre Schritte siehst du im Tab „Geräte“.') }}</p>
        <div class="actions"><button class="primary" @click="emit('close')">{{ $t('Fertig') }}</button></div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.big { width: min(1100px, 96vw); max-height: 92vh; overflow: auto; }
.dim { color: var(--fg-dim); font-size: 12px; } h3 small { font-weight: 400; margin-left: 6px; } h4 { margin: 10px 0 4px; font-size: 13px; }
.drop { border: 2px dashed var(--border); border-radius: 10px; padding: 26px; text-align: center; } .drop.over { border-color: var(--accent); background: var(--row-sel); }
.cols { display: grid; grid-template-columns: 1.1fr 1fr; gap: 20px; } @media (max-width: 800px) { .cols { grid-template-columns: 1fr; } }
.map { border-collapse: collapse; width: 100%; font-size: 13px; } .map td { padding: 2px 6px 2px 0; } .map td:first-child { white-space: nowrap; width: 46%; } .map select { width: 100%; }
.req { color: var(--bar-critical); } select.miss { border-color: var(--bar-critical); }
label { display: flex; flex-direction: column; gap: 3px; font-size: 13px; margin: 4px 0; } label.chk { flex-direction: row; align-items: center; gap: 6px; } input[type=checkbox] { width: auto; }
.sample { margin: 10px 0; font-size: 12px; overflow: auto; } .sample table { border-collapse: collapse; } .sample th, .sample td { border: 1px solid var(--border); padding: 2px 6px; white-space: nowrap; }
.rep { border: 1px solid var(--border); border-left: 4px solid var(--ok); border-radius: 8px; padding: 8px 12px; margin: 10px 0; font-size: 13px; } .rep.bad { border-left-color: var(--bar-critical); } .rep.ok { border-left-color: var(--ok); }
.errs { color: var(--bar-critical); margin-top: 6px; } .errs ul, .warns { margin: 4px 0 0; padding-left: 18px; } .warns { color: var(--blocked); list-style: none; padding: 0; }
.prev { border-collapse: collapse; margin-top: 8px; font-size: 12px; width: 100%; } .prev th, .prev td { text-align: left; padding: 2px 8px; border-bottom: 1px solid var(--border); }
.actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 10px; flex-wrap: wrap; }
</style>
