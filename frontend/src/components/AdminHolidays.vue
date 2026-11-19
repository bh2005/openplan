<script setup lang="ts">
// Verwaltung -> Feiertags-API: Quelle der gesetzlichen Feiertage (Import in den Projekteinstellungen).
import { onMounted, reactive, ref } from 'vue'
import { api, type HolidaysApiState, type HolidaysApiTest } from '../lib/api'
import { fmt } from '../lib/dates'
import { toast } from '../lib/store'
import { t as tr } from '../lib/i18n'

const st = ref<HolidaysApiState | null>(null)
const f = reactive({ url: '' })
const res = ref<HolidaysApiTest | null>(null)
const busy = ref(false)

function fill(s: HolidaysApiState) { st.value = s; f.url = s.url }
onMounted(async () => { try { fill(await api.holidaysApi()) } catch (e) { toast((e as Error).message, 'error') } })
async function save() { try { fill(await api.saveHolidaysApi(f.url)); res.value = null; toast(tr('Gespeichert')) } catch (e) { toast((e as Error).message, 'error') } }
async function test() {
  busy.value = true; res.value = null
  try { res.value = await api.testHolidaysApi(f.url) } catch (e) { toast((e as Error).message, 'error') } finally { busy.value = false }
}
async function clear() { if (confirm(tr('Zwischengespeicherte Feiertage löschen? Sie werden beim nächsten Import neu geladen.'))) { try { fill(await api.clearHolidaysCache()) } catch (e) { toast((e as Error).message, 'error') } } }
</script>

<template>
  <form class="hapi" @submit.prevent="save">
    <p class="dim">{{ $t('Quelle für „Feiertage laden“ in den Projekteinstellungen. Der Server ruft die URL je Jahr ab und hängt') }} <code>years=JJJJ</code> {{ $t('an (oder ersetzt den Platzhalter') }} <code>{year}</code>{{ $t('). Erwartet wird das JSON-Format von api-feiertage.de mit einem Flag je Bundesland. Leer lassen = Standard.') }}</p>
    <label>{{ $t('URL der Feiertags-API') }}
      <input v-model="f.url" type="url" maxlength="500" :placeholder="st?.default" spellcheck="false" />
    </label>
    <small class="dim">{{ $t('Standard:') }} <code>{{ st?.default }}</code> · {{ $t('Der Aufruf geht aus dem Container heraus; hinter einem Proxy müssen HTTPS_PROXY und das CA-Bundle gesetzt sein (siehe Server-Umgebung).') }}</small>
    <div class="actions">
      <button class="primary" type="submit">{{ $t('Speichern') }}</button>
      <button type="button" :disabled="busy" @click="test">{{ $t('Verbindung testen') }}</button>
    </div>
    <p v-if="res && res.ok" class="okmsg">✓ {{ $t('{1} Feiertage für {2} geladen', { 1: res.count, 2: res.year }) }} <small class="dim">({{ res.sample?.map(s => fmt(s.date) + ' ' + s.name).join(', ') }} …)</small></p>
    <p v-else-if="res" class="bad">✗ {{ res.message }}</p>
    <p v-if="res" class="dim"><small>{{ $t('Abgerufen:') }} <code>{{ res.called }}</code></small></p>

    <fieldset>
      <legend>{{ $t('Zwischenspeicher') }}</legend>
      <p v-if="!st?.cache.length" class="dim">{{ $t('Leer – die Feiertage werden beim ersten Import geladen und 30 Tage gemerkt.') }}</p>
      <ul v-else class="dim"><li v-for="c in st.cache" :key="c.year">{{ c.year }}: {{ $t('{1} Einträge', { 1: c.count }) }} · {{ $t('geladen am') }} {{ fmt(c.fetched) }}</li></ul>
      <button type="button" :disabled="!st?.cache.length" @click="clear">{{ $t('Zwischenspeicher leeren') }}</button>
    </fieldset>
  </form>
</template>

<style scoped>
.hapi { } .dim { color: var(--fg-dim); } .bad { color: var(--bar-critical); } .okmsg { color: var(--ok); }
label { display: block; margin: 10px 0 4px; font-size: 13px; color: var(--fg-dim); } label input { display: block; width: 100%; margin-top: 3px; color: var(--fg); }
.actions { display: flex; gap: 8px; margin: 12px 0; }
fieldset { border: 1px solid var(--border); border-radius: 8px; padding: 8px 14px; margin-top: 16px; } legend { padding: 0 6px; color: var(--fg-dim); font-size: 13px; }
</style>
