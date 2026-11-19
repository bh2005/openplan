<script setup lang="ts">
import { dfull, dname } from '../lib/people'
import { onBeforeUnmount, ref, watch } from 'vue'
import { api } from '../lib/api'
import type { DirUser } from '../lib/types'

/** Benutzersuche (ID, Name oder E-Mail) statt Auswahlliste – trägt auch bei vielen hundert Benutzern. */
const props = defineProps<{ exclude?: number[]; noViewers?: boolean; placeholder?: string }>()
const emit = defineEmits<{ (e: 'pick', u: DirUser): void }>()

const q = ref('')
const hits = ref<DirUser[]>([])
const busy = ref(false)
let timer: number | undefined

watch(q, v => {
  window.clearTimeout(timer)
  if (v.trim().length < 2) { hits.value = []; return }
  timer = window.setTimeout(async () => {
    busy.value = true
    try {
      hits.value = (await api.directory(v.trim(), 25))
        .filter(u => !props.exclude?.includes(u.id) && !(props.noViewers && u.role === 'viewer')).slice(0, 10)
    } catch { hits.value = [] } finally { busy.value = false }
  }, 250)
})
onBeforeUnmount(() => window.clearTimeout(timer))
function pick(u: DirUser) { emit('pick', u); q.value = ''; hits.value = [] }
</script>

<template>
  <div class="up">
    <input v-model="q" type="search" autocomplete="off" :placeholder="placeholder ?? $t('Benutzer suchen (ID, Name oder E-Mail) …')" :aria-label="$t('Benutzer suchen')" />
    <ul v-if="hits.length" class="hits">
      <li v-for="u in hits" :key="u.id"><button type="button" @click="pick(u)">{{ dfull(u) }} <small>{{ u.role }}</small></button></li>
    </ul>
    <small v-else-if="q.trim().length >= 2 && !busy" class="none">{{ $t('Keine Treffer.') }}</small>
  </div>
</template>

<style scoped>
.up { position: relative; flex: 1; min-width: 200px; }
.up input { width: 100%; }
.hits { position: absolute; left: 0; right: 0; top: 100%; z-index: 30; list-style: none; margin: 2px 0 0; padding: 4px; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; box-shadow: 0 6px 20px rgba(0, 0, 0, .25); max-height: 260px; overflow: auto; }
.hits button { display: flex; justify-content: space-between; width: 100%; text-align: left; border: 0; background: none; padding: 5px 8px; border-radius: 6px; }
.hits button:hover { background: var(--row-sel); }
.hits small, .none { color: var(--fg-dim); }
</style>
