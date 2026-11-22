<script setup lang="ts">
import { dfull, dname } from '../lib/people'
import { computed, reactive, ref } from 'vue'
import { api, type WizardKind } from '../lib/api'
import { parseDate, todayIso } from '../lib/dates'
import { isAdmin, state, toast } from '../lib/store'
import { t as tr, weekdayLong, weekdayShort } from '../lib/i18n'
import type { DirUser } from '../lib/types'
import UserPicker from './UserPicker.vue'
import HolidayLoader from './HolidayLoader.vue'

/** Assistent „Neues Projekt“: Projektart → Grunddaten → Team → Berichte → Zusammenfassung. */
const emit = defineEmits<{ (e: 'close'): void; (e: 'quick'): void; (e: 'created', pid: number): void }>()

const KINDS: { kind: WizardKind; icon: string; title: string; text: string }[] = [
  { kind: 'empty', icon: '📄', title: 'Leeres Projekt', text: 'Nur Grunddaten und Team – die Struktur baust du selbst.' },
  { kind: 'network', icon: '🌐', title: 'Netzwerk-/Geräte-Rollout', text: 'Konzeption, Beschaffung, Rollout je Standort (danach Geräteliste importieren), Abschluss.' },
  { kind: 'migration', icon: '🖥️', title: 'Server-Migration auf neues Cluster', text: 'Analyse, Aufbau Zielumgebung, Pilot, vier Migrationswellen, Hypercare und Rückbau, mit Freigabe-Gates.' },
  { kind: 'release', icon: '🔄', title: 'Transition Release-Wechsel', text: 'Bewertung, Test und Abnahme, Schulung, Cutover, Hypercare und Übergabe in den Betrieb, mit drei Gates.' },
  { kind: 'patchpanel', icon: '🔌', title: 'Einbau Patchfelder / Verkabelung', text: 'Planung, Montage, Verlegen und Auflegen, Messung, Patchaufträge aus Portwerk, Abnahme.' },
]
const STEPS = ['Art', 'Grunddaten', 'Team', 'Berichte', 'Fertig']

const step = ref(0)
const busy = ref(false)
const f = reactive({
  kind: 'empty' as WizardKind, name: '', description: '', start: todayIso().split('-').reverse().join('.'),
  ownerId: state.user!.id, ownerName: dname(state.user!), days: [0, 1, 2, 3, 4], holidays: '', holidayState: '',
  members: [] as { user_id: number; username: string; role: 'editor' | 'viewer' }[],
  report_enabled: false, report_weekday: 0, report_hour: 7, report_to: 'owner' as 'owner' | 'members',
})

function pickOwner(u: DirUser) {
  f.ownerId = u.id; f.ownerName = dname(u)
  f.members = f.members.filter(m => m.user_id !== u.id)
}
function addMember(u: DirUser) {
  if (u.id !== f.ownerId && !f.members.some(m => m.user_id === u.id)) f.members.push({ user_id: u.id, username: dname(u), role: 'editor' })
}
const excluded = computed(() => [f.ownerId, ...f.members.map(m => m.user_id)])
const toggleDay = (d: number) => { f.days = f.days.includes(d) ? f.days.filter(x => x !== d) : [...f.days, d].sort() }

/** Eingaben des aktuellen Schritts prüfen; liefert die Fehlermeldung oder null. */
function check(s: number): string | null {
  if (s === 1) {
    if (!f.name.trim()) return tr('Bitte einen Projektnamen eingeben.')
    if (!parseDate(f.start)) return tr('Startdatum ungültig (TT.MM.JJJJ)')
    if (!f.days.length) return tr('Mindestens ein Arbeitstag nötig')
    for (const line of f.holidays.split(/[\n;,]/).map(x => x.trim()).filter(Boolean)) if (!parseDate(line)) return tr('Feiertag ungültig: {1}', { 1: line })
  }
  return null
}
function next() {
  const err = check(step.value)
  if (err) return toast(err, 'error')
  step.value++
}
function jump(i: number) {
  for (let s = 0; s < i; s++) { const err = check(s); if (err) { step.value = s; return toast(err, 'error') } }
  step.value = i
}

const kindTitle = computed(() => tr(KINDS.find(k => k.kind === f.kind)!.title))
const reportText = computed(() => (f.report_enabled
  ? tr('{1} um {2} Uhr an {3}', { 1: weekdayLong(f.report_weekday), 2: f.report_hour, 3: f.report_to === 'owner' ? tr('den Verantwortlichen') : tr('alle Mitglieder') })
  : tr('aus')))

async function create() {
  const err = check(1)
  if (err) { step.value = 1; return toast(err, 'error') }
  busy.value = true
  try {
    const r = await api.createProjectWizard({
      kind: f.kind, name: f.name.trim(), description: f.description, start_date: parseDate(f.start)!, work_days: f.days,
      holidays: f.holidays.split(/[\n;,]/).map(x => x.trim()).filter(Boolean).map(x => parseDate(x)!), holiday_state: f.holidayState,
      owner_id: isAdmin.value && f.ownerId !== state.user!.id ? f.ownerId : undefined,
      members: f.members.map(m => ({ user_id: m.user_id, role: m.role })),
      report_enabled: f.report_enabled, report_weekday: f.report_weekday, report_hour: f.report_hour, report_to: f.report_to,
    })
    toast(tr('Projekt „{1}“ angelegt', { 1: f.name.trim() }))
    emit('created', r.project.id)
  } catch (e) { toast((e as Error).message, 'error') } finally { busy.value = false }
}
</script>

<template>
  <div class="modal-back" @mousedown.self="emit('close')">
    <form class="modal wiz" @submit.prevent="step === STEPS.length - 1 ? create() : next()">
      <h3>{{ $t('Neues Projekt') }}</h3>
      <ol class="steps">
        <li v-for="(s, i) in STEPS" :key="s" :class="{ on: i === step, done: i < step }"><button type="button" @click="jump(i)"><b>{{ i + 1 }}</b><span>{{ $t(s) }}</span></button></li>
      </ol>

      <section v-if="step === 0">
        <p class="dim">{{ $t('Welche Art Projekt planst du? Die Projektart legt Phasen, Vorgänge und Meilensteine an – alles lässt sich danach ändern.') }}</p>
        <div class="kinds">
          <button v-for="k in KINDS" :key="k.kind" type="button" class="kind" :class="{ on: f.kind === k.kind }" @click="f.kind = k.kind">
            <span class="ic">{{ k.icon }}</span><b>{{ $t(k.title) }}</b><small>{{ $t(k.text) }}</small>
          </button>
        </div>
      </section>

      <section v-else-if="step === 1">
        <label>{{ $t('Name') }} <input v-model="f.name" maxlength="200" autofocus /></label>
        <label>{{ $t('Beschreibung') }} <textarea v-model="f.description" rows="2" /></label>
        <label>{{ $t('Projektstart') }} <input v-model="f.start" :placeholder="$t('TT.MM.JJJJ')" /></label>
        <label v-if="isAdmin">{{ $t('Verantwortlicher (Projektleiter)') }}
          <span class="curowner"><b>{{ f.ownerName }}</b></span>
          <UserPicker :no-viewers="true" :placeholder="$t('Anderen Verantwortlichen suchen …')" @pick="pickOwner" />
        </label>
        <p v-else class="dim">{{ $t('Du wirst Verantwortlicher (Projektleiter) dieses Projekts.') }}</p>
        <div class="days"><b>{{ $t('Arbeitstage') }}</b>
          <label v-for="d in [0, 1, 2, 3, 4, 5, 6]" :key="d" class="chk"><input type="checkbox" :checked="f.days.includes(d)" @change="toggleDay(d)" /> {{ weekdayShort(d) }}</label>
        </div>
        <label>{{ $t('Feiertage / freie Tage (ein Datum pro Zeile, TT.MM.JJJJ)') }} <textarea v-model="f.holidays" rows="2" /></label>
        <HolidayLoader v-model:state="f.holidayState" v-model:text="f.holidays" :start="f.start" />
      </section>

      <section v-else-if="step === 2">
        <p class="dim">{{ $t('Wer arbeitet mit? Editor = darf planen · Leser = nur ansehen. Wer später einem Vorgang zugeordnet wird, bekommt automatisch Zugriff auf seine Vorgänge.') }}</p>
        <div v-for="m in f.members" :key="m.user_id" class="mrow">
          <span>{{ m.username }}</span>
          <select v-model="m.role"><option value="editor">{{ $t('Editor') }}</option><option value="viewer">{{ $t('Leser') }}</option></select>
          <button type="button" class="danger" :aria-label="$t('Entfernen')" @click="f.members = f.members.filter(x => x !== m)">×</button>
        </div>
        <p v-if="!f.members.length" class="dim">{{ $t('Noch keine Mitglieder – du kannst sie auch später hinzufügen.') }}</p>
        <UserPicker :exclude="excluded" :placeholder="$t('Mitglied hinzufügen (Name oder E-Mail suchen) …')" @pick="addMember" />
      </section>

      <section v-else-if="step === 3">
        <p class="dim">{{ $t('Der Verantwortliche kann einen automatischen Projektreport (E-Mail und Glocke) einrichten: Fortschritt, überfällige und blockierte Vorgänge, anstehende Termine.') }}</p>
        <label class="chk"><input type="checkbox" v-model="f.report_enabled" /> {{ $t('Projektreport automatisch per E-Mail und Glocke versenden') }}</label>
        <div v-if="f.report_enabled" class="rep">
          <select v-model.number="f.report_weekday"><option v-for="d in [0, 1, 2, 3, 4, 5, 6]" :key="d" :value="d">{{ weekdayLong(d) }}</option></select>
          <span>{{ $t('ab') }}</span><input v-model.number="f.report_hour" type="number" min="0" max="23" class="num" /><span>{{ $t('Uhr an') }}</span>
          <select v-model="f.report_to"><option value="owner">{{ $t('den Verantwortlichen') }}</option><option value="members">{{ $t('alle Mitglieder') }}</option></select>
        </div>
        <p class="dim">{{ $t('Erinnerungen bei fälligen, überfälligen und blockierten Vorgängen laufen automatisch, sobald Vorgängen Personen zugeordnet sind.') }}</p>
      </section>

      <section v-else class="sum">
        <dl>
          <dt>{{ $t('Projektart') }}</dt><dd>{{ kindTitle }}</dd>
          <dt>{{ $t('Name') }}</dt><dd>{{ f.name }}</dd>
          <dt>{{ $t('Projektstart') }}</dt><dd>{{ f.start }}</dd>
          <dt>{{ $t('Verantwortlicher') }}</dt><dd>{{ f.ownerName }}</dd>
          <dt>{{ $t('Arbeitstage') }}</dt><dd>{{ f.days.map(weekdayShort).join(', ') }}</dd>
          <dt>{{ $t('Mitglieder') }}</dt><dd>{{ f.members.length ? f.members.map(m => m.username + ' (' + (m.role === 'editor' ? $t('Editor') : $t('Leser')) + ')').join(', ') : '–' }}</dd>
          <dt>{{ $t('Automatischer Report') }}</dt><dd>{{ reportText }}</dd>
        </dl>
        <p class="dim">{{ $t('Mit „Projekt anlegen“ entstehen Projekt, Struktur und Mitgliedschaften. Ressourcen, Budget und Basisplan richtest du danach im Projekt ein.') }}</p>
      </section>

      <div class="actions">
        <button type="button" class="ghost quick" @click="emit('quick')">{{ $t('Schnell anlegen (ohne Assistent)') }}</button>
        <span class="grow" />
        <button type="button" @click="step ? step-- : emit('close')">{{ step ? $t('Zurück') : $t('Abbrechen') }}</button>
        <button class="primary" type="submit" :disabled="busy">{{ step === STEPS.length - 1 ? $t('Projekt anlegen') : $t('Weiter') }}</button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.wiz { width: 640px; }
.steps { list-style: none; display: flex; gap: 4px; padding: 0; margin: 4px 0 14px; overflow-x: auto; scrollbar-width: none; }
.steps li { flex: 1 0 auto; }
.steps button { width: 100%; display: flex; align-items: center; gap: 6px; border: 0; border-bottom: 3px solid var(--border); border-radius: 0; background: none; padding: 6px 8px; color: var(--fg-dim); white-space: nowrap; }
.steps b { display: inline-flex; width: 20px; height: 20px; border-radius: 50%; background: var(--chip); align-items: center; justify-content: center; font-size: 11px; }
.steps li.done button { border-bottom-color: var(--ok); color: var(--fg); }
.steps li.on button { border-bottom-color: var(--accent); color: var(--fg); font-weight: 600; }
.steps li.on b { background: var(--accent); color: #fff; }
.dim { color: var(--fg-dim); font-size: 13px; margin: 0 0 10px; }
.kinds { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.kind { display: flex; flex-direction: column; align-items: flex-start; gap: 3px; text-align: left; padding: 10px 12px; border-radius: 10px; border: 2px solid var(--border); background: var(--bg-head); }
.kind.on { border-color: var(--accent); background: var(--row-sel); }
.kind .ic { font-size: 22px; }
.kind small { color: var(--fg-dim); font-weight: 400; }
.curowner { display: block; margin: 2px 0 4px; }
.days { display: flex; flex-wrap: wrap; gap: 6px 12px; align-items: center; margin: 4px 0 10px; }
.mrow { display: flex; gap: 8px; align-items: center; margin-bottom: 6px; } .mrow span { flex: 1; }
.rep { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 8px 0; } .num { width: 64px; }
.sum dl { display: grid; grid-template-columns: max-content 1fr; gap: 6px 14px; margin: 0 0 12px; } .sum dt { color: var(--fg-dim); } .sum dd { margin: 0; font-weight: 600; word-break: break-word; }
.actions { align-items: center; flex-wrap: wrap; } .grow { flex: 1; } .quick { font-size: 12px; color: var(--fg-dim); }
@media (max-width: 700px) { .kinds { grid-template-columns: 1fr; } .steps span { display: none; } .steps li.on span { display: inline; } }
</style>
