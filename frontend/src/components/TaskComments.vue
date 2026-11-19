<script setup lang="ts">
import { dfull, dname } from '../lib/people'
import { computed, onMounted, ref } from 'vue'
import { api } from '../lib/api'
import { toast } from '../lib/store'
import type { TaskComment } from '../lib/types'
import { t as tr, locale } from '../lib/i18n'

const props = defineProps<{ taskId: number; canEdit: boolean }>()
const items = ref<TaskComment[]>([])
const people = ref<string[]>([])
const text = ref('')
const area = ref<HTMLTextAreaElement | null>(null)
const caret = ref(0)
const busy = ref(false)

function apply(r: { items: TaskComment[]; people: string[] }) { items.value = r.items; people.value = r.people }
onMounted(async () => { try { apply(await api.comments(props.taskId)) } catch (e) { toast((e as Error).message, 'error') } })

// @-Vorschläge: Wort direkt vor dem Cursor, das mit @ beginnt
const token = computed(() => { const m = /(?:^|[\s(])@([A-Za-z0-9._-]*)$/.exec(text.value.slice(0, caret.value)); return m ? m[1] : null })
const suggestions = computed(() => (token.value === null ? [] : people.value.filter(p => p.toLowerCase().startsWith(token.value!.toLowerCase())).slice(0, 6)))
function track() { caret.value = area.value?.selectionStart ?? text.value.length }
function pick(name: string) {
  const before = text.value.slice(0, caret.value).replace(/@[A-Za-z0-9._-]*$/, '@' + name + ' ')
  text.value = before + text.value.slice(caret.value)
  const pos = before.length
  requestAnimationFrame(() => { area.value?.focus(); area.value?.setSelectionRange(pos, pos); caret.value = pos })
}
async function send() {
  const body = text.value.trim()
  if (!body || busy.value) return
  busy.value = true
  try { apply(await api.addComment(props.taskId, body)); text.value = ''; caret.value = 0 } catch (e) { toast((e as Error).message, 'error') } finally { busy.value = false }
}
async function del(c: TaskComment) {
  if (!confirm(tr('Kommentar löschen?'))) return
  try { apply(await api.deleteComment(c.id)) } catch (e) { toast((e as Error).message, 'error') }
}
// Text sicher darstellen (kein v-html): @Namen werden hervorgehoben
const lower = computed(() => new Set(people.value.map(p => p.toLowerCase())))
const parts = (b: string) => b.split(/(@[A-Za-z0-9][A-Za-z0-9._-]*)/).map(s => ({ s, m: s.startsWith('@') && (lower.value.has(s.slice(1).toLowerCase()) || lower.value.has(s.slice(1).replace(/[._-]+$/, '').toLowerCase())) }))
const when = (s: string) => { const d = new Date(s.replace(' ', 'T') + 'Z'); return isNaN(+d) ? s : d.toLocaleString(locale(), { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' }) }
</script>

<template>
  <section class="cm">
    <b>{{ $t('Kommentare') }} <span v-if="items.length" class="n">{{ items.length }}</span></b>
    <p v-if="!items.length" class="dim">{{ $t('Noch keine Kommentare.') }}</p>
    <ul v-else class="list">
      <li v-for="c in items" :key="c.id">
        <div class="hd"><b>{{ dname(c) }}</b><span class="dim">{{ when(c.created_at) }}</span>
          <button v-if="c.can_delete" type="button" class="x" :title="$t('Löschen')" @click="del(c)">×</button></div>
        <div class="bd"><template v-for="(p, i) in parts(c.body)" :key="i"><span v-if="p.m" class="men">{{ p.s }}</span><template v-else>{{ p.s }}</template></template></div>
      </li>
    </ul>
    <div v-if="canEdit" class="new">
      <textarea ref="area" v-model="text" rows="2" maxlength="4000" :placeholder="$t('Kommentar … mit @Name jemanden benachrichtigen (Strg+Enter sendet)')"
                @input="track" @click="track" @keyup="track" @keydown.ctrl.enter.prevent="send" />
      <ul v-if="suggestions.length" class="sug"><li v-for="p in suggestions" :key="p"><button type="button" @mousedown.prevent="pick(p)">@{{ p }}</button></li></ul>
      <div class="act"><button type="button" class="primary" :disabled="busy || !text.trim()" @click="send">{{ $t('Kommentieren') }}</button></div>
    </div>
  </section>
</template>

<style scoped>
.cm { border-top: 1px solid var(--border); margin-top: 10px; padding-top: 8px; display: flex; flex-direction: column; gap: 6px; position: relative; }
.n { font-weight: 400; font-size: 11px; color: var(--fg-dim); margin-left: 4px; } .dim { color: var(--fg-dim); font-size: 12px; margin: 0; }
.list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; max-height: 220px; overflow: auto; }
.list li { background: var(--bg-head); border-radius: 6px; padding: 6px 10px; } .hd { display: flex; gap: 8px; align-items: center; font-size: 12px; } .hd .x { margin-left: auto; background: none; border: 0; color: var(--fg-dim); cursor: pointer; padding: 0 4px; }
.bd { font-size: 13px; white-space: pre-wrap; word-break: break-word; margin-top: 2px; } .men { color: var(--accent); font-weight: 600; background: color-mix(in srgb, var(--accent) 12%, transparent); border-radius: 3px; padding: 0 2px; }
.new { position: relative; display: flex; flex-direction: column; gap: 4px; } .new textarea { width: 100%; resize: vertical; }
.act { display: flex; justify-content: flex-end; }
.sug { position: absolute; left: 8px; bottom: 56px; z-index: 5; list-style: none; margin: 0; padding: 2px; background: var(--bg); border: 1px solid var(--border); border-radius: 6px; box-shadow: 0 4px 14px rgba(0, 0, 0, .2); }
.sug button { display: block; width: 100%; text-align: left; background: none; border: 0; padding: 4px 10px; cursor: pointer; color: inherit; border-radius: 4px; } .sug button:hover { background: var(--row-sel); }
</style>
