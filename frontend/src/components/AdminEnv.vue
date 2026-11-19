<script setup lang="ts">
// Verwaltung → Server-Umgebung: .env des Containers bearbeiten und den Container neu starten.
import { computed, onMounted, reactive, ref } from 'vue'
import { api, type EnvState } from '../lib/api'
import { toast } from '../lib/store'
import { t as tr } from '../lib/i18n'

interface Row { key: string; value: string; secret: boolean; set: boolean; isNew: boolean; removed: boolean; touched: boolean; orig: string }
const st = ref<EnvState | null>(null)
const rows = reactive<Row[]>([])
const busy = ref(false)
const restarting = ref(false)
const SECRET = /PASSWORD|PASSWD|SECRET|TOKEN|PASSPHRASE|PRIVATE|_KEY$/i

function fill(s: EnvState) {
  st.value = s
  rows.splice(0, rows.length, ...s.entries.map(e => ({ key: e.key, value: e.value ?? '', secret: e.secret, set: e.set, isNew: false, removed: false, touched: false, orig: e.value ?? '' })))
}
onMounted(async () => { try { fill(await api.envState()) } catch (e) { toast((e as Error).message, 'error') } })

const dirty = computed(() => rows.some(r => r.isNew && r.key.trim() || r.removed || (!r.isNew && (r.secret ? r.touched && r.value !== '' : r.value !== r.orig))))
const known = computed(() => (st.value?.known ?? []).filter(k => !rows.some(r => r.key === k)))
function addRow() { rows.push({ key: '', value: '', secret: false, set: false, isNew: true, removed: false, touched: false, orig: '' }) }
function onKey(r: Row) { r.secret = SECRET.test(r.key) }

async function save() {
  const entries = rows.filter(r => !r.removed && (r.key.trim() || !r.isNew)).map(r => ({
    key: r.key.trim(),
    value: !r.isNew && r.secret && !(r.touched && r.value !== '') ? null : r.value,
  }))
  busy.value = true
  try {
    fill(await api.saveEnv(entries))
    toast(tr('Gespeichert – wirksam nach einem Neustart des Containers'))
  } catch (e) { toast((e as Error).message, 'error') } finally { busy.value = false }
}

async function restart() {
  if (!confirm(tr('Container jetzt neu starten? Die Anwendung ist dabei für etwa 10–30 Sekunden nicht erreichbar, angemeldete Benutzer müssen kurz warten.'))) return
  try { await api.restartServer() } catch (e) { return toast((e as Error).message, 'error') }
  restarting.value = true
  const t0 = Date.now()
  await new Promise(r => setTimeout(r, 3000))                      // erst abwarten, bis der alte Prozess beendet ist
  while (Date.now() - t0 < 180000) {
    try { const r = await fetch('/health', { cache: 'no-store' }); if (r.ok) { location.reload(); return } } catch { /* noch nicht erreichbar */ }
    await new Promise(r => setTimeout(r, 1500))
  }
  restarting.value = false
  toast(tr('Der Server antwortet nach 3 Minuten noch nicht – bitte Container und Log prüfen.'), 'error')
}
</script>

<template>
  <div class="env">
    <p v-if="!st" class="dim">{{ $t('Lade …') }}</p>
    <div v-else-if="!st.enabled" class="off">
      <b>{{ $t('Nicht aktiviert') }}</b>
      <p>{{ st.reason }}</p>
    </div>
    <template v-else>
      <p class="dim">{{ $t('Bearbeitet die Datei') }} <code>{{ st.path }}</code> {{ $t('(im Container; auf dem Host die .env neben der Compose-Datei). Passwörter und Schlüssel werden nie angezeigt – ein leeres Feld lässt den Wert unverändert, ein neuer Wert ersetzt ihn. Vor jeder Änderung wird die alte Datei gesichert:') }} <code>{{ st.backup_dir }}</code>.</p>
      <p v-if="!st.writable" class="bad">{{ $t('Die Datei ist schreibgeschützt – Speichern ist nicht möglich (Mount ohne Schreibrecht oder falscher Besitzer).') }}</p>
      <p v-if="st.pending_restart" class="pend">⚠ {{ $t('Die gespeicherte Datei unterscheidet sich vom Stand beim Start – die Änderungen wirken erst nach einem Neustart des Containers.') }}</p>

      <table class="tbl">
        <thead><tr><th>{{ $t('Variable') }}</th><th>{{ $t('Wert') }}</th><th /></tr></thead>
        <tbody>
          <tr v-for="(r, i) in rows" :key="i" :class="{ gone: r.removed }">
            <td><input v-model="r.key" :readonly="!r.isNew" list="env-known" class="k" :placeholder="$t('NAME')" :aria-label="$t('Variable')" @input="onKey(r)" /></td>
            <td>
              <input v-model="r.value" :type="r.secret ? 'password' : 'text'" autocomplete="off" spellcheck="false" :disabled="r.removed" :aria-label="$t('Wert')"
                     :placeholder="r.secret && !r.isNew ? (r.set ? $t('•••••• (gesetzt) – leer = unverändert') : $t('(leer) – neuen Wert eingeben')) : ''"
                     @input="r.touched = true" />
            </td>
            <td class="act"><button type="button" class="danger" :title="r.removed ? $t('Wiederherstellen') : $t('Entfernen')" @click="r.isNew ? rows.splice(i, 1) : (r.removed = !r.removed)">{{ r.removed ? '↶' : '×' }}</button></td>
          </tr>
          <tr v-if="!rows.length"><td colspan="3" class="dim">{{ $t('Keine Variablen in der Datei.') }}</td></tr>
        </tbody>
      </table>
      <datalist id="env-known"><option v-for="k in known" :key="k" :value="k" /></datalist>
      <div class="actions">
        <button type="button" @click="addRow">{{ $t('+ Variable') }}</button>
        <span class="spacer" />
        <button type="button" class="primary" :disabled="busy || !dirty || !st.writable" @click="save">{{ $t('Speichern') }}</button>
      </div>

      <fieldset>
        <legend>{{ $t('Container neu starten') }}</legend>
        <p class="dim">{{ $t('Die Anwendung beendet sich und Docker startet sie neu (Richtlinie „unless-stopped“); dabei wird die .env neu eingelesen. Nur nötig, wenn „Speichern“ eine Änderung gemeldet hat. Falls die Anwendung danach nicht startet: auf dem Host die gesicherte Datei zurückkopieren und') }} <code>docker compose up -d</code> {{ $t('ausführen.') }}</p>
        <button type="button" class="danger" :disabled="!st.restart_enabled || restarting" @click="restart">{{ $t('Container neu starten') }}</button>
        <small v-if="!st.restart_enabled" class="dim"> {{ $t('Nicht aktiviert (ALLOW_SELF_RESTART=1 und restart: unless-stopped in der Compose-Datei).') }}</small>
      </fieldset>
    </template>
    <div v-if="restarting" class="overlay" role="alert"><div class="box"><b>{{ $t('Server startet neu …') }}</b><p class="dim">{{ $t('Die Seite lädt automatisch neu, sobald die Anwendung wieder antwortet.') }}</p></div></div>
  </div>
</template>

<style scoped>
.env { }
.dim { color: var(--fg-dim); } .bad { color: var(--bar-critical); } .pend { color: var(--blocked); font-weight: 600; }
.off { border: 1px dashed var(--border); border-radius: 10px; padding: 12px 18px; }
.tbl { border-collapse: collapse; width: 100%; margin: 10px 0; }
.tbl th, .tbl td { text-align: left; padding: 4px 6px; border-bottom: 1px solid var(--border); } .tbl input { width: 100%; }
.k { font-family: monospace; min-width: 220px; } .act { width: 40px; text-align: right !important; }
tr.gone td { opacity: .45; } tr.gone input { text-decoration: line-through; }
.actions { display: flex; gap: 8px; margin: 8px 0 18px; } .spacer { flex: 1; }
fieldset { border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; } legend { padding: 0 6px; color: var(--fg-dim); font-size: 13px; }
.overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, .6); display: flex; align-items: center; justify-content: center; z-index: 100; }
.box { background: var(--bg); border: 1px solid var(--border); border-radius: 10px; padding: 18px 26px; text-align: center; }
</style>
