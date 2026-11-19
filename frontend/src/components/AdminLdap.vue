<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../lib/api'
import { toast } from '../lib/store'
import type { LdapSettings } from '../lib/types'
import { t as tr } from '../lib/i18n'

const f = reactive({
  enabled: false, url: '', base_dn: '', domain: '', bind_dn: '', bind_password: '', clear_bind_password: false,
  user_filter: '(&(objectClass=user)(sAMAccountName={username}))', ca_pem: '', required_group: '', admin_group: '', auditor_group: '',
  default_role: 'editor' as 'editor' | 'viewer', auto_create: true, nested_groups: true,
})
const meta = reactive({ bind_password_set: false, from_db: false })
const t = reactive({ username: '', password: '' })
const result = ref<{ ok: boolean; steps: { step: string; ok: boolean; detail: string }[] } | null>(null)
const busy = ref(false)
const unencrypted = computed(() => /(^|[\s,;])ldap:\/\//i.test(f.url))

function fill(s: LdapSettings) {
  const { bind_password_set, from_db, ...rest } = s
  Object.assign(f, rest, { bind_password: '', clear_bind_password: false })
  Object.assign(meta, { bind_password_set, from_db })
}
const payload = () => ({ ...f, bind_password: f.bind_password || undefined })
onMounted(async () => { try { fill(await api.ldapSettings()) } catch (e) { toast((e as Error).message, 'error') } })

async function save() {
  busy.value = true
  try { fill(await api.saveLdapSettings(payload())); toast(tr('AD-Einstellungen gespeichert')) }
  catch (e) { toast((e as Error).message, 'error') }
  finally { busy.value = false }
}
async function test() {
  busy.value = true; result.value = null
  try { result.value = await api.testLdap(payload(), t.username, t.password) }
  catch (e) { toast((e as Error).message, 'error') }
  finally { busy.value = false }
}
</script>

<template>
  <form class="ldap" @submit.prevent="save">
    <p class="dim">{{ $t('Mitarbeiter melden sich mit ihrem Windows-Benutzernamen und -Passwort an. Das Konto entsteht beim ersten Login. Der lokale Admin bleibt immer als Notzugang erhalten.') }}
      <span v-if="!meta.from_db">{{ $t('Es sind noch keine Werte gespeichert (Voreinstellung aus der Server-Umgebung).') }}</span></p>
    <label class="chk"><input type="checkbox" v-model="f.enabled" /> <b>{{ $t('Anmeldung über Active Directory aktivieren') }}</b></label>

    <fieldset>
      <legend>{{ $t('Server') }}</legend>
      <label>{{ $t('LDAP-URL') }} <input v-model="f.url" :placeholder="$t('ldaps://dc01.corp.example:636 ldaps://dc02.corp.example:636')" />
        <small class="dim">{{ $t('Mehrere Server mit Leerzeichen oder Komma trennen: Der nächste wird nur bei Verbindungsproblemen versucht (nie bei falschem Passwort).') }}</small></label>
      <p v-if="unencrypted" class="warn">{{ $t('⚠ ldap:// überträgt Passwörter unverschlüsselt – bitte ldaps:// verwenden.') }}</p>
      <label>{{ $t('Base-DN') }} <input v-model="f.base_dn" :placeholder="$t('DC=corp,DC=example')" /></label>
      <label>{{ $t('CA-Zertifikat für LDAPS (PEM, optional)') }} <textarea v-model="f.ca_pem" rows="4" :placeholder="$t('-----BEGIN CERTIFICATE-----\n…\n-----END CERTIFICATE-----')" spellcheck="false" /></label>
    </fieldset>

    <fieldset>
      <legend>{{ $t('Anmeldung prüfen') }}</legend>
      <p class="dim">{{ $t('Entweder direkt als') }} <code>{{ $t('benutzer@domain') }}</code> {{ $t('binden (Domain eintragen) oder über einen Service-Account den Benutzer suchen.') }}</p>
      <label>{{ $t('Domain (UPN-Suffix)') }} <input v-model="f.domain" :placeholder="$t('corp.example')" /></label>
      <label>{{ $t('Service-Account (Bind-DN, optional)') }} <input v-model="f.bind_dn" :placeholder="$t('CN=svc-openplan,OU=Service,DC=corp,DC=example')" autocomplete="off" /></label>
      <label>{{ $t('Service-Account-Passwort') }}
        <input v-model="f.bind_password" type="password" autocomplete="new-password" :placeholder="meta.bind_password_set ? $t('●●●●●● gespeichert – leer lassen zum Beibehalten') : ''" /></label>
      <label v-if="meta.bind_password_set" class="chk"><input type="checkbox" v-model="f.clear_bind_password" /> {{ $t('gespeichertes Passwort entfernen') }}</label>
      <label>{{ $t('Benutzerfilter') }} <input v-model="f.user_filter" /><small class="dim">{{ $t('{username} wird durch den Anmeldenamen ersetzt.') }}</small></label>
    </fieldset>

    <fieldset>
      <legend>{{ $t('Berechtigung') }}</legend>
      <label>{{ $t('Pflichtgruppe (DN, optional)') }} <input v-model="f.required_group" :placeholder="$t('CN=OpenPlan-Users,OU=Groups,DC=corp,DC=example')" /><small class="dim">{{ $t('Nur Mitglieder dürfen sich anmelden. Leer = jeder Benutzer im Verzeichnis.') }}</small></label>
      <label>{{ $t('Admin-Gruppe (DN, optional)') }} <input v-model="f.admin_group" :placeholder="$t('CN=OpenPlan-Admins,OU=Groups,DC=corp,DC=example')" /><small class="dim">{{ $t('Mitglieder werden OpenPlan-Administratoren (bei jedem Login abgeglichen).') }}</small></label>
      <label>{{ $t('Betrachter-Gruppe (DN, optional)') }} <input v-model="f.auditor_group" :placeholder="$t('CN=OpenPlan-Viewers,OU=Groups,DC=corp,DC=example')" /><small class="dim">{{ $t('Mitglieder sehen alle Projekte lesend (Rolle viewer + „Alle Projekte“), bei jedem Login abgeglichen. Die Admin-Gruppe hat Vorrang.') }}</small></label>
      <label class="chk"><input type="checkbox" v-model="f.nested_groups" /> {{ $t('verschachtelte Gruppen auflösen (AD)') }}</label>
      <div class="inline">
        <label>{{ $t('Rolle neuer Benutzer') }} <select v-model="f.default_role"><option value="editor">{{ $t('editor') }}</option><option value="viewer">{{ $t('viewer (nur lesen)') }}</option></select></label>
        <label class="chk"><input type="checkbox" v-model="f.auto_create" /> {{ $t('Konto beim ersten Login automatisch anlegen') }}</label>
      </div>
    </fieldset>

    <div class="actions"><button class="primary" :disabled="busy">{{ $t('Speichern') }}</button></div>

    <fieldset class="testbox">
      <legend>{{ $t('Verbindung testen') }}</legend>
      <p class="dim">{{ $t('Testet mit den Werten oben (auch ungespeichert). Ohne Benutzer wird nur der Service-Account geprüft; mit Benutzer der komplette Ablauf inkl. Gruppen.') }}</p>
      <div class="inline">
        <input v-model="t.username" :placeholder="$t('Test-Benutzer (optional)')" autocomplete="off" />
        <input v-model="t.password" type="password" :placeholder="$t('Passwort')" autocomplete="new-password" />
        <button type="button" :disabled="busy" @click="test">{{ $t('Testen') }}</button>
      </div>
      <ul v-if="result" class="steps">
        <li v-for="(s, i) in result.steps" :key="i" :class="s.ok ? 'ok' : 'bad'"><b>{{ s.ok ? '✓' : '✗' }} {{ s.step }}</b><span v-if="s.detail"> – {{ s.detail }}</span></li>
        <li :class="result.ok ? 'ok' : 'bad'"><b>{{ result.ok ? $t('Test erfolgreich') : $t('Test fehlgeschlagen') }}</b></li>
      </ul>
    </fieldset>
  </form>
</template>

<style scoped>
.ldap { display: flex; flex-direction: column; gap: 12px; }
fieldset { border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px 12px; display: flex; flex-direction: column; gap: 8px; }
legend { font-weight: 600; padding: 0 6px; }
label { display: flex; flex-direction: column; gap: 3px; font-size: 13px; } label.chk { flex-direction: row; align-items: center; gap: 6px; }
textarea { font-family: ui-monospace, monospace; font-size: 12px; }
.dim { color: var(--fg-dim); font-size: 12px; margin: 0; } .warn { color: var(--blocked); font-size: 12px; margin: 0; }
.inline { display: flex; gap: 14px; align-items: end; flex-wrap: wrap; } .inline input:not([type=checkbox]) { flex: 1; min-width: 160px; } .inline select { min-width: 150px; }
input[type=checkbox] { width: auto; flex: none; }
.actions { display: flex; gap: 8px; }
.steps { list-style: none; padding: 0; margin: 8px 0 0; font-size: 13px; } .steps li { padding: 2px 0; } .ok { color: var(--ok); } .bad { color: var(--bar-critical); }
</style>
