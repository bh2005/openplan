<script setup lang="ts">
// Verwaltung → API-Zugänge: Zugangsschlüssel (Tokens) für Dienstkonten anlegen und widerrufen.
import { computed, onMounted, reactive, ref } from 'vue'
import { api, type ApiToken } from '../lib/api'
import type { Project } from '../lib/types'
import { toast } from '../lib/store'
import { t as tr, locale } from '../lib/i18n'

const items = ref<ApiToken[]>([])
const projects = ref<Project[]>([])
const f = reactive({ name: '', username: '', role: 'editor' as 'editor' | 'viewer', scope: 'read' as 'read' | 'write', expires_days: 365, project_ids: [] as number[], absences: false })
const fresh = ref<{ token: string; username: string } | null>(null)
const busy = ref(false)

async function load() {
  try { items.value = await api.apiTokens() } catch (e) { toast((e as Error).message, 'error') }
}
onMounted(async () => {
  await load()
  try { projects.value = await api.projects() } catch { /* Auswahl bleibt leer = alle */ }
})

const valid = computed(() => f.name.trim() && f.username.trim().length >= 2 && f.expires_days >= 1)
async function create() {
  busy.value = true
  try {
    const r = await api.createApiToken({ name: f.name.trim(), username: f.username.trim(), role: f.role, scope: f.scope, project_ids: f.project_ids, expires_days: f.expires_days, absences: f.absences })
    fresh.value = { token: r.token, username: r.username }
    f.name = ''
    toast(tr('Zugang erstellt'))
    await load()
  } catch (e) { toast((e as Error).message, 'error') } finally { busy.value = false }
}
async function revoke(t: ApiToken) {
  if (!confirm(tr('Zugang widerrufen? Systeme, die diesen Schlüssel nutzen, verlieren sofort den Zugriff.'))) return
  try { await api.revokeApiToken(t.id); toast(tr('Zugang widerrufen')); await load() } catch (e) { toast((e as Error).message, 'error') }
}
async function toggleAbsences(t: ApiToken) {
  try { await api.updateApiToken(t.id, { absences: !t.absences }); await load() } catch (e) { toast((e as Error).message, 'error') }
}
async function copy() {
  try { await navigator.clipboard.writeText(fresh.value!.token); toast(tr('Kopiert')) } catch { /* Markieren genügt */ }
}
const when = (s: string | null) => { if (!s) return tr('nie'); const d = new Date(s.replace(' ', 'T') + 'Z'); return isNaN(+d) ? s : d.toLocaleString(locale()) }
const pname = (id: number) => projects.value.find(p => p.id === id)?.name ?? '#' + id
const example = computed(() => `curl -H "Authorization: Bearer ${fresh.value?.token ?? 'op_…'}" ${location.origin}/api/projects`)
</script>

<template>
  <div class="tok">
    <p class="dim">{{ $t('Zugangsschlüssel für Skripte und andere Systeme (z. B. Ansible, Checkmk, ServiceNow). Jeder Schlüssel gehört zu einem Dienstkonto ohne Passwort-Anmeldung; es gelten dessen Rolle und Projektrechte. Das Dienstkonto muss im Projekt als Mitglied eingetragen sein. Der Schlüssel wird nur einmal angezeigt.') }}</p>

    <div v-if="fresh" class="fresh" role="status">
      <b>{{ $t('Neuer Schlüssel – jetzt kopieren, er wird nicht noch einmal angezeigt:') }}</b>
      <div class="keyrow"><input :value="fresh.token" readonly class="key" @focus="($event.target as HTMLInputElement).select()" /><button type="button" @click="copy">{{ $t('Kopieren') }}</button><button type="button" class="ghost" @click="fresh = null">×</button></div>
      <small class="dim">{{ $t('Verwendung:') }} <code>{{ example }}</code></small>
    </div>

    <fieldset>
      <legend>{{ $t('Neuen Zugang anlegen') }}</legend>
      <form class="form" @submit.prevent="create">
        <label>{{ $t('Name des Zugangs') }}<input v-model="f.name" maxlength="80" required placeholder="awx-rollout" /></label>
        <label>{{ $t('Dienstkonto (Name)') }}<input v-model="f.username" minlength="2" maxlength="64" required placeholder="svc-awx" autocomplete="off" /></label>
        <label>{{ $t('Umfang') }}
          <select v-model="f.scope"><option value="read">{{ $t('nur lesen') }}</option><option value="write">{{ $t('lesen und schreiben') }}</option></select>
        </label>
        <label>{{ $t('Rolle des Kontos') }}
          <select v-model="f.role"><option value="editor">editor</option><option value="viewer">viewer</option></select>
        </label>
        <label>{{ $t('Laufzeit (Tage)') }}<input v-model.number="f.expires_days" type="number" min="1" max="3650" required /></label>
        <label class="wide">{{ $t('Projekte (leer = alle des Kontos)') }}
          <select v-model="f.project_ids" multiple size="4"><option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option></select>
        </label>
        <label class="wide check"><input v-model="f.absences" type="checkbox" /> {{ $t('Darf die Abwesenheiten aller Benutzer lesen (nur Zeitraum und Art, ohne Notiz; „Krank“ erscheint als „Sonstiges“) – z. B. für Portwerk') }}</label>
        <button class="primary" :disabled="busy || !valid">{{ $t('Zugang erstellen') }}</button>
      </form>
    </fieldset>

    <table class="tbl">
      <thead><tr><th>{{ $t('Name des Zugangs') }}</th><th>{{ $t('Konto') }}</th><th>{{ $t('Umfang') }}</th><th>{{ $t('Projekte') }}</th><th>{{ $t('Abwesenheiten') }}</th><th>{{ $t('Läuft ab') }}</th><th>{{ $t('Zuletzt benutzt') }}</th><th /></tr></thead>
      <tbody>
        <tr v-for="t in items" :key="t.id" :class="{ gone: t.expired }">
          <td><b>{{ t.name }}</b><br /><code class="dim">{{ t.prefix }}…</code></td>
          <td>{{ t.username }} <small class="dim">({{ t.role }})</small></td>
          <td>{{ t.scope === 'write' ? $t('lesen und schreiben') : $t('nur lesen') }}</td>
          <td>{{ t.project_ids.length ? t.project_ids.map(pname).join(', ') : $t('alle') }}</td>
          <td><label class="check" :title="$t('Darf die Abwesenheiten aller Benutzer lesen')"><input type="checkbox" :checked="t.absences" @change="toggleAbsences(t)" /> {{ t.absences ? $t('lesen') : $t('nein') }}</label></td>
          <td>{{ when(t.expires_at) }} <span v-if="t.expired" class="bad">{{ $t('abgelaufen') }}</span></td>
          <td>{{ when(t.last_used_at) }}</td>
          <td class="act"><button type="button" class="danger" @click="revoke(t)">{{ $t('Widerrufen') }}</button></td>
        </tr>
        <tr v-if="!items.length"><td colspan="8" class="dim">{{ $t('Keine API-Zugänge angelegt.') }}</td></tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.tok { }
.dim { color: var(--fg-dim); } .bad { color: var(--bar-critical); font-weight: 600; }
.fresh { border: 1px solid var(--border); border-left: 4px solid #6d28d9; border-radius: 8px; padding: 10px 14px; margin: 10px 0; }
.keyrow { display: flex; gap: 8px; margin: 6px 0; } .key { flex: 1; font-family: monospace; }
fieldset { border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; margin: 12px 0; } legend { padding: 0 6px; color: var(--fg-dim); font-size: 13px; }
.form { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; align-items: end; }
.form label { display: flex; flex-direction: column; gap: 3px; font-size: 13px; } .form .wide { grid-column: 1 / -1; } .form label.check, label.check { flex-direction: row; align-items: center; gap: 6px; }
.tbl { border-collapse: collapse; width: 100%; margin: 10px 0; }
.tbl th, .tbl td { text-align: left; padding: 6px; border-bottom: 1px solid var(--border); vertical-align: top; } .act { text-align: right !important; }
tr.gone td { opacity: .55; }
</style>
