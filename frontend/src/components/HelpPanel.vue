<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { contextTopic, getTopic, getTopics, GROUPS, highlight, search } from '../content/help'
import { ui } from '../lib/store'

const route = useRoute()
const router = useRouter()
const query = ref('')
const picked = ref<string | null>(null)        // vom Nutzer gewähltes Thema (überschreibt den Kontext)
const searchEl = ref<HTMLInputElement | null>(null)

const ctx = computed(() => contextTopic(route.path, ui.tab, ui.sub))
const topic = computed(() => getTopic(picked.value ?? ctx.value) ?? getTopics()[0])
const hits = computed(() => search(query.value))
const body = computed(() => highlight(topic.value.html, query.value))
// Kontext gewechselt (anderer Tab/andere Seite) -> wieder dem Kontext folgen
watch(ctx, () => { picked.value = null })
watch(() => ui.helpOpen, async open => { if (open) { await Promise.resolve(); searchEl.value?.focus() } else { query.value = '' } })

function pick(id: string) { picked.value = id; query.value = '' }
function handbook() { ui.helpOpen = false; router.push('/help/' + topic.value.id) }
function onKey(e: KeyboardEvent) { if (e.key === 'Escape' && ui.helpOpen) ui.helpOpen = false }
onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
</script>

<template>
  <Teleport to="body">
    <Transition name="help-slide">
      <div v-if="ui.helpOpen" class="help-overlay no-print" @click.self="ui.helpOpen = false">
        <aside class="help-panel" role="dialog" :aria-label="$t('Hilfe')">
          <header>
            <span class="title">{{ $t('Hilfe') }}</span>
            <button class="lnk" @click="handbook">{{ $t('Handbuch →') }}</button>
            <button class="close" :title="$t('Schließen (Esc)')" @click="ui.helpOpen = false">✕</button>
          </header>
          <div class="searchbox"><input ref="searchEl" v-model="query" type="search" :placeholder="$t('Hilfe durchsuchen …')" /></div>

          <div v-if="query.trim().length >= 2" class="body results">
            <p v-if="!hits.length" class="dim">{{ $t('Keine Treffer für „{1}“.', { 1: query }) }}</p>
            <button v-for="h in hits" :key="h.topic.id" class="hit" @click="pick(h.topic.id)">
              <b>{{ h.topic.title }}</b><small>{{ $t(h.topic.group) }}</small><span v-html="highlight(h.snippet.replace(/</g, '&lt;'), query)" />
            </button>
          </div>
          <div v-else class="body">
            <div class="help-body" v-html="body" />
            <h4 class="more">{{ $t('Weitere Themen') }}</h4>
            <template v-for="g in GROUPS" :key="g">
              <div class="grp">{{ $t(g) }}</div>
              <button v-for="t in getTopics().filter(x => x.group === g)" :key="t.id" class="topic" :class="{ on: t.id === topic.id }" @click="pick(t.id)">{{ t.title }}</button>
            </template>
          </div>
          <footer>{{ $t('F1 oder ? öffnet/schließt die Hilfe · Esc schließt') }}</footer>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.help-overlay { position: fixed; inset: 0; z-index: 150; background: rgba(0, 0, 0, .3); }
.help-panel { position: fixed; top: 0; right: 0; bottom: 0; width: 420px; max-width: 96vw; background: var(--bg); color: var(--fg); box-shadow: -4px 0 24px rgba(0, 0, 0, .25); display: flex; flex-direction: column; overflow: hidden; border-left: 1px solid var(--border); }
header { display: flex; align-items: center; gap: 10px; padding: 12px 16px; border-bottom: 1px solid var(--border); background: var(--bg-head); }
.title { font-weight: 700; font-size: 15px; flex: 1; }
.lnk { background: none; border: 0; color: var(--accent); font-size: 12px; font-weight: 600; cursor: pointer; padding: 2px 4px; }
.lnk:hover { text-decoration: underline; }
.close { background: none; border: 0; font-size: 16px; color: var(--fg-dim); cursor: pointer; padding: 2px 6px; }
.searchbox { padding: 8px 16px; border-bottom: 1px solid var(--border); }
.searchbox input { width: 100%; }
.body { flex: 1; overflow-y: auto; padding: 14px 18px 20px; }
footer { padding: 8px 16px; border-top: 1px solid var(--border); font-size: 11px; color: var(--fg-dim); text-align: center; background: var(--bg-head); }
.dim { color: var(--fg-dim); }
.more { margin: 22px 0 4px; font-size: 12px; text-transform: uppercase; letter-spacing: .05em; color: var(--fg-dim); border-top: 1px solid var(--border); padding-top: 14px; }
.grp { font-size: 11px; color: var(--fg-dim); margin: 10px 0 2px; font-weight: 600; }
.topic { display: block; width: 100%; text-align: left; background: none; border: 0; border-radius: 5px; padding: 4px 8px; font-size: 13px; cursor: pointer; color: var(--fg); }
.topic:hover { background: var(--row-sel); } .topic.on { color: var(--accent); font-weight: 600; background: var(--row-sel); }
.hit { display: flex; flex-direction: column; gap: 2px; width: 100%; text-align: left; background: none; border: 0; border-bottom: 1px solid var(--border); border-radius: 0; padding: 8px 4px; cursor: pointer; color: var(--fg); }
.hit:hover { background: var(--row-sel); } .hit small { color: var(--fg-dim); } .hit span { font-size: 12px; color: var(--fg-dim); }
.help-slide-enter-active, .help-slide-leave-active { transition: opacity .2s ease; }
.help-slide-enter-active .help-panel, .help-slide-leave-active .help-panel { transition: transform .22s ease; }
.help-slide-enter-from, .help-slide-leave-to { opacity: 0; }
.help-slide-enter-from .help-panel, .help-slide-leave-to .help-panel { transform: translateX(100%); }
</style>
