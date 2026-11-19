<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getTopic, getTopics, GROUPS, highlight, search } from '../content/help'

const route = useRoute()
const router = useRouter()
const query = ref('')
const all = ref(false)                               // alle Kapitel untereinander (Drucken)

const id = computed(() => (getTopic(String(route.params.id)) ? String(route.params.id) : 'start'))
const topic = computed(() => getTopic(id.value)!)
const idx = computed(() => getTopics().findIndex(t => t.id === id.value))
const prev = computed(() => getTopics()[idx.value - 1])
const next = computed(() => getTopics()[idx.value + 1])
const hits = computed(() => search(query.value))
const shown = computed(() => (all.value ? getTopics() : [topic.value]))
const html = (t: ReturnType<typeof getTopics>[number]) => highlight(t.html, query.value)

function go(t: string) { query.value = ''; all.value = false; router.push('/help/' + t); document.querySelector('.hv-main')?.scrollTo(0, 0) }
async function printAll() {
  all.value = true
  await nextTick()
  window.print()
  all.value = false
}
</script>

<template>
  <div class="hv">
    <aside class="hv-side no-print">
      <input v-model="query" type="search" :placeholder="$t('Handbuch durchsuchen …')" />
      <template v-if="query.trim().length >= 2">
        <p v-if="!hits.length" class="dim">{{ $t('Keine Treffer.') }}</p>
        <button v-for="h in hits" :key="h.topic.id" class="hit" @click="go(h.topic.id)"><b>{{ h.topic.title }}</b><small>{{ $t(h.topic.group) }}</small></button>
      </template>
      <template v-else>
        <template v-for="g in GROUPS" :key="g">
          <div class="grp">{{ $t(g) }}</div>
          <a v-for="t in getTopics().filter(x => x.group === g)" :key="t.id" href="#" class="item" :class="{ on: t.id === id && !all }" @click.prevent="go(t.id)">{{ t.title }}</a>
        </template>
      </template>
      <button class="print" @click="printAll">{{ $t('🖨 Gesamtes Handbuch drucken') }}</button>
    </aside>

    <main class="hv-main">
      <article v-for="t in shown" :key="t.id" class="help-body doc">
        <div class="crumb no-print">{{ $t(t.group) }}</div>
        <div v-html="html(t)" />
      </article>
      <nav v-if="!all" class="pn no-print">
        <button v-if="prev" @click="go(prev.id)">← {{ prev.title }}</button><span class="sp" />
        <button v-if="next" @click="go(next.id)">{{ next.title }} →</button>
      </nav>
    </main>
  </div>
</template>

<style scoped>
.hv { display: flex; height: 100%; min-height: 0; }
.hv-side { width: 280px; flex: none; overflow-y: auto; padding: 14px; border-right: 1px solid var(--border); background: var(--bg-head); }
.hv-side input { width: 100%; margin-bottom: 8px; }
.grp { font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--fg-dim); margin: 14px 0 4px; font-weight: 600; }
.item { display: block; padding: 5px 8px; border-radius: 5px; color: var(--fg); text-decoration: none; font-size: 13px; }
.item:hover { background: var(--row-sel); } .item.on { background: var(--accent); color: #fff; font-weight: 600; }
.hit { display: flex; flex-direction: column; width: 100%; text-align: left; background: none; border: 0; border-bottom: 1px solid var(--border); border-radius: 0; padding: 7px 4px; cursor: pointer; color: var(--fg); }
.hit small, .dim { color: var(--fg-dim); }
.print { margin-top: 18px; width: 100%; }
.hv-main { flex: 1; min-width: 0; overflow-y: auto; padding: 24px 32px 40px; }
.doc { max-width: 860px; margin-bottom: 30px; }
.crumb { font-size: 12px; text-transform: uppercase; letter-spacing: .05em; color: var(--fg-dim); margin-bottom: 4px; }
.pn { display: flex; max-width: 860px; margin-top: 28px; padding-top: 14px; border-top: 1px solid var(--border); } .sp { flex: 1; }
@media (max-width: 800px) { .hv { flex-direction: column; } .hv-side { width: auto; max-height: 38%; border-right: 0; border-bottom: 1px solid var(--border); } .hv-main { padding: 16px; } }
</style>
