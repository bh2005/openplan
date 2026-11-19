<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../lib/api'

const route = useRoute()
const router = useRouter()
const rep = ref<{ title: string; html: string } | null>(null)
const mine = ref<{ id: number; name: string; kind: string }[]>([])
const err = ref('')

async function load(id: number | null) {
  err.value = ''; rep.value = null
  try {
    mine.value = await api.myReports()
    const sid = id ?? mine.value[0]?.id
    if (sid) rep.value = await api.viewReport(sid)
  } catch (e) { err.value = (e as Error).message }
}
onMounted(() => load(route.params.id ? Number(route.params.id) : null))
const frame = (html: string) => `<!doctype html><meta charset="utf-8"><base target="_blank"><body style="margin:12px;background:#fff">${html}</body>`
</script>

<template>
  <div class="rv">
    <nav v-if="mine.length > 1" class="tabs">
      <button v-for="m in mine" :key="m.id" :class="{ on: Number($route.params.id) === m.id }" @click="router.push('/reports/' + m.id); load(m.id)">{{ m.name || (m.kind === 'portfolio' ? $t('Portfolio') : $t('Kostenstellen')) }}</button>
    </nav>
    <p v-if="err" class="err">{{ err }}</p>
    <p v-else-if="!rep && !mine.length" class="dim">{{ $t('Dir sind keine übergreifenden Reports zugeordnet. Ein Administrator richtet sie unter Verwaltung → Reports ein.') }}</p>
    <!-- Server-generiertes, escaptes HTML; zusätzlich in einer Sandbox ohne Skripte dargestellt -->
    <iframe v-if="rep" class="frame" sandbox="allow-popups allow-popups-to-escape-sandbox" :srcdoc="frame(rep.html)" :title="rep.title" />
  </div>
</template>

<style scoped>
.rv { padding: 14px 18px; display: flex; flex-direction: column; gap: 10px; height: 100%; min-height: 0; }
.tabs { display: flex; gap: 2px; border-bottom: 1px solid var(--border); flex-wrap: wrap; }
.tabs button { border: 0; border-bottom: 2px solid transparent; border-radius: 0; background: none; padding: 6px 12px; } .tabs button.on { border-bottom-color: var(--accent); font-weight: 600; }
.frame { flex: 1; min-height: 400px; width: 100%; max-width: 1100px; border: 1px solid var(--border); border-radius: 8px; background: #fff; }
.dim { color: var(--fg-dim); } .err { color: var(--bar-critical); }
</style>
