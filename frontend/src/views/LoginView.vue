<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError } from '../lib/api'
import { login } from '../lib/store'
import { lang, setLang, t } from '../lib/i18n'

const router = useRouter()
const route = useRoute()
const username = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  busy.value = true
  error.value = ''
  try {
    await login(username.value, password.value)
    router.push((route.query.next as string) || '/')
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : t('Anmeldung fehlgeschlagen')
  } finally { busy.value = false }
}
</script>

<template>
  <div class="wrap">
    <form class="card" @submit.prevent="submit">
      <img src="/icon.svg" width="56" height="56" alt="" />
      <h2>OpenPlan</h2>
      <p class="sub">{{ $t('Projektplanung mit Gantt & kritischem Pfad') }}</p>
      <label>{{ $t('Benutzername') }} <input v-model="username" autocomplete="username" autofocus required /></label>
      <label>{{ $t('Passwort') }} <input v-model="password" type="password" autocomplete="current-password" required /></label>
      <p v-if="error" class="err">{{ error }}</p>
      <button class="primary" :disabled="busy">{{ $t('Anmelden') }}</button>
      <button type="button" class="ghost lng" @click="setLang(lang === 'de' ? 'en' : 'de')">{{ lang === 'de' ? 'English' : 'Deutsch' }}</button>
    </form>
  </div>
</template>

<style scoped>
.wrap { display: flex; align-items: center; justify-content: center; padding: 16px; }
.card { width: 340px; max-width: 100%; display: flex; flex-direction: column; gap: 10px; padding: 28px; border: 1px solid var(--border); border-radius: 12px; background: var(--bg-head); }
.card h2 { margin: 0; }
.sub { margin: 0 0 8px; color: var(--fg-dim); font-size: 13px; }
label { display: flex; flex-direction: column; gap: 3px; font-size: 13px; color: var(--fg-dim); }
.err { color: var(--bar-critical); margin: 0; }
button { padding: 8px; }
</style>
