<script setup lang="ts">
import UserPicker from './UserPicker.vue'
import { dfull } from '../lib/people'
import type { DirUser } from '../lib/types'

/** Verknüpfter Benutzer einer Ressource: gewählte Person als Chip (× löst), sonst Benutzersuche (ID, Name, E-Mail). */
defineProps<{ userId?: number | null; label?: string }>()
const emit = defineEmits<{ (e: 'pick', u: DirUser | null): void }>()
</script>

<template>
  <span v-if="userId" class="chip">{{ label || '#' + userId }} <button type="button" class="x" :title="$t('Verknüpfung lösen')" @click="emit('pick', null)">×</button></span>
  <UserPicker v-else :placeholder="$t('Benutzer suchen …')" @pick="u => emit('pick', u)" />
</template>

<style scoped>
.chip { display: inline-flex; align-items: center; gap: 6px; padding: 3px 4px 3px 10px; border: 1px solid var(--border); border-radius: 999px; background: var(--row-sel); }
.x { border: 0; background: none; cursor: pointer; font-size: 1.1em; line-height: 1; padding: 0 6px; color: var(--fg-dim); }
.x:hover { color: var(--fg); }
</style>
