<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../lib/api'
import type { AppNotification } from '../lib/types'
import { locale } from '../lib/i18n'

const router = useRouter()
const open = ref(false)
const items = ref<AppNotification[]>([])
const unread = ref(0)
let timer: number | undefined

async function load() {
  try { const r = await api.notifications(); items.value = r.items; unread.value = r.unread } catch { /* offline/abgemeldet */ }
}
async function go(n: AppNotification) {
  open.value = false
  if (!n.read_at) { try { const r = await api.readNotification(n.id); items.value = r.items; unread.value = r.unread } catch { /* ignorieren */ } }
  if (n.link) router.push(n.link)
}
async function readAll() { try { const r = await api.readAllNotifications(); items.value = r.items; unread.value = r.unread } catch { /* ignorieren */ } }
const when = (s: string) => { const d = new Date(s.replace(' ', 'T') + 'Z'); return isNaN(+d) ? s : d.toLocaleString(locale(), { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) }
const ICONS: Record<string, string> = { assigned: '📌', unassigned: '↩', report: '📊', mention: '💬', comment: '💬', due: '⏰', overdue: '⚠️', escalation: '🚨', blocked: '⛔' }
const icon = (k: string) => ICONS[k] ?? '🔔'
function away(e: MouseEvent) { if (!(e.target as HTMLElement).closest('.bell')) open.value = false }
onMounted(() => { load(); timer = window.setInterval(() => { if (!document.hidden) load() }, 30000); document.addEventListener('click', away) })
onBeforeUnmount(() => { window.clearInterval(timer); document.removeEventListener('click', away) })
</script>

<template>
  <div class="bell">
    <button class="ghost bellbtn" :title="unread ? $t('{1} ungelesene Benachrichtigung(en)', { 1: unread }) : $t('Benachrichtigungen')" @click="open = !open; if (open) load()">
      🔔<span v-if="unread" class="cnt">{{ unread > 99 ? '99+' : unread }}</span>
    </button>
    <div v-if="open" class="drop">
      <div class="dh"><b>{{ $t('Benachrichtigungen') }}</b><button v-if="unread" class="lnk" @click="readAll">{{ $t('Alle gelesen') }}</button></div>
      <div v-if="!items.length" class="empty">{{ $t('Keine Benachrichtigungen.') }}</div>
      <button v-for="n in items" :key="n.id" class="item" :class="{ unread: !n.read_at }" @click="go(n)">
        <span class="ic">{{ icon(n.kind) }}</span>
        <span class="tx"><b>{{ n.title }}</b><small v-if="n.project_name">{{ n.project_name }}</small><small>{{ when(n.created_at) }}</small></span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.bell { position: relative; }
.bellbtn { position: relative; padding: 2px 8px; font-size: 16px; }
.cnt { position: absolute; top: -4px; right: -4px; min-width: 16px; height: 16px; padding: 0 4px; border-radius: 8px; background: var(--bar-critical); color: #fff; font-size: 10px; line-height: 16px; text-align: center; }
.drop { position: absolute; right: 0; top: 36px; width: 360px; max-width: 92vw; max-height: 70vh; overflow: auto; background: var(--bg); color: var(--fg); border: 1px solid var(--border); border-radius: 8px; box-shadow: 0 8px 24px rgba(0, 0, 0, .25); z-index: 60; }
.dh { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; border-bottom: 1px solid var(--border); position: sticky; top: 0; background: var(--bg); }
.lnk { background: none; border: 0; color: var(--accent); cursor: pointer; font-size: 12px; padding: 0; }
.empty { padding: 18px; color: var(--fg-dim); text-align: center; font-size: 13px; }
.item { display: flex; gap: 8px; width: 100%; text-align: left; background: none; border: 0; border-bottom: 1px solid var(--border); border-radius: 0; padding: 8px 12px; cursor: pointer; color: inherit; }
.item:hover { background: var(--row-sel); } .item.unread { background: color-mix(in srgb, var(--accent) 10%, transparent); }
.item.unread b::before { content: '● '; color: var(--accent); font-size: 10px; }
.tx { display: flex; flex-direction: column; gap: 1px; min-width: 0; font-size: 13px; } .tx small { color: var(--fg-dim); font-size: 11px; }
</style>
