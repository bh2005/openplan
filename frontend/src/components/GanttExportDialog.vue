<script setup lang="ts">
// Gantt als PNG / SVG / PDF exportieren (Folien für Vorstand & Management). Rendert unabhängig von der Bildschirmansicht.
import { computed, reactive, ref, watch } from 'vue'
import { buildGanttPages, PAGE, colLabel, type Col, type GanttExportOptions, type PageFmt, type Scope } from '../lib/exportGantt'
import { downloadBlob, fileSlug, printSvgPages, svgToPngBlob } from '../lib/exportImage'
import { fmt, todayIso, WorkCal } from '../lib/dates'
import { STATUS_LABEL } from '../lib/status'
import { toast } from '../lib/store'
import type { Dep, Task } from '../lib/types'
import { t as tr } from '../lib/i18n'

const props = defineProps<{ tasks: Task[]; deps: Dep[]; cal: WorkCal; resourceNames: Record<number, string>; projectName: string; hasBaseline: boolean }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const ALL_COLS: Col[] = ['wbs', 'name', 'start', 'finish', 'duration', 'percent', 'status', 'resources']
const KEY = 'openplan.exportopts'
const defaults = (): GanttExportOptions => ({
  scope: 'all', maxLevel: 2, from: '', to: '', cols: ['wbs', 'name', 'start', 'finish', 'percent'], title: props.projectName,
  subtitle: tr('Stand') + ' ' + fmt(todayIso()), fmt: 'slide', showToday: true, showBaseline: props.hasBaseline, showCritical: true,
  showDeps: false, showLegend: true, barLabels: false,
})
const o = reactive<GanttExportOptions>(defaults())
try {                                                  // zuletzt benutzte Einstellungen (ohne Titel/Zeitraum)
  const saved = JSON.parse(localStorage.getItem(KEY) ?? 'null')
  if (saved) Object.assign(o, saved, { title: props.projectName, subtitle: tr('Stand') + ' ' + fmt(todayIso()), from: '', to: '' })
} catch { /* privat */ }
const busy = ref(false)

watch(() => o.scope, s => {                            // Voreinstellungen je Umfang
  if (s === 'phases') Object.assign(o, { cols: ['name', 'start', 'finish'], barLabels: true, showDeps: false })
  else if (s === 'all') Object.assign(o, { cols: ['wbs', 'name', 'start', 'finish', 'percent'], barLabels: false })
})
watch(o, () => { try { const { title, subtitle, from, to, ...rest } = o; localStorage.setItem(KEY, JSON.stringify(rest)) } catch { /* privat */ } }, { deep: true })

const built = computed(() => buildGanttPages({ tasks: props.tasks, deps: props.deps, cal: props.cal, resourceNames: props.resourceNames, statusLabel: s => STATUS_LABEL[s as keyof typeof STATUS_LABEL] ?? s }, o))
const toggleCol = (c: Col) => { o.cols = o.cols.includes(c) ? o.cols.filter(x => x !== c) : ALL_COLS.filter(x => x === c || o.cols.includes(x)) }
const name = () => fileSlug(o.title || props.projectName)

async function png() {
  busy.value = true
  try {
    const b = built.value
    for (let i = 0; i < b.pages.length; i++) downloadBlob(await svgToPngBlob(b.pages[i], b.width, b.height, 2), `${name()}${b.pages.length > 1 ? '_' + (i + 1) : ''}.png`)
  } catch (e) { toast((e as Error).message, 'error') } finally { busy.value = false }
}
function svg() {
  const b = built.value
  b.pages.forEach((p, i) => downloadBlob(new Blob([p], { type: 'image/svg+xml' }), `${name()}${b.pages.length > 1 ? '_' + (i + 1) : ''}.svg`))
}
function pdf() {
  const b = built.value
  printSvgPages(b.pages, o.fmt === 'auto' ? { px: [b.width, b.height] } : { mm: PAGE[o.fmt].mm }, o.title || props.projectName)
}
const FMTS: { v: PageFmt; l: () => string }[] = [
  { v: 'slide', l: () => tr('Folie 16:9') }, { v: 'a4', l: () => tr('A4 quer') }, { v: 'a3', l: () => tr('A3 quer') }, { v: 'auto', l: () => tr('Automatisch (Originalgröße)') },
]
const SCOPES: { v: Scope; l: () => string }[] = [
  { v: 'all', l: () => tr('Alle Vorgänge') }, { v: 'phases', l: () => tr('Phasen & Meilensteine (Management-Sicht)') }, { v: 'critical', l: () => tr('Nur kritischer Pfad') },
]
</script>

<template>
  <div class="modal-back" @mousedown.self="emit('close')">
    <div class="modal xd" role="dialog" :aria-label="$t('Gantt exportieren')">
      <h3>{{ $t('Gantt als Bild / PDF exportieren') }}</h3>
      <div class="cols">
        <div class="opts">
          <label>{{ $t('Umfang') }}<select v-model="o.scope"><option v-for="s in SCOPES" :key="s.v" :value="s.v">{{ s.l() }}</option></select></label>
          <label v-if="o.scope === 'phases'">{{ $t('Ebenen der Phasen') }}<select v-model.number="o.maxLevel"><option v-for="n in 4" :key="n" :value="n">{{ n }}</option></select></label>
          <label>{{ $t('Format') }}<select v-model="o.fmt"><option v-for="f in FMTS" :key="f.v" :value="f.v">{{ f.l() }}</option></select></label>
          <div class="two">
            <label>{{ $t('Von') }}<input v-model="o.from" type="date" /></label>
            <label>{{ $t('Bis') }}<input v-model="o.to" type="date" /></label>
          </div>
          <label>{{ $t('Titel') }}<input v-model="o.title" maxlength="120" /></label>
          <label>{{ $t('Untertitel') }}<input v-model="o.subtitle" maxlength="160" /></label>
          <fieldset><legend>{{ $t('Spalten') }}</legend>
            <label v-for="c in ALL_COLS" :key="c" class="chk"><input type="checkbox" :checked="o.cols.includes(c)" @change="toggleCol(c)" /> {{ colLabel(c) }}</label>
          </fieldset>
          <fieldset><legend>{{ $t('Anzeigen') }}</legend>
            <label class="chk"><input type="checkbox" v-model="o.showToday" /> {{ $t('Heute-Linie') }}</label>
            <label class="chk"><input type="checkbox" v-model="o.showCritical" /> {{ $t('Kritischer Pfad') }}</label>
            <label class="chk"><input type="checkbox" v-model="o.showBaseline" :disabled="!hasBaseline" /> {{ $t('Basisplan') }}</label>
            <label class="chk"><input type="checkbox" v-model="o.showDeps" /> {{ $t('Abhängigkeiten') }}</label>
            <label class="chk"><input type="checkbox" v-model="o.barLabels" /> {{ $t('Beschriftung am Balken') }}</label>
            <label class="chk"><input type="checkbox" v-model="o.showLegend" /> {{ $t('Legende') }}</label>
          </fieldset>
        </div>
        <div class="prev">
          <div class="pv" v-html="built.pages[0]" />
          <small class="dim">{{ $t('{1} Zeilen · {2} Seite(n)', { 1: built.rows, 2: built.pages.length }) }}<template v-if="built.pages.length > 1"> · {{ $t('Vorschau zeigt Seite 1') }}</template></small>
        </div>
      </div>
      <div class="actions">
        <small class="dim hint">{{ $t('PDF: im Druckdialog „Als PDF speichern“ wählen, Ränder „Keine“.') }}</small>
        <button type="button" @click="emit('close')">{{ $t('Schließen') }}</button>
        <button type="button" :disabled="busy" @click="svg">SVG</button>
        <button type="button" :disabled="busy" @click="pdf">PDF</button>
        <button type="button" class="primary" :disabled="busy" @click="png">PNG</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.xd { width: min(1180px, 97vw); }
.cols { display: grid; grid-template-columns: 290px 1fr; gap: 16px; }
.opts { display: flex; flex-direction: column; gap: 0; max-height: 62vh; overflow: auto; padding-right: 6px; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
fieldset { border: 1px solid var(--border); border-radius: 8px; margin: 4px 0 10px; padding: 6px 10px; display: flex; flex-wrap: wrap; gap: 2px 12px; }
legend { font-size: 12px; color: var(--fg-dim); padding: 0 4px; }
.chk { margin: 0 !important; font-size: 13px; }
.prev { min-width: 0; display: flex; flex-direction: column; gap: 6px; }
.pv { border: 1px solid var(--border); background: #fff; border-radius: 6px; overflow: auto; max-height: 62vh; }
.pv :deep(svg) { display: block; width: 100%; height: auto; }
.dim { color: var(--fg-dim); } .hint { margin-right: auto; align-self: center; }
@media (max-width: 800px) { .cols { grid-template-columns: 1fr; } .opts { max-height: none; } .pv { max-height: 40vh; } }
</style>
