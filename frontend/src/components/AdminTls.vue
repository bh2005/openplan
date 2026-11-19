<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { api } from '../lib/api'
import { toast } from '../lib/store'
import type { TlsStatus } from '../lib/types'
import { t as tr, locale } from '../lib/i18n'

const st = ref<TlsStatus | null>(null)
const f = reactive({ directory_url: '', domains: '', email: '', ca_pem: '', auto_renew: true, renew_days: 30 })
const caUrl = ref('http://ca.corp.example/acme/ca-chain.pem')
const caInfo = ref<{ subject: string; fingerprint: string }[]>([])
const dirty = ref(false)
const busy = ref(false)
let timer: number | undefined

function fill(s: TlsStatus) {
  st.value = s
  if (!dirty.value) Object.assign(f, s.settings, { domains: s.settings.domains.join('\n') })
}
async function refresh() { try { fill(await api.tls()) } catch { /* ignorieren */ } }
function schedule() { window.clearInterval(timer); timer = window.setInterval(async () => { await refresh(); if (!st.value?.running) window.clearInterval(timer) }, 2000) }
onMounted(async () => { await refresh(); if (st.value?.running) schedule() })
onBeforeUnmount(() => window.clearInterval(timer))

const payload = () => ({ ...f, domains: f.domains.split(/[\n,;\s]+/).map(s => s.trim()).filter(Boolean) })
async function save(): Promise<boolean> {
  busy.value = true
  try { dirty.value = false; fill(await api.saveTls(payload())); toast(tr('Einstellungen gespeichert')); return true }
  catch (e) { dirty.value = true; toast((e as Error).message, 'error'); return false }
  finally { busy.value = false }
}
async function fetchCa() {
  try {
    const r = await api.fetchTlsCa(caUrl.value); f.ca_pem = r.pem; caInfo.value = r.certs; dirty.value = true
    toast(tr('CA-Kette geladen – Fingerabdrücke prüfen und speichern'))
  } catch (e) { toast((e as Error).message, 'error') }
}
async function issue() {
  if (dirty.value && !(await save())) return
  try { await api.issueTls(); await refresh(); schedule() } catch (e) { toast((e as Error).message, 'error') }
}
async function download() {
  try {
    const blob = await api.tlsCert()
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'openplan-fullchain.pem'; a.click(); URL.revokeObjectURL(a.href)
  } catch (e) { toast((e as Error).message, 'error') }
}
const cert = computed(() => st.value?.cert ?? null)
const when = (iso?: string) => (iso ? new Date(iso).toLocaleString(locale()) : '')
const level = computed(() => (!cert.value ? 'none' : cert.value.days_left < 7 ? 'bad' : cert.value.days_left < f.renew_days ? 'warn' : 'ok'))
</script>

<template>
  <div class="tls">
    <p class="dim">{{ $t('OpenPlan holt sich sein Server-Zertifikat selbst per ACME (z. B. von der internen step-ca) und erneuert es automatisch. Die CA prüft per HTTP-01.') }}</p>

    <section class="card" :class="'lv-' + level">
      <h3>{{ $t('Aktuelles Zertifikat') }}</h3>
      <template v-if="cert">
        <table class="kv">
          <tr><th>{{ $t('Domains') }}</th><td>{{ cert.san.join(', ') }}</td></tr>
          <tr><th>{{ $t('Aussteller') }}</th><td>{{ cert.issuer }}</td></tr>
          <tr><th>{{ $t('Gültig bis') }}</th><td>{{ when(cert.not_after) }} <span class="badge" :class="level">{{ $t('noch {1} Tage', { 1: cert.days_left }) }}</span></td></tr>
          <tr><th>{{ $t('Fingerabdruck') }}</th><td class="mono">{{ cert.fingerprint }}</td></tr>
          <tr><th>{{ $t('HTTPS-Listener') }}</th><td>{{ st?.serving ? $t('aktiv (lädt erneuerte Zertifikate automatisch)') : $t('nicht aktiv – TLS_PORT im Container setzen') }}</td></tr>
        </table>
      </template>
      <p v-else class="dim">{{ $t('Noch kein Zertifikat ausgestellt.') }}</p>
      <p v-if="st?.running" class="run">⏳ {{ st.message || $t('Anforderung läuft …') }}</p>
      <p v-else-if="st?.state?.ts" :class="st.state.ok ? 'okmsg' : 'badmsg'">{{ $t('Letzter Lauf ({1}, {2}): {3}', { 1: when(st.state.ts), 2: st.state.trigger, 3: st.state.message }) }}</p>
      <div class="actions">
        <button class="primary" :disabled="busy || st?.running" @click="issue">{{ cert ? $t('Jetzt erneuern') : $t('Zertifikat anfordern') }}</button>
        <button v-if="cert" @click="download">{{ $t('Zertifikatskette herunterladen') }}</button>
      </div>
    </section>

    <form class="cfg" @submit.prevent="save">
      <fieldset @input="dirty = true" @change="dirty = true">
        <legend>{{ $t('ACME-Einstellungen') }}</legend>
        <label>{{ $t('ACME-Directory-URL') }} <input v-model="f.directory_url" :placeholder="$t('https://ca.corp.example/acme/acme/directory')" /></label>
        <label>{{ $t('Domains (eine pro Zeile; die erste ist der Hauptname)') }}
          <textarea v-model="f.domains" rows="3" :placeholder="$t('openplan.corp.example')" spellcheck="false" /></label>
        <label>{{ $t('E-Mail für Ablaufwarnungen (optional)') }} <input v-model="f.email" type="email" :placeholder="$t('it-ops@corp.example')" /></label>
        <label>{{ $t('CA-Kette der ACME-Schnittstelle (PEM: Root + Intermediate)') }}
          <textarea v-model="f.ca_pem" rows="4" :placeholder="$t('-----BEGIN CERTIFICATE-----\n…\n-----END CERTIFICATE-----')" spellcheck="false" />
          <small class="dim">{{ $t('Für die interne step-ca') }} <b>{{ $t('immer nötig') }}</b>{{ $t(': Sie nutzt die eigene PKI „KS ROOT CA → KS Linux CA“, die dem Container nicht bekannt ist. Ohne Kette scheitert die Anmeldung mit „unable to get local issuer certificate“.') }}</small></label>
        <div class="inline">
          <label class="grow">{{ $t('CA-Kette von URL laden') }} <input v-model="caUrl" :placeholder="$t('http://…/ks-chain-ca.pem')" /></label>
          <button type="button" @click="fetchCa">{{ $t('Laden') }}</button>
        </div>
        <ul v-if="caInfo.length" class="cas"><li v-for="c in caInfo" :key="c.fingerprint"><b>{{ c.subject }}</b><br /><span class="mono">{{ $t('SHA-256 {1}', { 1: c.fingerprint }) }}</span></li></ul>
        <small v-if="caInfo.length && caUrl.startsWith('http://')" class="dim warn">{{ $t('⚠ Per http:// geladen: Fingerabdrücke bitte gegen die bekannten Werte der CA prüfen, bevor du speicherst.') }}</small>
        <div class="inline">
          <label class="chk"><input type="checkbox" v-model="f.auto_renew" /> {{ $t('automatisch erneuern') }}</label>
          <label class="chk">{{ $t('erneuern ab') }} <input v-model.number="f.renew_days" type="number" min="1" max="60" class="num" /> {{ $t('Tagen vor Ablauf') }}</label>
        </div>
      </fieldset>
      <div class="actions"><button class="primary" :disabled="busy">{{ $t('Speichern') }}</button><span v-if="dirty" class="dim">{{ $t('ungespeicherte Änderungen') }}</span></div>
    </form>

    <details class="hint">
      <summary>{{ $t('Voraussetzungen im Betrieb') }}</summary>
      <ul>
        <li><b>{{ $t('HTTP-01:') }}</b> {{ $t('Die CA ruft') }} <code>http://&lt;Domain&gt;:80/.well-known/acme-challenge/…</code> {{ $t('ab. Port 80 der Domain muss zur App (Container-Port 8080) weitergeleitet werden, z. B.') }} <code>80:8080</code> {{ $t('in der Compose-Datei oder per Reverse-Proxy.') }}</li>
        <li><b>{{ $t('HTTPS:') }}</b> {{ $t('Mit der Umgebungsvariable') }} <code>{{ $t('TLS_PORT=8443') }}</code> {{ $t('startet der Container zusätzlich einen HTTPS-Listener. Er lädt ein erneuertes Zertifikat innerhalb einer Minute ohne Neustart. Alternativ liegen Kette und Schlüssel in') }} <code>{{ $t('data/tls/') }}</code> {{ $t('für einen Reverse-Proxy.') }}</li>
        <li>{{ $t('Der private Schlüssel verlässt den Server nie; heruntergeladen wird nur die öffentliche Kette.') }}</li>
      </ul>
    </details>
  </div>
</template>

<style scoped>
.tls { display: flex; flex-direction: column; gap: 14px; }
.dim { color: var(--fg-dim); font-size: 12px; margin: 0; }
.card { border: 1px solid var(--border); border-left-width: 4px; border-radius: 8px; padding: 10px 14px 12px; background: var(--bg-head); }
.card.lv-ok { border-left-color: var(--ok); } .card.lv-warn { border-left-color: var(--blocked); } .card.lv-bad { border-left-color: var(--bar-critical); }
.card h3 { margin: 0 0 8px; font-size: 14px; }
.kv { border-collapse: collapse; font-size: 13px; width: 100%; } .kv th { text-align: left; color: var(--fg-dim); font-weight: 400; width: 130px; padding: 3px 8px 3px 0; vertical-align: top; } .kv td { padding: 3px 0; }
.mono { font-family: ui-monospace, monospace; font-size: 11px; word-break: break-all; }
.badge { margin-left: 6px; padding: 1px 8px; border-radius: 9px; font-size: 11px; color: #fff; background: var(--ok); } .badge.warn { background: var(--blocked); } .badge.bad { background: var(--bar-critical); }
.run { margin: 8px 0 0; } .okmsg { color: var(--ok); font-size: 13px; margin: 8px 0 0; } .badmsg { color: var(--bar-critical); font-size: 13px; margin: 8px 0 0; }
.actions { display: flex; gap: 8px; align-items: center; margin-top: 10px; flex-wrap: wrap; }
fieldset { border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px 12px; display: flex; flex-direction: column; gap: 8px; }
legend { font-weight: 600; padding: 0 6px; }
label { display: flex; flex-direction: column; gap: 3px; font-size: 13px; } label.chk { flex-direction: row; align-items: center; gap: 6px; }
textarea { font-family: ui-monospace, monospace; font-size: 12px; }
.inline { display: flex; gap: 14px; align-items: end; flex-wrap: wrap; } .num { width: 70px; } .grow { flex: 1; min-width: 220px; }
.cas { list-style: none; margin: 0; padding: 0; font-size: 12px; } .cas li { padding: 3px 0; } .warn { color: var(--blocked); }
input[type=checkbox] { width: auto; flex: none; }
.hint { font-size: 13px; color: var(--fg-dim); } .hint ul { margin: 6px 0 0; padding-left: 18px; } .hint li { margin: 4px 0; }
</style>
