<script setup lang="ts">
import { dfull, dname } from '../lib/people'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../lib/api'
import { toast } from '../lib/store'
import type { ReportAdmin, ReportSub } from '../lib/types'
import { t as tr } from '../lib/i18n'

const router = useRouter()
const d = ref<ReportAdmin>({ subscriptions: [], owners: [], projects: [], known_codes: [] })
const users = ref<{ id: number; username: string; display_name?: string; email?: string }[]>([])
const WD = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
const blank = () => ({ id: 0, user_id: 0, kind: 'portfolio' as 'portfolio' | 'costcenter', name: '', project_ids: [] as number[], include_costs: false, weekday: 0, hour: 7, enabled: true })
const f = reactive(blank())
const editing = ref(false)
const owners = ref<{ code: string; name: string; user_id: number }[]>([])
const nowner = reactive({ code: '', name: '', user_id: 0 })

async function load() {
  try {
    d.value = await api.adminReports(); users.value = await api.users()
    owners.value = d.value.owners.map(o => ({ code: o.code, name: o.name, user_id: o.user_id }))
  } catch (e) { toast((e as Error).message, 'error') }
}
onMounted(load)
const uname = (id: number) => dname(users.value.find(u => u.id === id)) || '?'
const pname = (s: ReportSub) => (s.project_ids.length ? s.project_ids.map(i => d.value.projects.find(p => p.id === i)?.name ?? '#' + i).join(', ') : tr('alle Projekte'))
const plan = (s: ReportSub) => (s.weekday === -1 ? 'werktags' : WD[s.weekday]) + ' ab ' + String(s.hour).padStart(2, '0') + ':00'
const recipientNoMail = computed(() => users.value.find(u => u.id === f.user_id && !u.email))

function edit(s?: ReportSub) {
  Object.assign(f, s ? { id: s.id, user_id: s.user_id, kind: s.kind, name: s.name, project_ids: [...s.project_ids], include_costs: !!s.include_costs, weekday: s.weekday, hour: s.hour, enabled: !!s.enabled } : blank())
  editing.value = true
}
async function save() {
  if (!f.user_id) return toast(tr('Empfänger wählen'), 'error')
  const body = { user_id: f.user_id, kind: f.kind, name: f.name, project_ids: f.project_ids, include_costs: f.kind === 'portfolio' && f.include_costs, weekday: f.weekday, hour: f.hour, enabled: f.enabled }
  try { f.id ? await api.updateReportSub(f.id, body) : await api.createReportSub(body); editing.value = false; await load(); toast(tr('Report gespeichert')) }
  catch (e) { toast((e as Error).message, 'error') }
}
async function del(s: ReportSub) { if (confirm(tr('Report „{1}" für {2} löschen?', { 1: s.name || s.kind, 2: dname(s) }))) { await api.deleteReportSub(s.id).catch(e => toast(e.message, 'error')); await load() } }
async function sendNow(s: ReportSub) {
  try { const r = await api.sendReportSub(s.id); toast(tr('Report verschickt ({1} E-Mail{2}, Glocke: {3})', { 1: r.mails, 2: r.mails === 1 ? '' : 's', 3: r.notified })); await load() } catch (e) { toast((e as Error).message, 'error') }
}
function addOwner() {
  if (!nowner.code.trim() || !nowner.user_id) return toast(tr('Kostenstelle und Benutzer angeben'), 'error')
  owners.value.push({ code: nowner.code.trim(), name: nowner.name.trim(), user_id: nowner.user_id }); Object.assign(nowner, { code: '', name: '', user_id: 0 })
}
async function saveOwners() {
  try { d.value = await api.saveCostOwners(owners.value); toast(tr('Kostenstellenverantwortliche gespeichert')) } catch (e) { toast((e as Error).message, 'error') }
}
</script>

<template>
  <div class="rep">
    <p class="dim">{{ $t('Übergreifende Reports gehen an Vorgesetzte (Portfolio über mehrere Projekte) und Kostenstellenverantwortliche (Summen ihrer Kostenstelle je Projekt). Empfänger brauchen keinen Projektzugriff: Sie sehen nur den Report. Projektreports stellt der jeweilige Verantwortliche in den Projekteinstellungen ein.') }}</p>

    <h3>{{ $t('Reports') }}</h3>
    <table v-if="d.subscriptions.length" class="tbl">
      <thead><tr><th>{{ $t('Report') }}</th><th>{{ $t('Empfänger') }}</th><th>{{ $t('Umfang') }}</th><th>{{ $t('Zeitplan') }}</th><th /></tr></thead>
      <tbody>
        <tr v-for="s in d.subscriptions" :key="s.id" :class="{ off: !s.enabled }">
          <td><b>{{ s.name || (s.kind === 'portfolio' ? $t('Portfolio-Report') : $t('Kostenstellen-Report')) }}</b><br /><small>{{ s.kind === 'portfolio' ? $t('Portfolio') : $t('Kostenstellen') }}{{ s.include_costs ? ' · ' + $t('mit Kosten') : '' }}{{ s.enabled ? '' : ' · ' + $t('pausiert') }}</small></td>
          <td>{{ dname(s) }}<br /><small :class="{ warn: !s.email }">{{ s.email || $t('keine E-Mail-Adresse (nur Glocke)') }}</small></td>
          <td class="small">{{ s.kind === 'portfolio' ? pname(s) : $t('Kostenstellen des Empfängers') }}</td>
          <td class="small">{{ plan(s) }}<br /><span class="dim">{{ $t('zuletzt: {1}', { 1: s.last_sent || '–' }) }}</span></td>
          <td class="act"><button @click="router.push('/reports/' + s.id)">{{ $t('Ansehen') }}</button> <button @click="sendNow(s)">{{ $t('Jetzt senden') }}</button> <button @click="edit(s)">{{ $t('Bearbeiten') }}</button> <button class="danger" @click="del(s)">×</button></td>
        </tr>
      </tbody>
    </table>
    <p v-else class="dim">{{ $t('Noch keine übergreifenden Reports eingerichtet.') }}</p>
    <div v-if="!editing"><button class="primary" @click="edit()">{{ $t('+ Report einrichten') }}</button></div>

    <form v-else class="form" @submit.prevent="save">
      <fieldset>
        <legend>{{ f.id ? $t('Report bearbeiten') : $t('Neuer Report') }}</legend>
        <div class="inline">
          <label>{{ $t('Art') }} <select v-model="f.kind"><option value="portfolio">{{ $t('Portfolio (Vorgesetzte)') }}</option><option value="costcenter">{{ $t('Kostenstellen (Verantwortliche)') }}</option></select></label>
          <label class="grow">{{ $t('Empfänger') }} <select v-model.number="f.user_id"><option :value="0">{{ $t('– wählen –') }}</option><option v-for="u in users" :key="u.id" :value="u.id">{{ dfull(u) }}</option></select></label>
          <label class="grow">{{ $t('Titel') }} <input v-model="f.name" :placeholder="f.kind === 'portfolio' ? $t('z. B. Wochenbericht IT-Projekte') : $t('z. B. Kostenstellenbericht')" /></label>
        </div>
        <p v-if="recipientNoMail" class="warn">{{ $t('⚠ Für {1} ist keine E-Mail-Adresse hinterlegt – der Report erscheint nur in der Glocke und unter „Reports“.', { 1: dname(recipientNoMail) }) }}</p>
        <fieldset v-if="d.projects.length" class="sub">
          <legend>{{ $t('Projekte {1}', { 1: f.project_ids.length ? '' : '(alle)' }) }}</legend>
          <div class="plist"><label v-for="p in d.projects" :key="p.id" class="chk"><input type="checkbox" :value="p.id" v-model="f.project_ids" /> {{ p.name }}</label></div>
          <small class="dim">{{ $t('Nichts ausgewählt = alle Projekte (auch künftige).') }}</small>
        </fieldset>
        <label v-if="f.kind === 'portfolio'" class="chk"><input type="checkbox" v-model="f.include_costs" /> {{ $t('Kosten ausweisen (Budget, Ist, CPI) – nur für Empfänger, die Kosten sehen dürfen') }}</label>
        <p v-if="f.kind === 'costcenter'" class="dim">{{ $t('Die Kostenstellen des Empfängers legst du unten fest. Der Report zeigt je Projekt Budget, Plan, Ist und Rest dieser Kostenstellen – ohne Vorgangsdetails.') }}</p>
        <div class="inline">
          <label>{{ $t('Versand') }} <select v-model.number="f.weekday"><option :value="-1">{{ $t('werktags (Mo–Fr)') }}</option><option v-for="(n, i) in WD" :key="i" :value="i">{{ n }}</option></select></label>
          <label>{{ $t('ab Uhrzeit') }} <input v-model.number="f.hour" type="number" min="0" max="23" class="num" /></label>
          <label class="chk"><input type="checkbox" v-model="f.enabled" /> {{ $t('aktiv') }}</label>
        </div>
      </fieldset>
      <div class="actions"><button class="primary">{{ $t('Speichern') }}</button><button type="button" @click="editing = false">{{ $t('Abbrechen') }}</button></div>
    </form>

    <h3>{{ $t('Kostenstellenverantwortliche') }}</h3>
    <p class="dim">{{ $t('Je Kostenstellen-Code ein Verantwortlicher (führende Nullen sind egal). Der Code gilt projektübergreifend. Bekannte Codes aus den Projekten: {1}', { 1: d.known_codes.join(', ') || '–' }) }}</p>
    <table class="tbl">
      <thead><tr><th>{{ $t('Kostenstelle') }}</th><th>{{ $t('Bezeichnung') }}</th><th>{{ $t('Verantwortlicher') }}</th><th /></tr></thead>
      <tbody>
        <tr v-for="(o, i) in owners" :key="i">
          <td><input v-model="o.code" /></td><td><input v-model="o.name" /></td>
          <td><select v-model.number="o.user_id"><option v-for="u in users" :key="u.id" :value="u.id">{{ dfull(u) }}</option></select></td>
          <td class="act"><button class="danger" @click="owners.splice(i, 1)">×</button></td>
        </tr>
        <tr class="new">
          <td><input v-model="nowner.code" :placeholder="$t('Code')" list="knowncodes" /><datalist id="knowncodes"><option v-for="c in d.known_codes" :key="c" :value="c" /></datalist></td>
          <td><input v-model="nowner.name" :placeholder="$t('Bezeichnung')" /></td>
          <td><select v-model.number="nowner.user_id"><option :value="0">{{ $t('– Benutzer –') }}</option><option v-for="u in users" :key="u.id" :value="u.id">{{ dfull(u) }}</option></select></td>
          <td class="act"><button @click="addOwner">{{ $t('Hinzufügen') }}</button></td>
        </tr>
      </tbody>
    </table>
    <div class="actions"><button class="primary" @click="saveOwners">{{ $t('Zuordnung speichern') }}</button></div>
  </div>
</template>

<style scoped>
.rep { display: flex; flex-direction: column; gap: 10px; }
.dim { color: var(--fg-dim); font-size: 12px; margin: 0; } .warn { color: var(--blocked); font-size: 12px; margin: 0; } small { color: var(--fg-dim); font-size: 11px; } small.warn { color: var(--blocked); }
h3 { margin: 14px 0 0; }
.tbl { border-collapse: collapse; width: 100%; font-size: 13px; } .tbl th, .tbl td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border); vertical-align: top; }
.tbl input, .tbl select { width: 100%; } .tr.off, tr.off { opacity: .55; } .small { font-size: 12px; max-width: 220px; }
.act { white-space: nowrap; text-align: right !important; }
fieldset { border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px 12px; display: flex; flex-direction: column; gap: 8px; } legend { font-weight: 600; padding: 0 6px; }
fieldset.sub { padding: 6px 12px 8px; } .plist { display: flex; flex-wrap: wrap; gap: 4px 16px; max-height: 140px; overflow: auto; }
label { display: flex; flex-direction: column; gap: 3px; font-size: 13px; } label.chk { flex-direction: row; align-items: center; gap: 6px; }
.inline { display: flex; gap: 12px; align-items: end; flex-wrap: wrap; } .grow { flex: 1; min-width: 180px; } .num { width: 70px; }
input[type=checkbox] { width: auto; flex: none; }
.actions { display: flex; gap: 8px; margin-top: 6px; }
</style>
