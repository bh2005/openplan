<script setup lang="ts">
// Externe Referenzen eines Vorgangs (ServiceNow-Change, AWX-Job, Checkmk-Host …): je System ein Eintrag, optional mit Link.
import { onMounted, reactive, ref } from 'vue'
import { api, type TaskRef } from '../lib/api'
import { state, toast } from '../lib/store'

const props = defineProps<{ taskId: number; projectId: number; canEdit: boolean }>()
const items = ref<TaskRef[]>([])
const f = reactive({ system: '', ref: '', url: '' })
const SYSTEMS = ['servicenow', 'awx', 'checkmk', 'jira', 'autopatch']

async function load() {
  try { items.value = await api.taskRefs(props.taskId) } catch (e) { toast((e as Error).message, 'error') }
}
onMounted(load)
async function refreshProject() { try { state.data = await api.project(props.projectId) } catch { /* Poll holt es nach */ } }

async function save() {
  if (!f.system.trim() || !f.ref.trim()) return
  try {
    await api.putTaskRef(props.taskId, f.system.trim().toLowerCase(), { ref: f.ref.trim(), url: f.url.trim() })
    f.system = ''; f.ref = ''; f.url = ''
    await load(); await refreshProject()
  } catch (e) { toast((e as Error).message, 'error') }
}
async function remove(r: TaskRef) {
  try { await api.deleteTaskRef(props.taskId, r.system); await load(); await refreshProject() } catch (e) { toast((e as Error).message, 'error') }
}
</script>

<template>
  <section v-if="items.length || canEdit" class="refs">
    <h4>{{ $t('Externe Referenzen') }}</h4>
    <ul v-if="items.length">
      <li v-for="r in items" :key="r.system">
        <span class="sys">{{ r.system }}</span>
        <a v-if="r.url" :href="r.url" target="_blank" rel="noopener noreferrer">{{ r.ref }}</a><span v-else>{{ r.ref }}</span>
        <button v-if="canEdit" type="button" class="ghost" :title="$t('Entfernen')" :aria-label="$t('Entfernen')" @click="remove(r)">×</button>
      </li>
    </ul>
    <p v-else class="dim">{{ $t('Keine Referenzen.') }}</p>
    <div v-if="canEdit" class="add">
      <input v-model="f.system" list="ref-systems" :placeholder="$t('System')" maxlength="32" :aria-label="$t('System')" />
      <datalist id="ref-systems"><option v-for="s in SYSTEMS" :key="s" :value="s" /></datalist>
      <input v-model="f.ref" :placeholder="$t('Referenz (z. B. CHG0012345)')" maxlength="200" :aria-label="$t('Referenz')" @keydown.enter.prevent="save" />
      <input v-model="f.url" type="url" :placeholder="$t('Link (optional)')" maxlength="500" :aria-label="$t('Link')" @keydown.enter.prevent="save" />
      <button type="button" :disabled="!f.system.trim() || !f.ref.trim()" @click="save">{{ $t('Hinzufügen') }}</button>
    </div>
  </section>
</template>

<style scoped>
.refs { margin: 12px 0; } h4 { margin: 0 0 6px; }
ul { list-style: none; padding: 0; margin: 0 0 6px; } li { display: flex; gap: 8px; align-items: center; padding: 2px 0; }
.sys { font-size: 12px; background: var(--border); border-radius: 10px; padding: 1px 8px; min-width: 70px; text-align: center; }
.dim { color: var(--fg-dim); margin: 0 0 6px; }
.add { display: grid; grid-template-columns: 110px 1fr 1.4fr auto; gap: 6px; } .add input { min-width: 0; }
@media (max-width: 640px) { .add { grid-template-columns: 1fr; } }
</style>
