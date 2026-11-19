<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api } from '../lib/api'
import { toast } from '../lib/store'
import type { MailSettings } from '../lib/types'
import { t as tr, locale } from '../lib/i18n'

const f = reactive({ enabled: false, host: '', port: 25, security: 'none' as 'none' | 'starttls' | 'ssl', username: '', password: '', clear_password: false,
  from_addr: '', from_name: 'OpenPlan', public_url: '' })
const meta = reactive({ password_set: false, state: {} as MailSettings['state'] })
const to = ref('')
const res = ref<{ ok: boolean; message: string } | null>(null)
const busy = ref(false)

function fill(s: MailSettings) {
  const { password_set, state, ...rest } = s
  Object.assign(f, rest, { password: '', clear_password: false }); meta.password_set = password_set; meta.state = state
}
onMounted(async () => { try { fill(await api.mailSettings()) } catch (e) { toast((e as Error).message, 'error') } })
const payload = () => ({ ...f, password: f.password || undefined })
async function save() {
  busy.value = true
  try { fill(await api.saveMailSettings(payload())); toast(tr('Mail-Einstellungen gespeichert')) } catch (e) { toast((e as Error).message, 'error') } finally { busy.value = false }
}
async function test() {
  busy.value = true; res.value = null
  try { res.value = await api.testMail(to.value) } catch (e) { toast((e as Error).message, 'error') } finally { busy.value = false }
}
const when = (iso?: string) => (iso ? new Date(iso).toLocaleString(locale()) : '')
</script>

<template>
  <form class="mail" @submit.prevent="save">
    <p class="dim">{{ $t('OpenPlan benachrichtigt Ressourcen bei Zuteilung eines Vorgangs oder Arbeitspakets und verschickt Reports. In der Glocke erscheinen die Nachrichten immer; E-Mails nur, wenn der Versand hier aktiv ist, der Benutzer eine Adresse hinterlegt hat und E-Mails nicht abgeschaltet hat.') }}</p>
    <label class="chk"><input type="checkbox" v-model="f.enabled" /> <b>{{ $t('E-Mail-Versand aktivieren') }}</b></label>
    <fieldset>
      <legend>{{ $t('SMTP-Server') }}</legend>
      <div class="inline">
        <label class="grow">{{ $t('Server') }} <input v-model="f.host" :placeholder="$t('smtp.corp.example')" /></label>
        <label>{{ $t('Port') }} <input v-model.number="f.port" type="number" min="1" max="65535" class="num" /></label>
        <label>{{ $t('Verschlüsselung') }} <select v-model="f.security"><option value="none">{{ $t('keine (intern, Port 25)') }}</option><option value="starttls">{{ $t('STARTTLS (587)') }}</option><option value="ssl">{{ $t('SSL/TLS (465)') }}</option></select></label>
      </div>
      <div class="inline">
        <label class="grow">{{ $t('Benutzer (optional)') }} <input v-model="f.username" autocomplete="off" /></label>
        <label class="grow">{{ $t('Passwort') }} <input v-model="f.password" type="password" autocomplete="new-password" :placeholder="meta.password_set ? $t('●●●●●● gespeichert – leer lassen zum Beibehalten') : ''" /></label>
      </div>
      <label v-if="meta.password_set" class="chk"><input type="checkbox" v-model="f.clear_password" /> {{ $t('gespeichertes Passwort entfernen') }}</label>
    </fieldset>
    <fieldset>
      <legend>{{ $t('Absender & Links') }}</legend>
      <div class="inline">
        <label class="grow">{{ $t('Absenderadresse') }} <input v-model="f.from_addr" type="email" :placeholder="$t('openplan@corp.example')" /></label>
        <label class="grow">{{ $t('Anzeigename') }} <input v-model="f.from_name" /></label>
      </div>
      <label>{{ $t('Öffentliche URL von OpenPlan') }} <input v-model="f.public_url" :placeholder="$t('https://openplan.corp.example')" />
        <small class="dim">{{ $t('Damit werden die Links in den E-Mails gebaut (z. B. …/project/12?task=34). Ohne Angabe wird die Adresse verwendet, unter der der Auslöser OpenPlan aufgerufen hat.') }}</small></label>
    </fieldset>
    <div class="actions"><button class="primary" :disabled="busy">{{ $t('Speichern') }}</button>
      <span v-if="meta.state.ts" :class="meta.state.ok ? 'okmsg' : 'badmsg'">{{ $t('Letzter Versand ({1}): {2}', { 1: when(meta.state.ts), 2: meta.state.message }) }}</span></div>
    <fieldset>
      <legend>{{ $t('Testmail') }}</legend>
      <div class="inline"><input v-model="to" type="email" :placeholder="$t('empfaenger@corp.example')" class="grow" /><button type="button" :disabled="busy || !to" @click="test">{{ $t('Senden') }}</button></div>
      <p v-if="res" :class="res.ok ? 'okmsg' : 'badmsg'">{{ res.ok ? '✓' : '✗' }} {{ res.message }}</p>
    </fieldset>
  </form>
</template>

<style scoped>
.mail { display: flex; flex-direction: column; gap: 12px; }
.dim { color: var(--fg-dim); font-size: 12px; margin: 0; }
fieldset { border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px 12px; display: flex; flex-direction: column; gap: 8px; } legend { font-weight: 600; padding: 0 6px; }
label { display: flex; flex-direction: column; gap: 3px; font-size: 13px; } label.chk { flex-direction: row; align-items: center; gap: 6px; }
.inline { display: flex; gap: 12px; align-items: end; flex-wrap: wrap; } .grow { flex: 1; min-width: 200px; } .num { width: 80px; }
input[type=checkbox] { width: auto; flex: none; }
.actions { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.okmsg { color: var(--ok); font-size: 13px; margin: 0; } .badmsg { color: var(--bar-critical); font-size: 13px; margin: 0; }
</style>
