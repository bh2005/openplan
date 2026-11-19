<script setup lang="ts">
import { dfull, dname } from '../lib/people'
import { computed, onMounted, reactive, ref } from 'vue'
import { api, setToken } from '../lib/api'
import { isAdmin, state, toast } from '../lib/store'
import AdminLdap from '../components/AdminLdap.vue'
import AdminTls from '../components/AdminTls.vue'
import AdminEnv from '../components/AdminEnv.vue'
import AdminTokens from '../components/AdminTokens.vue'
import AdminWebhooks from '../components/AdminWebhooks.vue'
import AdminHolidays from '../components/AdminHolidays.vue'
import AdminMail from '../components/AdminMail.vue'
import AdminReports from '../components/AdminReports.vue'
import AdminAudit from '../components/AdminAudit.vue'
import AdminBackup from '../components/AdminBackup.vue'
import AdminReminders from '../components/AdminReminders.vue'
import AdminChangelog from '../components/AdminChangelog.vue'
import { currentVersion } from '../content/changelog'
import { t } from '../lib/i18n'

const tab = ref<'users' | 'ldap' | 'mail' | 'reminders' | 'reports' | 'tls' | 'holidays' | 'env' | 'tokens' | 'webhooks' | 'backup' | 'audit' | 'changelog'>('users')

const users = ref<{ id: number; username: string; display_name?: string; role: string; created_at: string; auth_source: string; email?: string; see_all?: number | boolean }[]>([])
const uf = reactive({ q: '', role: '', source: '' })
const shownUsers = computed(() => {
  const words = uf.q.toLowerCase().split(/\s+/).filter(Boolean)
  return users.value.filter(u => {
    const hay = `${u.username} ${u.display_name ?? ''} ${u.email ?? ''} ${u.role} ${u.auth_source === 'ldap' ? 'active directory ad' : 'lokal'}`.toLowerCase()
    return words.every(w => hay.includes(w)) && (!uf.role || u.role === uf.role) && (!uf.source || u.auth_source === uf.source)
  })
})
const prof = reactive({ email: state.user?.email ?? '', notify: !!(state.user?.notify_email ?? true) })
async function saveProfile() {
  try { const r = await api.saveProfile({ email: prof.email, notify_email: prof.notify }); state.user = { ...state.user!, ...r }; toast(t('Gespeichert')) } catch (e) { toast((e as Error).message, 'error') }
}
async function setEmail(u: { id: number; email?: string }, ev: Event) {
  const v = (ev.target as HTMLInputElement).value.trim()
  try { await api.setUserEmail(u.id, v); u.email = v; toast(t('E-Mail gespeichert')) } catch (e) { toast((e as Error).message, 'error'); (ev.target as HTMLInputElement).value = u.email ?? '' }
}
const nu = reactive({ username: '', display_name: '', password: '', role: 'editor', source: 'local' })
async function seeAll(u: { id: number; see_all?: number | boolean }, ev: Event) {
  const on = (ev.target as HTMLInputElement).checked
  try { await api.setSeeAll(u.id, on); u.see_all = on ? 1 : 0; toast(t('Gespeichert')) } catch (e) { toast((e as Error).message, 'error'); (ev.target as HTMLInputElement).checked = !on }
}
async function endSessions(u: { id: number; username: string }) {
  if (!confirm(t('Alle Sitzungen von „{name}" beenden? Der Benutzer muss sich neu anmelden.', { name: u.username }))) return
  try { await api.endSessions(u.id); toast(t('Sitzungen beendet')) } catch (e) { toast((e as Error).message, 'error') }
}
async function setDisplay(u: { id: number; display_name?: string }, ev: Event) {
  const el = ev.target as HTMLInputElement
  const v = el.value.trim()
  try { await api.setUserDisplayName(u.id, v); u.display_name = v; toast(t('Gespeichert')) } catch (e) { toast((e as Error).message, 'error'); el.value = u.display_name ?? '' }
}
async function setUserPw(u: { id: number; username: string }) {
  const v = prompt(t('Neues Passwort für „{name}" (min. 8 Zeichen):', { name: u.username }))
  if (v === null) return
  try { await api.setUserPassword(u.id, v); toast(t('Passwort geändert')) } catch (e) { toast((e as Error).message, 'error') }
}
async function setRole(u: { id: number; role: string; see_all?: number | boolean }, ev: Event) {
  const sel = ev.target as HTMLSelectElement
  const old = u.role
  try { await api.setUserRole(u.id, sel.value); u.role = sel.value; u.see_all = 0; toast(t('Gespeichert')) } catch (e) { toast((e as Error).message, 'error'); sel.value = old }
}
const pw = reactive({ old: '', next: '' })

async function load() { if (isAdmin.value) users.value = await api.users().catch(() => []) }
onMounted(load)

async function add() {
  try { await api.createUser({ ...nu, role: nu.role === 'auditor' ? 'viewer' : nu.role, see_all: nu.role === 'auditor', password: nu.source === 'ldap' ? undefined : nu.password }); nu.username = ''; nu.display_name = ''; nu.password = ''; toast(t('Benutzer angelegt')); await load() }
  catch (e) { toast((e as Error).message, 'error') }
}
async function del(id: number, name: string) {
  if (!confirm(t('Benutzer „{name}" löschen?', { name }))) return
  try { await api.deleteUser(id); await load() } catch (e) { toast((e as Error).message, 'error') }
}
async function changePw() {
  try { const r = await api.changePassword(pw.old, pw.next); if (r.token) setToken(r.token); pw.old = pw.next = ''; toast(t('Passwort geändert')) }
  catch (e) { toast((e as Error).message, 'error') }
}
</script>

<template>
  <div class="adm">
    <h2>{{ $t('Mein Konto') }} – {{ dname(state.user) }}</h2>
    <form class="row" @submit.prevent="changePw">
      <input v-model="pw.old" type="password" :placeholder="$t('Altes Passwort')" autocomplete="current-password" required />
      <input v-model="pw.next" type="password" :placeholder="$t('Neues Passwort (min. 8 Zeichen)')" autocomplete="new-password" minlength="8" required />
      <button class="primary">{{ $t('Passwort ändern') }}</button>
    </form>
    <form class="row" @submit.prevent="saveProfile">
      <input v-model="prof.email" type="email" :placeholder="$t('Meine E-Mail-Adresse (für Benachrichtigungen)')" />
      <label class="chk"><input type="checkbox" v-model="prof.notify" /> {{ $t('E-Mails bei Zuteilungen und Reports erhalten') }}</label>
      <button class="primary">{{ $t('Speichern') }}</button>
    </form>

    <template v-if="isAdmin">
      <nav class="tabs">
        <button style="--tc: #2563eb" :class="{ on: tab === 'users' }" @click="tab = 'users'">{{ $t('Benutzer') }}</button>
        <button style="--tc: #7c3aed" :class="{ on: tab === 'ldap' }" @click="tab = 'ldap'">{{ $t('Anmeldung (Active Directory)') }}</button>
        <button style="--tc: #0891b2" :class="{ on: tab === 'mail' }" @click="tab = 'mail'">{{ $t('Benachrichtigung (E-Mail)') }}</button>
        <button style="--tc: #d97706" :class="{ on: tab === 'reminders' }" @click="tab = 'reminders'">{{ $t('Erinnerungen') }}</button>
        <button style="--tc: #059669" :class="{ on: tab === 'reports' }" @click="tab = 'reports'">{{ $t('Reports') }}</button>
        <button style="--tc: #dc2626" :class="{ on: tab === 'tls' }" @click="tab = 'tls'">{{ $t('Server-Zertifikat (ACME)') }}</button>
        <button style="--tc: #0369a1" :class="{ on: tab === 'holidays' }" @click="tab = 'holidays'">{{ $t('Feiertags-API') }}</button>
        <button style="--tc: #b45309" :class="{ on: tab === 'env' }" @click="tab = 'env'">{{ $t('Server-Umgebung (.env)') }}</button>
        <button style="--tc: #6d28d9" :class="{ on: tab === 'tokens' }" @click="tab = 'tokens'">{{ $t('API-Zugänge') }}</button>
        <button style="--tc: #0e7490" :class="{ on: tab === 'webhooks' }" @click="tab = 'webhooks'">{{ $t('Webhooks') }}</button>
        <button style="--tc: #4d7c0f" :class="{ on: tab === 'backup' }" @click="tab = 'backup'">{{ $t('Backup') }}</button>
        <button style="--tc: #db2777" :class="{ on: tab === 'audit' }" @click="tab = 'audit'">{{ $t('Audit-Log') }}</button>
        <button style="--tc: #0d9488" :class="{ on: tab === 'changelog' }" @click="tab = 'changelog'">{{ $t('Release Notes') }} <span class="ver">v{{ currentVersion }}</span></button>
        <a class="docs" href="/docs" target="_blank" rel="noopener" :title="$t('Swagger-Dokumentation der API in neuem Tab öffnen')">{{ $t('API-Doku') }} ↗</a>
      </nav>
      <AdminLdap v-if="tab === 'ldap'" />
      <AdminTls v-if="tab === 'tls'" />
      <AdminEnv v-if="tab === 'env'" />
      <AdminTokens v-if="tab === 'tokens'" />
      <AdminWebhooks v-if="tab === 'webhooks'" />
      <AdminHolidays v-if="tab === 'holidays'" />
      <AdminMail v-if="tab === 'mail'" />
      <AdminReports v-if="tab === 'reports'" />
      <AdminReminders v-if="tab === 'reminders'" />
      <AdminBackup v-if="tab === 'backup'" />
      <AdminAudit v-if="tab === 'audit'" />
      <AdminChangelog v-if="tab === 'changelog'" />
      <template v-if="tab === 'users'">
      <h2>{{ $t('Benutzer') }} <span class="cnt">{{ shownUsers.length }}{{ shownUsers.length !== users.length ? ' ' + $t('von') + ' ' + users.length : '' }}</span></h2>
      <div class="ufilter">
        <input v-model="uf.q" type="search" class="uq" :placeholder="$t('Benutzer suchen (ID, Name, E-Mail, Rolle) …')" :aria-label="$t('Benutzer suchen')" />
        <select v-model="uf.role"><option value="">{{ $t('alle Rollen') }}</option><option value="admin">admin</option><option value="editor">editor</option><option value="viewer">viewer</option></select>
        <select v-model="uf.source"><option value="">{{ $t('alle Anmeldearten') }}</option><option value="local">{{ $t('lokal') }}</option><option value="ldap">Active Directory</option></select>
        <button v-if="uf.q || uf.role || uf.source" class="ghost" @click="uf.q = ''; uf.role = ''; uf.source = ''">{{ $t('Zurücksetzen') }}</button>
      </div>
      <table>
        <thead><tr><th>{{ $t('Benutzer-ID') }}</th><th>{{ $t('Anzeigename') }}</th><th>{{ $t('Rolle') }}</th><th>{{ $t('Anmeldung') }}</th><th>{{ $t('E-Mail') }}</th><th :title="$t('Betrachter sehen alle Projekte lesend')">{{ $t('Alle Projekte') }}</th><th /></tr></thead>
        <tbody>
          <tr v-for="u in shownUsers" :key="u.id">
            <td>{{ u.username }}</td><td><input v-if="u.auth_source !== 'ldap'" :value="u.display_name" class="em" placeholder="–" :aria-label="$t('Anzeigename')" @change="setDisplay(u, $event)" /><span v-else :title="$t('Kommt aus dem Active Directory')">{{ u.display_name || '–' }}</span></td><td><select :value="u.role" :disabled="u.id === state.user?.id" :title="u.id === state.user?.id ? $t('Eigene Rolle nicht änderbar') : u.auth_source === 'ldap' ? $t('AD-Konten: Gruppen-Abgleich beim Login kann die Rolle zurücksetzen') : ''" @change="setRole(u, $event)"><option value="admin">admin</option><option value="editor">editor</option><option value="viewer">viewer</option></select></td><td>{{ u.auth_source === 'ldap' ? 'Active Directory' : $t('lokal') }}</td><td><input :value="u.email" type="email" placeholder="–" class="em" @change="setEmail(u, $event)" /></td>
            <td class="ctr"><input v-if="u.role === 'viewer'" type="checkbox" :checked="!!u.see_all" :title="$t('Betrachter sehen alle Projekte lesend')" @change="seeAll(u, $event)" /><span v-else-if="u.role === 'admin'" class="dim" :title="$t('Administratoren sehen alle Projekte')">✓</span></td>
            <td><button v-if="u.auth_source !== 'ldap' && u.id !== state.user?.id" class="ghost" @click="setUserPw(u)">{{ $t('Passwort setzen') }}</button> <button v-if="u.id !== state.user?.id" class="ghost" :title="$t('Alle Sitzungen dieses Benutzers beenden')" @click="endSessions(u)">{{ $t('Sitzungen beenden') }}</button> <button class="danger" :disabled="u.id === state.user?.id" @click="del(u.id, u.username)">{{ $t('Löschen') }}</button></td>
          </tr>
          <tr v-if="!shownUsers.length"><td colspan="7" class="nores">{{ $t('Keine Benutzer gefunden.') }}</td></tr>
        </tbody>
      </table>
      <form class="row" @submit.prevent="add">
        <input v-model="nu.username" :placeholder="$t('Benutzer-ID')" minlength="2" required />
        <input v-if="nu.source === 'local'" v-model="nu.display_name" :placeholder="$t('Anzeigename (optional)')" maxlength="120" />
        <select v-model="nu.source" :title="$t('Anmeldung: lokales Passwort oder Active Directory (LDAP)')"><option value="local">{{ $t('lokal') }}</option><option value="ldap">Active Directory</option></select>
        <input v-if="nu.source === 'local'" v-model="nu.password" type="password" :placeholder="$t('Passwort (min. 8 Zeichen)')" minlength="8" required autocomplete="new-password" />
        <select v-model="nu.role"><option value="viewer">{{ $t('viewer (lesen)') }}</option><option value="auditor">{{ $t('Betrachter (alle Projekte)') }}</option><option value="editor">editor</option><option value="admin">admin</option></select>
        <button class="primary">{{ $t('Anlegen') }}</button>
      </form>
      </template>
    </template>
  </div>
</template>

<style scoped>
.adm { padding: 18px 22px; overflow: auto; }
.tabs { display: flex; gap: 4px; border-bottom: 2px solid var(--border); margin: 6px 0 14px; flex-wrap: wrap; }
.tabs button { --tc: var(--accent); border: 1px solid color-mix(in srgb, var(--tc) 35%, transparent); border-top: 3px solid var(--tc); border-bottom: 0; border-radius: 6px 6px 0 0; background: color-mix(in srgb, var(--tc) 9%, transparent); padding: 7px 12px; }
.tabs button:hover:not(:disabled) { background: color-mix(in srgb, var(--tc) 18%, transparent); border-color: var(--tc); }
.tabs button.on { background: var(--tc); border-color: var(--tc); color: #fff; font-weight: 600; margin-bottom: -2px; }
.tabs .ver { font-size: 11px; opacity: .8; margin-left: 4px; }
.tabs .docs { margin-left: auto; align-self: center; font-size: 13px; padding: 4px 10px; border: 1px dashed var(--border); border-radius: 6px; color: var(--accent); text-decoration: none; }
.tabs .docs:hover { border-style: solid; }
.row { display: flex; gap: 8px; margin: 10px 0 24px; flex-wrap: wrap; }
.row input:not([type=checkbox]) { flex: 1; min-width: 150px; }
.em { width: 100%; min-width: 180px; }
@media (max-width: 700px) {
  .adm { padding: 12px; }
  .row input:not([type=checkbox]), .row select { min-width: 0; flex: 1 1 100%; }
  .ufilter .uq { min-width: 0; flex: 1 1 100%; max-width: none; }
  .tabs { flex-wrap: nowrap; overflow-x: auto; scrollbar-width: none; }
  .tabs button { white-space: nowrap; flex: none; }
  .adm table { display: block; overflow-x: auto; }
  .em { min-width: 140px; }
}
.ctr { text-align: center; }
.cnt { font-size: 12px; font-weight: 400; color: var(--fg-dim); margin-left: 6px; }
.ufilter { display: flex; gap: 8px; flex-wrap: wrap; margin: 4px 0 10px; } .uq { flex: 1; min-width: 220px; max-width: 420px; }
.nores { color: var(--fg-dim); text-align: center; padding: 14px; }
.chk { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border); }
</style>
