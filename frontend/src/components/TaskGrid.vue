<script setup lang="ts">
import { nextTick, ref } from 'vue'
import type { Dep, Task } from '../lib/types'
import { addDays, fmt, WorkCal } from '../lib/dates'
import { depToText } from '../lib/deps'
import { toast } from '../lib/store'
import { STATUS } from '../lib/status'
import { t as tr } from '../lib/i18n'

const props = defineProps<{
  rows: Task[]
  wbsById: Record<number, string>
  deps: Dep[]
  collapsed: Set<number>
  selectedId: number | null
  selectedIds: Set<number>
  readonly: boolean
  canWork?: (t: Task) => boolean     // Mitarbeiter: Status/Fortschritt eigener Vorgänge trotz readonly
  rowHeight: number
  headerHeight: number
  resourceNames: Record<number, string>
  cal: WorkCal
  tracking: boolean          // Abweichungsspalten zum Basisplan
  showFloat?: boolean        // Spalten Gesamtpuffer / freier Puffer
  nearDays?: number          // „knapp kritisch“: Gesamtpuffer 1…nearDays Tage
}>()
const emit = defineEmits<{
  (e: 'select', id: number, mods: { ctrl: boolean; shift: boolean }): void
  (e: 'status', id: number, status: string): void
  (e: 'toggle', id: number): void
  (e: 'open', id: number): void
  (e: 'edit', id: number, field: string, value: string): void
}>()

type Field = 'name' | 'duration' | 'start' | 'percent' | 'preds'
const editing = ref<{ id: number; field: Field } | null>(null)
const draft = ref('')
const inputEl = ref<HTMLInputElement[] | HTMLInputElement | null>(null)

/** Abweichung in Arbeitstagen: >0 = später als im Basisplan */
function variance(actual: string, base: string | null): number | null {
  if (!base) return null
  if (actual === base) return 0
  return actual > base ? props.cal.count(addDays(base, 1), actual) : -props.cal.count(addDays(actual, 1), base)
}
const ftxt = (v: number | null | undefined) => (v == null ? '' : v + ' T')
const fcls = (v: number | null | undefined) => (v == null ? '' : v <= 0 ? 'vlate' : v <= (props.nearDays ?? 0) ? 'fnear' : 'v0')
const vtxt = (v: number | null) => (v == null ? '' : v === 0 ? '0' : (v > 0 ? '+' : '−') + Math.abs(v) + ' T')
const vcls = (v: number | null) => (v == null || v === 0 ? 'v0' : v > 0 ? 'vlate' : 'vearly')

const predText = (t: Task) =>
  props.deps.filter(d => d.succ_id === t.id).map(d => depToText(d, id => props.wbsById[id])).join(', ')

function begin(t: Task, field: Field) {
  if (props.readonly && !(field === 'percent' && props.canWork?.(t))) return
  if (t.summary && (field === 'duration' || field === 'percent')) {
    toast(tr('Sammelvorgang: Dauer und Fortschritt ergeben sich aus den Teilvorgängen. Ändere die Teilvorgänge – oder den Beginn, um die ganze Phase zu verschieben.'))
    return
  }
  editing.value = { id: t.id, field }
  draft.value = field === 'name' ? t.name
    : field === 'duration' ? String(t.duration)
    : field === 'percent' ? String(t.percent)
    : field === 'start' ? fmt(t.start)
    : predText(t)
  nextTick(() => {
    const el = Array.isArray(inputEl.value) ? inputEl.value[0] : inputEl.value
    el?.focus(); el?.select()
  })
}
function commit() {
  const e = editing.value
  if (!e) return
  editing.value = null
  emit('edit', e.id, e.field, draft.value)
}
const cancel = () => (editing.value = null)
const isEd = (t: Task, f: Field) => editing.value?.id === t.id && editing.value.field === f
</script>

<template>
  <div class="tgrid">
    <div class="thead" :style="{ height: headerHeight + 'px' }">
      <div class="c chk" :title="$t('Erledigt')">✓</div>
      <div class="c wbs">{{ $t('PSP') }}</div>
      <div class="c name">{{ $t('Vorgangsname') }}</div>
      <div class="c num">{{ $t('Dauer') }}</div>
      <div class="c date">{{ $t('Beginn') }}</div>
      <div class="c date">{{ $t('Ende') }}</div>
      <div class="c num">%</div>
      <div class="c st">{{ $t('Status') }}</div>
      <div class="c pred">{{ $t('Vorgänger') }}</div>
      <template v-if="showFloat"><div class="c var" :title="$t('Gesamtpuffer: so viele Arbeitstage darf der Vorgang rutschen, ohne das Projektende zu verschieben')">{{ $t('Puffer') }}</div><div class="c var" :title="$t('Freier Puffer: so viele Arbeitstage darf der Vorgang rutschen, ohne einen Nachfolger zu verschieben')">{{ $t('fr. Puffer') }}</div></template>
      <template v-if="tracking"><div class="c var" :title="$t('Abweichung Beginn zum Basisplan (Arbeitstage)')">{{ $t('Δ Beginn') }}</div><div class="c var" :title="$t('Abweichung Ende zum Basisplan (Arbeitstage)')">{{ $t('Δ Ende') }}</div></template>
    </div>
    <div v-for="t in rows" :key="t.id" class="trow"
         :class="['s-' + t.status, { sel: selectedIds.has(t.id) || t.id === selectedId, sum: t.summary, crit: t.critical && !t.summary }]"
         :style="{ height: rowHeight + 'px' }" @click="emit('select', t.id, { ctrl: $event.ctrlKey || $event.metaKey, shift: $event.shiftKey })" @dblclick.self="emit('open', t.id)">
      <div class="c chk" @click.stop>
        <input type="checkbox" :checked="t.status === 'done'" :indeterminate.prop="t.summary && t.status === 'in_progress'" :disabled="readonly && !canWork?.(t)"
               :title="t.summary ? $t('Alle Teilvorgänge erledigt / offen setzen') : $t('Erledigt')"
               @change="emit('status', t.id, ($event.target as HTMLInputElement).checked ? 'done' : 'open')" />
      </div>
      <div class="c wbs">{{ t.wbs }}</div>
      <div class="c name" :style="{ paddingLeft: 6 + t.level * 16 + 'px' }" @dblclick="begin(t, 'name')">
        <button v-if="t.summary" class="tog" @click.stop="emit('toggle', t.id)" :title="collapsed.has(t.id) ? $t('Aufklappen') : $t('Zuklappen')">
          {{ collapsed.has(t.id) ? '▸' : '▾' }}
        </button>
        <span v-else class="tog-sp" />
        <input v-if="isEd(t, 'name')" ref="inputEl" v-model="draft" @keydown.enter="commit" @keydown.esc="cancel" @blur="commit" />
        <span v-else class="txt" :title="t.name">{{ t.name }}</span>
        <button v-if="t.comment_count" class="clip" :title="$t('{1} Kommentar(e) – Klick öffnet die Details', { 1: t.comment_count })" @click.stop="emit('open', t.id)">💬{{ t.comment_count > 1 ? t.comment_count : '' }}</button>
        <span v-if="t.deadline_missed" class="dlmiss" :title="$t('Frist überschritten: bis {1}, geplantes Ende {2}', { 1: t.deadline, 2: t.finish })">⚠</span>
        <span v-if="t.pool" class="pool" :title="t.resource_ids.length ? $t('Arbeitspaket (übernommen)') : $t('Arbeitspaket – offen im Pool, Selbstübernahme im Tab Pakete')">{{ t.resource_ids.length ? '▣' : '◌' }}</span>
        <button v-if="t.file_count" class="clip" :title="$t('{1} Dokument(e)/Link(s) – Klick öffnet die Details', { 1: t.file_count })" @click.stop="emit('open', t.id)">📎{{ t.file_count > 1 ? t.file_count : '' }}</button>
      </div>
      <div class="c num" @dblclick="begin(t, 'duration')">
        <input v-if="isEd(t, 'duration')" ref="inputEl" v-model="draft" type="number" min="0" @keydown.enter="commit" @keydown.esc="cancel" @blur="commit" />
        <template v-else>{{ t.milestone ? '◆' : t.duration + ' T' }}</template>
      </div>
      <div class="c date" @dblclick="begin(t, 'start')">
        <input v-if="isEd(t, 'start')" ref="inputEl" v-model="draft" :placeholder="$t('TT.MM.JJ')" @keydown.enter="commit" @keydown.esc="cancel" @blur="commit" />
        <template v-else>{{ fmt(t.start) }}<span v-if="t.constraint_type !== 'ASAP' && !t.summary" class="pin" :title="$t('Einschränkung') + ': ' + t.constraint_type + ' ' + (t.constraint_date ?? '')">📌</span></template>
      </div>
      <div class="c date" @dblclick="t.summary && toast('Ende ergibt sich aus den Teilvorgängen. Beginn ändern verschiebt die ganze Phase.')">{{ fmt(t.finish) }}</div>
      <div class="c num" @dblclick="begin(t, 'percent')">
        <input v-if="isEd(t, 'percent')" ref="inputEl" v-model="draft" type="number" min="0" max="100" @keydown.enter="commit" @keydown.esc="cancel" @blur="commit" />
        <template v-else>{{ Math.round(t.percent) }}%</template>
      </div>
      <div class="c st" @click.stop @dblclick.stop>
        <select class="stsel" :class="t.status" :value="t.status" :disabled="readonly && !canWork?.(t)" :title="t.status === 'blocked' && t.status_note ? t.status_note : 'Status'"
                @change="emit('status', t.id, ($event.target as HTMLSelectElement).value)">
          <option v-for="s in STATUS" :key="s.value" :value="s.value">{{ s.label }}</option>
        </select>
      </div>
      <div class="c pred" @dblclick="begin(t, 'preds')">
        <input v-if="isEd(t, 'preds')" ref="inputEl" v-model="draft" :placeholder="$t('z. B. 2, 3AA+1T')" @keydown.enter="commit" @keydown.esc="cancel" @blur="commit" />
        <span v-else :title="predText(t)">{{ predText(t) }}</span>
      </div>
      <template v-if="showFloat">
        <div class="c var" :class="fcls(t.total_float)">{{ ftxt(t.total_float) }}</div>
        <div class="c var" :class="fcls(t.free_float)">{{ ftxt(t.free_float) }}</div>
      </template>
      <template v-if="tracking">
        <div class="c var" :class="vcls(variance(t.start, t.baseline_start))" :title="t.baseline_start ? $t('Basisplan') + ': ' + fmt(t.baseline_start) : $t('kein Basisplan')">{{ vtxt(variance(t.start, t.baseline_start)) }}</div>
        <div class="c var" :class="vcls(variance(t.finish, t.baseline_finish))" :title="t.baseline_finish ? $t('Basisplan') + ': ' + fmt(t.baseline_finish) : $t('kein Basisplan')">{{ vtxt(variance(t.finish, t.baseline_finish)) }}</div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.tgrid { font-size: 13px; width: var(--grid-w); }
.thead { position: sticky; top: 0; z-index: 4; display: flex; align-items: flex-end; background: var(--bg-head); border-bottom: 1px solid var(--border); font-weight: 600; color: var(--fg-dim); }
.trow { display: flex; align-items: stretch; border-bottom: 1px solid var(--border); background: var(--bg); cursor: default; }
.trow:nth-child(odd) { background: var(--row-alt-solid); }
.trow.sel { background: var(--row-sel-solid); }
.trow.sum { font-weight: 600; }
.dlmiss { flex: none; margin-left: 4px; font-size: 12px; color: var(--bar-critical); }
.pool { flex: none; margin-left: 4px; font-size: 12px; color: var(--accent); }
.trow.crit .name .txt { color: var(--bar-critical); }
.c { display: flex; align-items: center; padding: 0 6px; overflow: hidden; white-space: nowrap; border-right: 1px solid var(--border); min-width: 0; }
.thead .c { height: 100%; align-items: flex-end; padding-bottom: 6px; }
.chk { width: 26px; flex: none; justify-content: center; padding: 0; }
.chk input { width: auto; margin: 0; accent-color: var(--ok); cursor: pointer; }
.st { width: 90px; flex: none; padding: 0 4px; }
.stsel { width: 100%; font-size: 12px; padding: 1px 2px; border-radius: 10px; border: 1px solid var(--border); background: var(--bg-input); color: var(--fg); }
.stsel.in_progress { border-color: var(--bar); color: var(--bar); } .stsel.blocked { border-color: var(--blocked); color: var(--blocked); font-weight: 600; }
.stsel.done { border-color: var(--ok); color: var(--ok); }
.trow.s-done .name .txt, .trow.s-done .c { color: var(--fg-dim); }
.trow.s-done .name .txt { text-decoration: line-through; }
.trow.s-blocked { box-shadow: inset 3px 0 0 var(--blocked); }
.wbs { width: 44px; flex: none; color: var(--fg-dim); }
.name { flex: 1 1 auto; min-width: 200px; }
.num { width: 52px; flex: none; justify-content: flex-end; }
.date { width: 70px; flex: none; }
.pred { width: 96px; flex: none; }
.var { width: 64px; flex: none; justify-content: flex-end; font-variant-numeric: tabular-nums; }
.fnear { color: var(--bar-near); font-weight: 600; } .vlate { color: var(--bar-critical); font-weight: 600; } .vearly { color: var(--ok); } .v0 { color: var(--fg-dim); }
.txt { overflow: hidden; text-overflow: ellipsis; }
.tog { width: 16px; background: none; border: 0; color: var(--fg-dim); cursor: pointer; padding: 0; flex: none; }
.tog-sp { width: 16px; flex: none; }
.pin { margin-left: 4px; font-size: 10px; }
.clip { flex: none; margin-left: 4px; padding: 0 3px; border: 0; background: none; font-size: 12px; cursor: pointer; color: var(--fg-dim); }
.clip:hover { color: var(--accent); }
input { width: 100%; padding: 1px 4px; font: inherit; background: var(--bg-input); color: var(--fg); border: 1px solid var(--accent); border-radius: 3px; }
</style>
