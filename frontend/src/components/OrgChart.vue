<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import type { ProjectData } from '../lib/types'
import { buildOrg, orgSvg, type OrgNode } from '../lib/orgchart'
import { downloadBlob, fileSlug, printSvgPages, svgToPngBlob } from '../lib/exportImage'
import { toast } from '../lib/store'
import { t as tr } from '../lib/i18n'

/** Organigramm eines Projekts (Struktur aus „Berichtet an“ im Tab Ressourcen), Umhängen per Ziehen, Export als PNG/SVG/PDF. */
const props = defineProps<{ data: ProjectData; editable?: boolean }>()
const emit = defineEmits<{ (e: 'move', rid: number, parent: number | null): void }>()
const busy = ref(false)
const title = () => props.data.project.name + ' – ' + tr('Organigramm')
const tree = computed(() => buildOrg(props.data))
const out = computed(() => (tree.value ? orgSvg(tree.value, title()) : null))
const base = () => fileSlug(props.data.project.name + '_' + tr('Organigramm'))

// ── Export ──────────────────────────────────────────────────────────────────
type Fmt = 'auto' | 'a4' | 'a3' | 'slide'
const FMT_KEY = 'openplan.orgfmt'
const initial = (): Fmt => { try { const v = localStorage.getItem(FMT_KEY); return v === 'a4' || v === 'a3' || v === 'slide' ? v : 'auto' } catch { return 'auto' } }
const fmt = ref<Fmt>(initial())
const setFmt = () => { try { localStorage.setItem(FMT_KEY, fmt.value) } catch { /* ignorieren */ } }

async function png() {
  if (!out.value) return
  busy.value = true
  try { downloadBlob(await svgToPngBlob(out.value.svg, out.value.w, out.value.h, 2), base() + '.png') }
  catch (e) { toast((e as Error).message, 'error') } finally { busy.value = false }
}
function svg() { if (out.value) downloadBlob(new Blob([out.value.svg], { type: 'image/svg+xml' }), base() + '.svg') }
function pdf() {
  if (!out.value) return
  const size = ({ a4: { mm: [297, 210] }, a3: { mm: [420, 297] }, slide: { mm: [338.7, 190.5] } } as Record<string, { mm: [number, number] }>)[fmt.value]
  printSvgPages([out.value.svg], size ?? { px: [out.value.w, out.value.h] }, title())   // feste Formate: das SVG skaliert über die viewBox auf die Seite
}

// ── Umhängen per Ziehen (nur Maus/Stift; auf Touchgeräten über „Berichtet an“) ──
interface Drag { key: string; label: string; x: number; y: number; started: boolean; sx: number; sy: number; blocked: Set<string>; parent: string; over: string | null }
const drag = ref<Drag | null>(null)
let hot: Element | null = null

function walk(n: OrgNode, fn: (n: OrgNode, parent: OrgNode | null) => void, parent: OrgNode | null = null) { fn(n, parent); n.children.forEach(c => walk(c, fn, n)) }
function subtreeKeys(n: OrgNode): Set<string> { const s = new Set<string>(); walk(n, x => s.add(x.key)); return s }
const nodeG = (x: number, y: number) => document.elementFromPoint(x, y)?.closest('g[data-key]') ?? null
const keyOf = (g: Element | null) => g?.getAttribute('data-key') ?? null
function setHot(g: Element | null) { if (hot === g) return; hot?.classList.remove('drop-ok'); hot = g; hot?.classList.add('drop-ok') }

function down(e: PointerEvent) {
  if (!props.editable || !tree.value || e.pointerType === 'touch' || e.button !== 0) return
  const key = keyOf((e.target as Element).closest('g[data-key]'))
  if (!key || !key.startsWith('r')) return                    // nur Ressourcen sind verschiebbar (nicht Projektleitung/Mitglieder)
  let node: OrgNode | null = null, parent = 'root'
  walk(tree.value, (n, p) => { if (n.key === key) { node = n; parent = p?.key ?? 'root' } })
  if (!node) return
  e.preventDefault()
  drag.value = { key, label: (node as OrgNode).title, x: e.clientX, y: e.clientY, started: false, sx: e.clientX, sy: e.clientY, blocked: subtreeKeys(node), parent, over: null }
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', up)
  window.addEventListener('pointercancel', stop)
}
function move(e: PointerEvent) {
  const d = drag.value
  if (!d) return
  d.x = e.clientX; d.y = e.clientY
  if (!d.started && Math.hypot(e.clientX - d.sx, e.clientY - d.sy) > 6) d.started = true
  if (!d.started) return
  const g = nodeG(e.clientX, e.clientY)
  const k = keyOf(g)
  const ok = !!k && (k === 'root' || k.startsWith('r')) && !d.blocked.has(k) && k !== d.parent
  d.over = ok ? k : null
  setHot(ok ? g : null)
}
function stop() {
  window.removeEventListener('pointermove', move)
  window.removeEventListener('pointerup', up)
  window.removeEventListener('pointercancel', stop)
  setHot(null)
  drag.value = null
}
function up() {
  const d = drag.value
  stop()
  if (!d || !d.started || !d.over) return
  emit('move', Number(d.key.slice(1)), d.over === 'root' ? null : Number(d.over.slice(1)))
}
onBeforeUnmount(stop)
</script>

<template>
  <div class="oc">
    <div v-if="out" class="bar">
      <button :disabled="busy" :title="$t('Als Bild speichern (z. B. für Folien)')" @click="png">PNG</button>
      <button :title="$t('Als Vektorgrafik speichern')" @click="svg">SVG</button>
      <span class="pdf">
        <button :title="$t('Als PDF drucken/speichern')" @click="pdf">PDF</button>
        <select v-model="fmt" :aria-label="$t('PDF-Seitenformat')" :title="$t('PDF-Seitenformat')" @change="setFmt">
          <option value="auto">{{ $t('Bildgröße') }}</option><option value="a4">{{ $t('A4 quer') }}</option><option value="a3">{{ $t('A3 quer') }}</option><option value="slide">{{ $t('Folie 16:9') }}</option>
        </select>
      </span>
      <span class="dim">{{ $t('Aufbau: Tab „Ressourcen“ → Spalte „Berichtet an“') }}</span>
      <span v-if="editable" class="dim hint">{{ $t('Ziehen: ein Kästchen auf ein anderes ziehen = unterstellen, auf die Projektleitung = direkt unterstellen') }}</span>
    </div>
    <p v-if="!out" class="dim">{{ $t('Kein Verantwortlicher – kein Organigramm.') }}</p>
    <div v-else class="sheet" :class="{ edit: editable, dragging: drag?.started }" @pointerdown="down" v-html="out.svg" />
    <div v-if="drag?.started" class="ghost" :style="{ left: drag.x + 14 + 'px', top: drag.y + 14 + 'px' }">{{ drag.label }}</div>
  </div>
</template>

<style scoped>
.bar { display: flex; gap: 8px; align-items: center; margin-bottom: 10px; flex-wrap: wrap; }
.pdf { display: inline-flex; gap: 4px; align-items: center; }
.oc { min-width: 0; }
.dim { color: var(--fg-dim); }
.bar .dim { flex: 1 1 220px; min-width: 0; }
.hint { flex-basis: 100%; font-size: 12px; }
@media (pointer: coarse) { .hint { display: none; } }   /* Ziehen nur mit Maus/Stift */
.sheet { overflow: auto; background: #fff; border: 1px solid var(--border); border-radius: 8px; max-width: 100%; }
.sheet :deep(svg) { display: block; }
.sheet.edit :deep(g[data-key^="r"]) { cursor: grab; }
.sheet.dragging { user-select: none; cursor: grabbing; }
.sheet.dragging :deep(g[data-key^="r"]) { cursor: grabbing; }
.sheet :deep(g.drop-ok rect) { stroke: #16a34a; stroke-width: 3; }
.ghost { position: fixed; z-index: 200; pointer-events: none; padding: 5px 10px; border-radius: 6px; background: #1d4ed8; color: #fff; font-size: 13px; box-shadow: 0 4px 14px rgba(0, 0, 0, .3); max-width: 240px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
