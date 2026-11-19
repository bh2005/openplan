<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api } from '../lib/api'
import { toast } from '../lib/store'
import type { BackupState } from '../lib/types'
import { t as tr, locale } from '../lib/i18n'

const st = ref<BackupState | null>(null)
const f = reactive({ enabled: false, hour: 2, keep: 14 })
const busy = ref(false)
const checks = reactive<Record<string, { ok: boolean; message: string; counts?: Record<string, number>; files?: number }>>({})

function fill(s: BackupState) { st.value = s; Object.assign(f, s.settings) }
onMounted(async () => { try { fill(await api.backupState()) } catch (e) { toast((e as Error).message, 'error') } })
async function saveSettings() { try { fill(await api.saveBackupSettings({ ...f })); toast(tr('Einstellungen gespeichert')) } catch (e) { toast((e as Error).message, 'error') } }
async function now() {
  busy.value = true
  try { const r = await api.createBackup(); fill(r); toast(tr('Sicherung erstellt: {1}', { 1: r.created?.name ?? '' })) } catch (e) { toast((e as Error).message, 'error') } finally { busy.value = false }
}
async function verify(name: string) { try { checks[name] = await api.verifyBackup(name) } catch (e) { toast((e as Error).message, 'error') } }
async function download(name: string) {
  try { const b = await api.downloadBackup(name); const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = name; a.click(); URL.revokeObjectURL(a.href) } catch (e) { toast((e as Error).message, 'error') }
}
async function del(name: string) { if (confirm(tr('Sicherung {1} löschen?', { 1: name }))) { try { fill(await api.deleteBackup(name)) } catch (e) { toast((e as Error).message, 'error') } } }
const size = (n: number) => (n > 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(n / 1024)) + ' KB')
const when = (s: string) => new Date(s).toLocaleString(locale())
</script>

<template>
  <div class="bk">
    <p class="dim">{{ $t('Sichert die Datenbank (konsistent, auch im laufenden Betrieb) und alle hochgeladenen Dokumente als') }} <code>{{ $t('.tar.gz') }}</code>{{ $t('. Passwörter/Schlüssel (JWT-Secret, TLS-Schlüssel) sind bewusst') }} <b>{{ $t('nicht') }}</b> {{ $t('enthalten. Ablageort:') }} <code>{{ st?.dir }}</code> {{ $t('– für echten Schutz auf ein anderes Laufwerk legen (') }}<code>{{ $t('BACKUP_DIR') }}</code>{{ $t(') und zusätzlich extern kopieren.') }}</p>
    <div class="actions"><button class="primary" :disabled="busy" @click="now">{{ $t('Jetzt sichern') }}</button></div>

    <fieldset>
      <legend>{{ $t('Automatische Sicherung') }}</legend>
      <div class="inline">
        <label class="chk"><input type="checkbox" v-model="f.enabled" /> {{ $t('täglich sichern ab') }}</label>
        <input v-model.number="f.hour" type="number" min="0" max="23" class="num" /> {{ $t('Uhr') }}
        <label>{{ $t('Letzte') }} <input v-model.number="f.keep" type="number" min="1" max="365" class="num" /> {{ $t('Sicherungen behalten') }}</label>
        <button @click="saveSettings">{{ $t('Speichern') }}</button>
      </div>
    </fieldset>

    <table class="tbl" v-if="st?.backups.length">
      <thead><tr><th>{{ $t('Sicherung') }}</th><th>{{ $t('Erstellt') }}</th><th>{{ $t('Größe') }}</th><th /></tr></thead>
      <tbody>
        <template v-for="b in st.backups" :key="b.name">
          <tr><td><code>{{ b.name }}</code></td><td>{{ when(b.created) }}</td><td>{{ size(b.size) }}</td>
            <td class="act"><button @click="verify(b.name)">{{ $t('Prüfen') }}</button> <button @click="download(b.name)">{{ $t('Herunterladen') }}</button> <button class="danger" @click="del(b.name)">×</button></td></tr>
          <tr v-if="checks[b.name]"><td colspan="4" :class="checks[b.name].ok ? 'ok' : 'bad'">
            {{ checks[b.name].ok ? '✓' : '✗' }} {{ checks[b.name].message }}<template v-if="checks[b.name].counts"> {{ $t('– {1} Benutzer, {2} Projekte, {3} Vorgänge, {4} Dateien', { 1: checks[b.name].counts!.users, 2: checks[b.name].counts!.projects, 3: checks[b.name].counts!.tasks, 4: checks[b.name].files }) }}</template></td></tr>
        </template>
      </tbody>
    </table>
    <p v-else class="dim">{{ $t('Noch keine Sicherung vorhanden.') }}</p>

    <details class="hint"><summary>{{ $t('Wiederherstellen') }}</summary>
      <p>{{ $t('Aus Sicherheitsgründen nur offline (Container stoppen), z. B.:') }}</p>
      <pre>docker compose stop openplan
docker compose run --rm openplan python backup.py verify /app/data/backups/&lt;datei&gt;
docker compose run --rm openplan python backup.py restore /app/data/backups/&lt;datei&gt; --yes
docker compose start openplan</pre>
      <p>{{ $t('Die bisherigen Daten bleiben als') }} <code>{{ $t('*.before-restore-…') }}</code> {{ $t('daneben liegen.') }}</p>
    </details>
  </div>
</template>

<style scoped>
.bk { display: flex; flex-direction: column; gap: 12px; } .dim { color: var(--fg-dim); font-size: 12px; margin: 0; }
fieldset { border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px 12px; } legend { font-weight: 600; padding: 0 6px; }
.inline { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; } .num { width: 70px; } label.chk { display: flex; align-items: center; gap: 6px; font-size: 13px; }
input[type=checkbox] { width: auto; }
.tbl { border-collapse: collapse; width: 100%; font-size: 13px; } .tbl th, .tbl td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border); } .act { white-space: nowrap; text-align: right !important; }
.ok { color: var(--ok); font-size: 12px; } .bad { color: var(--bar-critical); font-size: 12px; }
.hint { font-size: 13px; color: var(--fg-dim); } pre { background: var(--bg-head); padding: 8px 10px; border-radius: 6px; font-size: 12px; overflow: auto; }
</style>
