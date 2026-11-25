<script setup lang="ts">
import { dfull, dname } from './lib/people'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api } from './lib/api'
import { useRouter } from 'vue-router'
import HelpPanel from './components/HelpPanel.vue'
import NotificationBell from './components/NotificationBell.vue'
import { isAdmin, logout, savePrefs, state, ui } from './lib/store'
import { lang, t, theme, type Theme } from './lib/i18n'

const nextTheme: Record<Theme, Theme> = { auto: 'light', light: 'dark', dark: 'auto' }
const themeIcon = { auto: '◐', light: '☀', dark: '☾' }
const themeTitle = () => ({ auto: t('Darstellung: automatisch (System)'), light: t('Darstellung: hell'), dark: t('Darstellung: dunkel') })[theme.value]

const router = useRouter()
const hasReports = ref(false)
watch(() => state.user?.id, async id => { hasReports.value = false; if (id) { try { hasReports.value = (await api.myReports()).length > 0 } catch { /* ignorieren */ } } }, { immediate: true })
const menuOpen = ref(false)
const ddOpen = ref(false)                                     // Untermenü „Übersicht“ (Dashboard, Wer arbeitet woran, Organigramm)
const overviewActive = computed(() => ['/dashboard', '/overview', '/org'].includes(router.currentRoute.value.path))
const closeDd = () => { ddOpen.value = false }
watch(() => router.currentRoute.value.fullPath, closeDd)
watch(() => router.currentRoute.value.fullPath, () => { menuOpen.value = false })
const todo = ref({ open: 0, late: 0 })
async function loadTodo() {
  if (!state.user) return
  try { const r = await api.myTasks(); todo.value = { open: r.items.length, late: r.items.filter(i => i.bucket === 'overdue').length } } catch { /* offline */ }
}
let todoTimer: number | undefined
watch(() => state.user?.id, () => loadTodo(), { immediate: true })
watch(() => router.currentRoute.value.fullPath, p => { if (p === '/todo') window.setTimeout(loadTodo, 1500) })
onMounted(() => { todoTimer = window.setInterval(() => { if (!document.hidden) loadTodo() }, 120000) })
onBeforeUnmount(() => window.clearInterval(todoTimer))
function out() { logout(); router.push('/login') }

function onKey(e: KeyboardEvent) {
  const el = e.target as HTMLElement | null
  const typing = !!el && (['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName) || el.isContentEditable)
  if (e.key === 'Escape') ddOpen.value = false
  if (e.key === 'F1') { e.preventDefault(); ui.helpOpen = !ui.helpOpen }
  else if (e.key === '?' && !typing && !e.ctrlKey && !e.metaKey && !e.altKey) { e.preventDefault(); ui.helpOpen = !ui.helpOpen }
}
onMounted(() => { document.addEventListener('keydown', onKey); document.addEventListener('click', closeDd) })
onBeforeUnmount(() => { document.removeEventListener('keydown', onKey); document.removeEventListener('click', closeDd) })
</script>

<template>
  <div class="app">
    <div v-if="!state.online" class="offline">{{ $t('Offline – Änderungen sind nicht möglich, gespeicherte Daten werden angezeigt.') }}</div>
    <header v-if="state.user" class="top no-print">
      <router-link to="/" class="brand"><img src="/icon.svg" alt="" width="22" height="22" /> OpenPlan <span class="motto desk" title="Hessisch: „Haben wir es bald?“">– hammersbald?</span></router-link>
      <span class="spacer" />
      <router-link to="/todo" class="lnk desk todo">{{ $t('Meine Aufgaben') }}<span v-if="todo.open" class="tb" :class="{ late: todo.late }" :title="todo.late ? $t('{1} überfällig', { 1: todo.late }) : ''">{{ todo.open }}</span></router-link>
      <div class="dd desk">
        <button class="lnk ddbtn" :class="{ on: overviewActive }" aria-haspopup="true" :aria-expanded="ddOpen" @click.stop="ddOpen = !ddOpen">{{ $t('Übersicht') }} ▾</button>
        <div v-if="ddOpen" class="ddmenu" role="menu">
          <router-link to="/dashboard" role="menuitem">{{ $t('Dashboard') }}</router-link>
          <router-link to="/overview" role="menuitem">{{ $t('Wer arbeitet woran') }}</router-link>
          <router-link to="/org" role="menuitem">{{ $t('Organigramm') }}</router-link>
        </div>
      </div>
      <router-link to="/absences" class="lnk desk">{{ $t('Meine Abwesenheiten') }}</router-link>
      <router-link to="/templates" class="lnk desk">{{ $t('Vorlagen') }}</router-link>
      <router-link v-if="hasReports" to="/reports" class="lnk desk">{{ $t('Reports') }}</router-link>
      <router-link to="/help" class="lnk desk">{{ $t('Handbuch') }}</router-link>
      <router-link v-if="isAdmin" to="/admin" class="lnk desk">{{ $t('Verwaltung') }}</router-link>
      <NotificationBell />
      <button class="ghost helpbtn desk" :title="$t('Hilfe (F1)')" @click="ui.helpOpen = !ui.helpOpen">?</button>
      <button class="ghost pref desk" :title="themeTitle()" :aria-label="themeTitle()" @click="savePrefs({ theme: nextTheme[theme] })">{{ themeIcon[theme] }}</button>
      <button class="ghost pref lng desk" :title="$t('Sprache')" :aria-label="$t('Sprache')" @click="savePrefs({ lang: lang === 'de' ? 'en' : 'de' })">{{ lang === 'de' ? 'DE' : 'EN' }}</button>
      <span class="who desk">{{ dname(state.user) }} <small>({{ state.user.role }})</small></span>
      <button class="ghost desk" @click="out">{{ $t('Abmelden') }}</button>
      <button class="ghost burger" :aria-label="$t('Menü')" :aria-expanded="menuOpen" @click.stop="menuOpen = !menuOpen">{{ menuOpen ? '✕' : '☰' }}</button>
    </header>
    <nav v-if="state.user && menuOpen" class="mmenu no-print" @click="menuOpen = false">
      <router-link to="/todo">{{ $t('Meine Aufgaben') }}<span v-if="todo.open" class="tb" :class="{ late: todo.late }">{{ todo.open }}</span></router-link>
      <router-link to="/dashboard">{{ $t('Dashboard') }}</router-link>
      <router-link to="/overview">{{ $t('Wer arbeitet woran') }}</router-link>
      <router-link to="/org">{{ $t('Organigramm') }}</router-link>
      <router-link to="/absences">{{ $t('Meine Abwesenheiten') }}</router-link>
      <router-link to="/templates">{{ $t('Vorlagen') }}</router-link>
      <router-link v-if="hasReports" to="/reports">{{ $t('Reports') }}</router-link>
      <router-link to="/help">{{ $t('Handbuch') }}</router-link>
      <router-link v-if="isAdmin" to="/admin">{{ $t('Verwaltung') }}</router-link>
      <div class="mrow">
        <button @click.stop="ui.helpOpen = !ui.helpOpen; menuOpen = false">? {{ $t('Hilfe') }}</button>
        <button @click.stop="savePrefs({ theme: nextTheme[theme] })">{{ themeIcon[theme] }} {{ themeTitle() }}</button>
        <button @click.stop="savePrefs({ lang: lang === 'de' ? 'en' : 'de' })">{{ lang === 'de' ? 'DE → EN' : 'EN → DE' }}</button>
      </div>
      <div class="mwho">{{ dname(state.user) }} <small>({{ state.user.role }})</small> <button @click="out">{{ $t('Abmelden') }}</button></div>
    </nav>
    <main><router-view /></main>
    <div v-if="state.toast" class="toast" :class="state.toastKind" @click="state.toast = ''">{{ state.toast }}</div>
    <div v-if="state.busy" class="busy no-print" />
    <HelpPanel v-if="state.user" />
  </div>
</template>

<style scoped>
.app { display: flex; flex-direction: column; height: 100%; }
main { flex: 1; min-height: 0; overflow: hidden; display: flex; flex-direction: column; }
main > :deep(*) { flex: 1; min-height: 0; }
.top { display: flex; align-items: center; gap: 14px; padding: 6px 14px; background: var(--bg-top); color: #fff; }
.brand { color: #fff; font-weight: 700; text-decoration: none; display: flex; align-items: center; gap: 8px; }
.brand .motto { font-weight: 400; font-style: italic; font-size: 12px; opacity: .6; margin-left: -2px; }
.spacer { flex: 1; }
.lnk { color: #cfe0ff; text-decoration: none; font-size: 13px; }
.dd { position: relative; }
.ddbtn { background: none; border: 0; padding: 0; cursor: pointer; font-family: inherit; }
.ddbtn.on, .ddbtn:hover { color: #fff; }
.ddmenu { position: absolute; top: calc(100% + 8px); left: -10px; z-index: 60; min-width: 200px; display: flex; flex-direction: column; padding: 6px; background: var(--bg-top); border: 1px solid rgba(255, 255, 255, .2); border-radius: 8px; box-shadow: 0 8px 24px rgba(0, 0, 0, .35); }
.ddmenu a { color: #e6efff; text-decoration: none; font-size: 13px; padding: 8px 10px; border-radius: 6px; white-space: nowrap; }
.ddmenu a:hover { background: rgba(255, 255, 255, .12); }
.ddmenu a.router-link-active { color: #fff; font-weight: 600; }
.tb { display: inline-block; margin-left: 5px; min-width: 18px; padding: 0 5px; border-radius: 9px; background: rgba(255, 255, 255, .22); color: #fff; font-size: 11px; text-align: center; line-height: 18px; }
.tb.late { background: #dc2626; }
.who { font-size: 13px; }
.who small { opacity: .7; }
.top .ghost { color: #fff; border-color: rgba(255, 255, 255, .35); }
.pref { height: 28px; padding: 0 8px; min-width: 28px; font-size: 14px; }
.helpbtn { width: 28px; height: 28px; padding: 0; border-radius: 50%; font-weight: 700; }
.offline { background: #b45309; color: #fff; text-align: center; padding: 4px; font-size: 13px; }
.toast { position: fixed; bottom: 18px; left: 50%; transform: translateX(-50%); background: #1f2937; color: #fff; padding: 10px 18px; border-radius: 8px; z-index: 100; max-width: 80vw; box-shadow: 0 4px 16px rgba(0, 0, 0, .35); cursor: pointer; }
.toast.error { background: #b42318; }
.busy { position: fixed; top: 0; left: 0; right: 0; height: 3px; z-index: 101; background: linear-gradient(90deg, transparent, var(--accent), transparent); animation: slide 1s infinite linear; background-size: 40% 100%; background-repeat: no-repeat; }
@keyframes slide { from { background-position: -40% 0; } to { background-position: 140% 0; } }
.burger { display: none; width: 34px; height: 30px; padding: 0; color: #fff; border-color: rgba(255, 255, 255, .35); font-size: 16px; }
.mmenu { display: none; }
@media (max-width: 700px) {
  .top { gap: 8px; padding: 6px 10px; flex-wrap: nowrap; }
  .top .desk { display: none; }
  .burger { display: inline-block; }
  .mmenu { display: flex; flex-direction: column; background: var(--bg-top); color: #fff; padding: 4px 10px 12px; border-top: 1px solid rgba(255, 255, 255, .12); }
  .mmenu a { color: #e6efff; text-decoration: none; padding: 11px 4px; border-bottom: 1px solid rgba(255, 255, 255, .1); font-size: 15px; }
  .mmenu a.router-link-active { color: #fff; font-weight: 600; }
  .mrow { display: flex; flex-wrap: wrap; gap: 8px; padding: 12px 0 8px; }
  .mrow button, .mwho button { color: #fff; background: transparent; border-color: rgba(255, 255, 255, .35); padding: 6px 10px; }
  .mwho { display: flex; align-items: center; gap: 8px; font-size: 13px; padding-top: 4px; }
  .mwho button { margin-left: auto; }
}
</style>
