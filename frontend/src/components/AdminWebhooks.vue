<script setup lang="ts">
// Verwaltung → Webhooks: Ereignisse (Status, Zuordnung, neues Gerät) signiert an Fremdsysteme senden; Zustellungen einsehen.
import { onMounted, reactive, ref } from 'vue'
import { api, type Webhook, type WebhookDelivery } from '../lib/api'
import type { Project } from '../lib/types'
import { toast } from '../lib/store'
import { t as tr, locale } from '../lib/i18n'

const items = ref<Webhook[]>([])
const events = ref<string[]>([])
const projects = ref<Project[]>([])
const secret = ref<{ name: string; value: string } | null>(null)
const open = ref<number | null>(null)
const deliveries = ref<WebhookDelivery[]>([])
const busy = ref(false)
const f = reactive({ name: '', url: '', events: [] as string[], project_id: null as number | null })

async function load() {
  try { const r = await api.webhooks(); items.value = r.items; events.value = r.events } catch (e) { toast((e as Error).message, 'error') }
}
onMounted(async () => { await load(); try { projects.value = await api.projects() } catch { /* leer = alle */ } })

async function create() {
  busy.value = true
  try {
    const r = await api.createWebhook({ name: f.name.trim(), url: f.url.trim(), events: f.events.length ? f.events : ['*'], project_id: f.project_id, enabled: true })
    secret.value = { name: r.name, value: r.secret! }
    f.name = ''; f.url = ''; f.events = []; f.project_id = null
    toast(tr('Webhook angelegt'))
    await load()
  } catch (e) { toast((e as Error).message, 'error') } finally { busy.value = false }
}
async function toggle(h: Webhook) {
  try { await api.updateWebhook(h.id, { name: h.name, url: h.url, events: h.events, project_id: h.project_id, enabled: !h.enabled }); await load() } catch (e) { toast((e as Error).message, 'error') }
}
async function rotate(h: Webhook) {
  if (!confirm(tr('Neues Geheimnis erzeugen? Der Empfänger muss es danach übernehmen, sonst schlägt die Signaturprüfung fehl.'))) return
  try {
    const r = await api.updateWebhook(h.id, { name: h.name, url: h.url, events: h.events, project_id: h.project_id, enabled: h.enabled, rotate_secret: true })
    secret.value = { name: r.name, value: r.secret! }
    await load()
  } catch (e) { toast((e as Error).message, 'error') }
}
async function remove(h: Webhook) {
  if (!confirm(tr('Webhook „{1}“ samt Zustellungen löschen?', { 1: h.name }))) return
  try { await api.deleteWebhook(h.id); if (open.value === h.id) open.value = null; await load() } catch (e) { toast((e as Error).message, 'error') }
}
async function test(h: Webhook) {
  try {
    const r = await api.testWebhook(h.id)
    toast(r.status === 'ok' ? tr('Test erfolgreich (HTTP {1})', { 1: r.code ?? '' }) : tr('Test fehlgeschlagen: {1}', { 1: r.error }), r.status === 'ok' ? undefined : 'error')
    if (open.value === h.id) await show(h)
    await load()
  } catch (e) { toast((e as Error).message, 'error') }
}
async function show(h: Webhook) {
  open.value = h.id
  try { deliveries.value = await api.webhookDeliveries(h.id) } catch (e) { toast((e as Error).message, 'error') }
}
async function copy() { try { await navigator.clipboard.writeText(secret.value!.value); toast(tr('Kopiert')) } catch { /* Markieren genügt */ } }
const when = (s: string | null) => { if (!s) return '–'; const d = new Date(s.replace(' ', 'T') + 'Z'); return isNaN(+d) ? s : d.toLocaleString(locale()) }
const pname = (id: number | null) => id == null ? tr('alle') : (projects.value.find(p => p.id === id)?.name ?? '#' + id)
</script>

<template>
  <div class="wh">
    <p class="dim">{{ $t('Sendet Ereignisse (Statuswechsel, Blockaden, Zuordnungen, neue Geräte) als JSON per HTTPS-POST an andere Systeme, z. B. Ansible/AWX, ServiceNow oder eine Middleware. Jede Zustellung ist mit dem Geheimnis des Webhooks signiert (Header X-OpenPlan-Signature, HMAC-SHA256 über den Body). Bei Fehlern wird bis zu fünfmal wiederholt (1, 5, 30, 120 Minuten).') }}</p>

    <div v-if="secret" class="fresh" role="status">
      <b>{{ $t('Geheimnis für „{1}“ – jetzt kopieren, es wird nicht noch einmal angezeigt:', { 1: secret.name }) }}</b>
      <div class="keyrow"><input :value="secret.value" readonly class="key" @focus="($event.target as HTMLInputElement).select()" /><button type="button" @click="copy">{{ $t('Kopieren') }}</button><button type="button" class="ghost" @click="secret = null">×</button></div>
    </div>

    <fieldset>
      <legend>{{ $t('Neuen Webhook anlegen') }}</legend>
      <form class="form" @submit.prevent="create">
        <label>{{ $t('Name') }}<input v-model="f.name" maxlength="80" required placeholder="awx-rollout" /></label>
        <label class="wide">{{ $t('Ziel-URL (https)') }}<input v-model="f.url" type="url" maxlength="500" required placeholder="https://awx.corp.example/api/v2/…" /></label>
        <label>{{ $t('Projekt') }}
          <select v-model="f.project_id"><option :value="null">{{ $t('alle') }}</option><option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option></select>
        </label>
        <label>{{ $t('Ereignisse (leer = alle)') }}
          <select v-model="f.events" multiple size="4"><option v-for="e in events" :key="e" :value="e">{{ e }}</option></select>
        </label>
        <button class="primary" :disabled="busy || !f.name.trim() || !f.url.trim()">{{ $t('Webhook anlegen') }}</button>
      </form>
    </fieldset>

    <table class="tbl">
      <thead><tr><th>{{ $t('Name') }}</th><th>{{ $t('Ziel') }}</th><th>{{ $t('Projekt') }}</th><th>{{ $t('Ereignisse') }}</th><th>{{ $t('Zustellung') }}</th><th /></tr></thead>
      <tbody>
        <template v-for="h in items" :key="h.id">
          <tr :class="{ gone: !h.enabled }">
            <td><b>{{ h.name }}</b><br /><small class="dim">{{ h.created_by }}</small></td>
            <td class="url">{{ h.url }}</td>
            <td>{{ pname(h.project_id) }}</td>
            <td>{{ h.events.join(', ') }}</td>
            <td><span v-if="h.pending" class="warn">{{ h.pending }} {{ $t('offen') }}</span> <span v-if="h.failed" class="bad">{{ h.failed }} {{ $t('fehlgeschlagen') }}</span>
              <span v-if="!h.pending && !h.failed" class="dim">{{ h.last_ok ? $t('zuletzt OK') + ' ' + when(h.last_ok) : '–' }}</span></td>
            <td class="act">
              <button type="button" @click="test(h)">{{ $t('Testen') }}</button>
              <button type="button" @click="open === h.id ? (open = null) : show(h)">{{ $t('Protokoll') }}</button>
              <button type="button" @click="toggle(h)">{{ h.enabled ? $t('Deaktivieren') : $t('Aktivieren') }}</button>
              <button type="button" @click="rotate(h)">{{ $t('Neues Geheimnis') }}</button>
              <button type="button" class="danger" @click="remove(h)">{{ $t('Löschen') }}</button>
            </td>
          </tr>
          <tr v-if="open === h.id"><td colspan="6">
            <table class="tbl sub">
              <thead><tr><th>#</th><th>{{ $t('Ereignis') }}</th><th>{{ $t('Status') }}</th><th>{{ $t('Versuche') }}</th><th>HTTP</th><th>{{ $t('Fehler') }}</th><th>{{ $t('Zeit') }}</th></tr></thead>
              <tbody>
                <tr v-for="d in deliveries" :key="d.id"><td>{{ d.id }}</td><td>{{ d.event }}</td><td :class="{ bad: d.status === 'failed' }">{{ d.status }}</td><td>{{ d.attempts }}</td><td>{{ d.last_code ?? '–' }}</td><td>{{ d.last_error }}</td><td>{{ when(d.ts) }}</td></tr>
                <tr v-if="!deliveries.length"><td colspan="7" class="dim">{{ $t('Noch keine Zustellungen.') }}</td></tr>
              </tbody>
            </table>
          </td></tr>
        </template>
        <tr v-if="!items.length"><td colspan="6" class="dim">{{ $t('Keine Webhooks eingerichtet.') }}</td></tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.wh { }
.dim { color: var(--fg-dim); } .bad { color: var(--bar-critical); font-weight: 600; } .warn { color: var(--blocked); font-weight: 600; }
.fresh { border: 1px solid var(--border); border-left: 4px solid #0e7490; border-radius: 8px; padding: 10px 14px; margin: 10px 0; }
.keyrow { display: flex; gap: 8px; margin: 6px 0; } .key { flex: 1; font-family: monospace; }
fieldset { border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; margin: 12px 0; } legend { padding: 0 6px; color: var(--fg-dim); font-size: 13px; }
.form { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; align-items: end; }
.form label { display: flex; flex-direction: column; gap: 3px; font-size: 13px; } .form .wide { grid-column: span 2; }
.tbl { border-collapse: collapse; width: 100%; margin: 10px 0; }
.tbl th, .tbl td { text-align: left; padding: 6px; border-bottom: 1px solid var(--border); vertical-align: top; }
.sub { font-size: 13px; margin: 0; } .url { font-family: monospace; font-size: 12px; word-break: break-all; }
.act { text-align: right !important; white-space: normal; } .act button { margin: 0 0 3px 4px; }
tr.gone td { opacity: .55; }
@media (max-width: 640px) { .form .wide { grid-column: auto; } }
</style>
