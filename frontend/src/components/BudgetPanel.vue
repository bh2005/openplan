<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import BudgetActuals from './BudgetActuals.vue'
import BudgetMaster from './BudgetMaster.vue'
import BudgetOverview from './BudgetOverview.vue'
import BudgetPlan from './BudgetPlan.vue'
import { fin, loadBudget, loadFinance } from '../lib/finance'
import { state, ui } from '../lib/store'

const props = defineProps<{ pid: number }>()
const sub = ref<'overview' | 'plan' | 'actuals' | 'master'>('overview')
watch(sub, s => (ui.sub = s), { immediate: true })
const canEdit = computed(() => state.data?.cost_access === 'edit')
const revision = computed(() => state.data?.project.revision)

async function reload() {
  await Promise.all([loadFinance(props.pid), loadBudget(props.pid)])
}
onMounted(reload)
watch(revision, () => loadBudget(props.pid))   // Plan hat sich geändert -> Kennzahlen neu rechnen
</script>

<template>
  <div class="bp">
    <nav class="sub">
      <button :class="{ on: sub === 'overview' }" @click="sub = 'overview'">{{ $t('Übersicht') }}</button>
      <button :class="{ on: sub === 'plan' }" @click="sub = 'plan'">{{ $t('Plankosten') }}</button>
      <button :class="{ on: sub === 'actuals' }" @click="sub = 'actuals'">{{ $t('Ist-Kosten') }}</button>
      <button :class="{ on: sub === 'master' }" @click="sub = 'master'">{{ $t('Budget & Stammdaten') }}</button>
      <span class="spacer" />
      <span class="dim">{{ $t('Alle Beträge in EUR') }}</span>
    </nav>
    <div v-if="!fin.data || !fin.budget" class="dim pad">{{ $t('Lade …') }}</div>
    <template v-else>
      <BudgetOverview v-if="sub === 'overview'" :pid="pid" />
      <BudgetPlan v-else-if="sub === 'plan'" :pid="pid" :can-edit="canEdit" />
      <BudgetActuals v-else-if="sub === 'actuals'" :pid="pid" :can-edit="canEdit" />
      <BudgetMaster v-else :pid="pid" :can-edit="canEdit" />
    </template>
  </div>
</template>

<style scoped>
.bp { height: 100%; display: flex; flex-direction: column; min-height: 0; }
.sub { display: flex; align-items: center; gap: 4px; padding: 6px 14px; border-bottom: 1px solid var(--border); flex-wrap: wrap; }
.sub button { border: 0; background: none; border-bottom: 2px solid transparent; border-radius: 0; padding: 6px 10px; }
.sub button.on { border-bottom-color: var(--accent); font-weight: 600; }
.spacer { flex: 1; }
.dim { color: var(--fg-dim); font-size: 12px; }
.pad { padding: 20px; }
.bp > :deep(div) { flex: 1; min-height: 0; overflow: auto; }
</style>
