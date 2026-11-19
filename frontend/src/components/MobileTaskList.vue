<script setup lang="ts">
import { fmt } from '../lib/dates'
import { STATUS_LABEL } from '../lib/status'
import type { Task } from '../lib/types'

/** Smartphone-Ansicht des Plans: Karten statt Tabelle + Zeitachse. Tippen öffnet die Details, ✓ setzt erledigt/offen. */
const props = defineProps<{
  rows: Task[]
  collapsed: Set<number>
  selectedId: number | null
  resourceNames: Record<number, string>
  readonly: boolean
  canWork?: (t: Task) => boolean
  tracking: boolean
}>()
const emit = defineEmits<{
  (e: 'open', id: number): void
  (e: 'toggle', id: number): void
  (e: 'status', id: number, status: string): void
}>()

const depth = (t: Task) => Math.max(0, t.wbs.split('.').length - 1)
const who = (t: Task) => t.resource_ids.map(id => props.resourceNames[id]).filter(Boolean).join(', ')
const can = (t: Task) => !props.readonly || !!props.canWork?.(t)
const late = (t: Task) => (props.tracking && t.baseline_finish ? Math.round((new Date(t.finish).getTime() - new Date(t.baseline_finish).getTime()) / 86400000) : 0)
</script>

<template>
  <div class="mtl">
    <p v-if="!rows.length" class="dim empty">{{ $t('Noch keine Vorgänge.') }}</p>
    <ul>
      <li v-for="t in rows" :key="t.id" :class="['s-' + t.status, { sum: t.summary, sel: t.id === selectedId, crit: t.critical && !t.summary }]" :style="{ paddingLeft: 10 + depth(t) * 14 + 'px' }">
        <button v-if="t.summary" class="tog" :aria-label="collapsed.has(t.id) ? $t('Aufklappen') : $t('Zuklappen')" @click="emit('toggle', t.id)">{{ collapsed.has(t.id) ? '▸' : '▾' }}</button>
        <button v-else class="chk" :class="{ on: t.status === 'done' }" :disabled="!can(t)" :title="$t('Erledigt')" :aria-label="$t('Erledigt')"
                @click="emit('status', t.id, t.status === 'done' ? 'open' : 'done')">{{ t.status === 'done' ? '✓' : '' }}</button>
        <div class="main" @click="emit('open', t.id)">
          <div class="name"><span v-if="t.milestone">◆ </span><small class="wbs">{{ t.wbs }}</small> {{ t.name }}</div>
          <div class="meta">
            <span>{{ fmt(t.start) }} – {{ fmt(t.finish) }}</span>
            <span v-if="!t.summary || t.percent" class="st" :class="t.status">{{ STATUS_LABEL[t.status] }}<template v-if="t.percent && t.status !== 'done'"> · {{ t.percent }} %</template></span>
            <span v-if="late(t) > 0" class="lateb">+{{ late(t) }} {{ $t('AT') }}</span>
            <span v-if="who(t)" class="who">👤 {{ who(t) }}</span>
            <span v-if="t.status === 'blocked' && t.status_note" class="note">⛔ {{ t.status_note }}</span>
            <span v-if="t.deadline_missed" class="lateb">⚠ {{ $t('Frist') }}</span>
          </div>
          <div v-if="!t.summary && t.percent > 0 && t.status !== 'done'" class="bar"><i :style="{ width: t.percent + '%' }" /></div>
        </div>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.mtl { flex: 1; min-height: 0; overflow: auto; }
ul { list-style: none; margin: 0; padding: 0; }
li { display: flex; align-items: flex-start; gap: 10px; padding: 9px 12px 9px 10px; border-bottom: 1px solid var(--border); }
li.sum { background: var(--bg-head); font-weight: 600; }
li.sel { background: var(--row-sel); }
li.s-blocked { border-left: 3px solid var(--blocked); }
li.s-done .name { color: var(--fg-dim); text-decoration: line-through; }
li.crit .name { color: var(--bar-critical); }
.chk, .tog { flex: none; width: 28px; height: 28px; padding: 0; border-radius: 50%; margin-top: 1px; }
.tog { border: 0; background: none; font-size: 14px; border-radius: 6px; }
.chk.on { background: var(--ok); border-color: var(--ok); color: #fff; }
.main { flex: 1; min-width: 0; }
.name { font-size: 14px; word-break: break-word; }
.wbs { color: var(--fg-dim); font-weight: 400; margin-right: 2px; }
.meta { display: flex; flex-wrap: wrap; gap: 4px 10px; font-size: 12px; color: var(--fg-dim); margin-top: 2px; font-weight: 400; }
.st.in_progress { color: var(--accent); } .st.blocked, .note { color: var(--blocked); } .st.done { color: var(--ok); }
.lateb { color: var(--bar-critical); }
.bar { height: 3px; background: var(--chip); border-radius: 2px; margin-top: 5px; overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--accent); }
.empty { padding: 20px; text-align: center; }
.dim { color: var(--fg-dim); }
</style>
