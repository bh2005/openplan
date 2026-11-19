<script setup lang="ts">
import { releases, type ChangeKind } from '../content/changelog'
import { locale } from '../lib/i18n'

const label: Record<ChangeKind, string> = { neu: 'Neu', verbessert: 'Verbessert', behoben: 'Behoben' }
const fmt = (d: string) => new Date(d + 'T00:00:00').toLocaleDateString(locale(), { day: '2-digit', month: '2-digit', year: 'numeric' })
</script>

<template>
  <div class="cl">
    <p class="dim">{{ $t('Was sich in OpenPlan geändert hat – die neueste Version steht oben.') }}</p>
    <section v-for="(r, i) in releases" :key="r.version" class="rel">
      <h3>
        <span class="ver">v{{ r.version }}</span> {{ $t(r.title) }}
        <span v-if="i === 0" class="cur">{{ $t('aktuell') }}</span>
        <span class="date">{{ fmt(r.date) }}</span>
      </h3>
      <ul>
        <li v-for="(c, j) in r.changes" :key="j"><span class="kind" :class="c.kind">{{ $t(label[c.kind]) }}</span>{{ $t(c.text) }}</li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.dim { color: var(--fg-dim); }
.rel { margin: 0 0 22px; }
.rel h3 { font-size: 15px; margin: 0 0 8px; display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.ver { font-family: ui-monospace, Consolas, monospace; background: var(--chip); padding: 1px 7px; border-radius: 4px; }
.cur { font-size: 11px; font-weight: 600; color: #fff; background: var(--ok); padding: 1px 7px; border-radius: 10px; }
.date { margin-left: auto; font-size: 12px; font-weight: 400; color: var(--fg-dim); }
ul { list-style: none; margin: 0; padding: 0; }
li { padding: 4px 0; border-bottom: 1px solid var(--border); }
.kind { display: inline-block; min-width: 74px; margin-right: 10px; text-align: center; font-size: 11px; font-weight: 600; padding: 1px 6px; border-radius: 4px; }
.kind.neu { background: color-mix(in srgb, var(--ok) 20%, transparent); color: var(--ok); }
.kind.verbessert { background: color-mix(in srgb, var(--accent) 18%, transparent); color: var(--accent); }
.kind.behoben { background: color-mix(in srgb, var(--blocked) 22%, transparent); color: var(--blocked); }
</style>
