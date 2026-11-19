<script setup lang="ts">
// Organigramme aller sichtbaren Projekte (für Vorgesetzte): Projekt wählen, anzeigen, als PNG/SVG/PDF exportieren.
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../lib/api'
import type { Project, ProjectData } from '../lib/types'
import { state, toast } from '../lib/store'
import OrgChart from '../components/OrgChart.vue'

const route = useRoute()
const router = useRouter()
const projects = ref<Project[]>([])
const pid = ref(0)
const data = ref<ProjectData | null>(null)
const loading = ref(true)
const editable = computed(() => ['edit', 'owner'].includes(data.value?.access ?? ''))
async function move(rid: number, parent: number | null) {
  try { data.value = await api.setReportsTo(rid, parent) } catch (e) { toast((e as Error).message, 'error') }
}

async function load() {
  if (!pid.value) { data.value = null; return }
  try { data.value = await api.project(pid.value) } catch (e) { data.value = null; toast((e as Error).message, 'error') }
}
onMounted(async () => {
  state.data = null
  try {
    projects.value = (await api.projects()).slice().sort((a, b) => a.name.localeCompare(b.name))
    const want = Number(route.query.p)
    pid.value = projects.value.some(p => p.id === want) ? want : projects.value[0]?.id ?? 0
  } catch (e) { toast((e as Error).message, 'error') }
  loading.value = false
})
watch(pid, () => { router.replace({ query: pid.value ? { p: String(pid.value) } : {} }); load() })
</script>

<template>
  <div class="ov">
    <div class="hd">
      <h2>{{ $t('Organigramm') }}</h2>
      <select v-model.number="pid" :aria-label="$t('Projekt')"><option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option></select>
    </div>
    <p v-if="!loading && !projects.length" class="dim">{{ $t('Keine Projekte sichtbar.') }}</p>
    <OrgChart v-if="data" :data="data" :editable="editable" @move="move" />
  </div>
</template>

<style scoped>
.ov { padding: 16px; width: 100%; max-width: 1400px; margin: 0 auto; box-sizing: border-box; overflow: auto; min-width: 0; }   /* main schneidet ab: die Seite scrollt selbst */
.hd { display: flex; gap: 14px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; min-width: 0; }
.hd h2 { margin: 0; }
.hd select { max-width: 100%; min-width: 0; }
.dim { color: var(--fg-dim); }
</style>
