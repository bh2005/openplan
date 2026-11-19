<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api } from '../lib/api'
import { fmt } from '../lib/dates'
import { state, toast } from '../lib/store'
import type { TaskFile } from '../lib/types'
import { t as tr } from '../lib/i18n'

const props = defineProps<{ taskId: number; projectId: number; canEdit: boolean }>()
const files = ref<TaskFile[]>([])
const busy = ref(false)
const over = ref(false)
const comment = ref('')
const link = reactive({ open: false, url: '', title: '' })
const input = ref<HTMLInputElement | null>(null)

async function load() {
  try { files.value = await api.files(props.taskId) } catch (e) { toast((e as Error).message, 'error') }
}
onMounted(load)
async function refreshProject() { try { state.data = await api.project(props.projectId) } catch { /* Poll holt es nach */ } }

async function upload(list: FileList | File[]) {
  const arr = Array.from(list)
  if (!arr.length) return
  busy.value = true
  try {
    files.value = await api.uploadFiles(props.taskId, arr, comment.value)
    comment.value = ''
    toast(arr.length === 1 ? tr('„{1}“ hochgeladen', { 1: arr[0].name }) : tr('{1} Dateien hochgeladen', { 1: arr.length }))
    await refreshProject()
  } catch (e) { toast((e as Error).message, 'error') } finally { busy.value = false; if (input.value) input.value.value = '' }
}
function onDrop(e: DragEvent) { over.value = false; if (props.canEdit && e.dataTransfer?.files) upload(e.dataTransfer.files) }

async function addLink() {
  if (!link.url.trim()) return
  busy.value = true
  try {
    files.value = await api.addLink(props.taskId, { url: link.url.trim(), title: link.title.trim(), comment: comment.value })
    link.url = ''; link.title = ''; link.open = false; comment.value = ''
    await refreshProject()
  } catch (e) { toast((e as Error).message, 'error') } finally { busy.value = false }
}

async function open(f: TaskFile, inline = false) {
  if (f.kind === 'link') { window.open(f.url, '_blank', 'noopener,noreferrer'); return }
  try {
    const blob = await api.downloadFile(f.id, inline)
    const url = URL.createObjectURL(blob)
    if (inline && blob.type && blob.type !== 'application/octet-stream') { window.open(url, '_blank', 'noopener'); setTimeout(() => URL.revokeObjectURL(url), 60000); return }
    const a = document.createElement('a')
    a.href = url; a.download = f.filename; a.click()
    setTimeout(() => URL.revokeObjectURL(url), 5000)
  } catch (e) { toast((e as Error).message, 'error') }
}
async function remove(f: TaskFile) {
  if (!confirm(f.kind === 'link' ? tr('Link „{1}“ entfernen?', { 1: f.filename }) : tr('Dokument „{1}“ endgültig löschen?', { 1: f.filename }))) return
  try { await api.deleteFile(f.id); files.value = files.value.filter(x => x.id !== f.id); await refreshProject() } catch (e) { toast((e as Error).message, 'error') }
}

const previewable = (f: TaskFile) => f.kind === 'file' && /^(application\/pdf|image\/(png|jpeg|gif|webp))$/.test(f.mime)
const host = (u: string) => { try { return new URL(u).host } catch { return '' } }
const isOneDrive = (u: string) => /(sharepoint\.com|onedrive\.live\.com|1drv\.ms|onedrive\.com)$/i.test(host(u))
function icon(f: TaskFile) {
  if (f.kind === 'link') return isOneDrive(f.url) ? '☁️' : '🔗'
  const n = f.filename.toLowerCase()
  if (/\.(xlsx?|xlsm|csv|ods)$/.test(n)) return '📊'
  if (/\.(docx?|odt|rtf|txt|md)$/.test(n)) return '📝'
  if (/\.pdf$/.test(n)) return '📕'
  if (/\.(png|jpe?g|gif|webp|bmp)$/.test(n)) return '🖼️'
  if (/\.(zip|7z|rar|tar|gz)$/.test(n)) return '🗜️'
  return '📄'
}
const size = (b: number) => (b < 1024 ? b + ' B' : b < 1048576 ? (b / 1024).toFixed(0) + ' KB' : (b / 1048576).toFixed(1).replace('.', ',') + ' MB')
</script>

<template>
  <div class="docs">
    <div class="head"><b>{{ $t('Dokumente & Links') }}</b><span class="dim">{{ files.length }}</span></div>
    <ul v-if="files.length" class="list">
      <li v-for="f in files" :key="f.id">
        <span class="ic">{{ icon(f) }}</span>
        <div class="meta">
          <a href="#" class="name" :title="f.kind === 'link' ? f.url : f.filename" @click.prevent="open(f)">{{ f.filename }}</a>
          <small class="dim">
            <template v-if="f.kind === 'link'">{{ isOneDrive(f.url) ? 'OneDrive/SharePoint' : host(f.url) }} · </template>
            <template v-else>{{ size(f.size) }} · </template>{{ f.uploaded_by }} · {{ fmt(f.uploaded_at) }}<template v-if="f.comment"> · {{ f.comment }}</template>
          </small>
        </div>
        <button v-if="previewable(f)" type="button" class="sm" :title="$t('Vorschau in neuem Tab')" @click="open(f, true)">{{ $t('Ansehen') }}</button>
        <button type="button" class="sm" @click="open(f)">{{ f.kind === 'link' ? $t('Öffnen') : $t('Laden') }}</button>
        <button v-if="canEdit" type="button" class="sm danger" :title="$t('Löschen')" @click="remove(f)">×</button>
      </li>
    </ul>
    <p v-else class="dim empty">{{ $t('Noch keine Dokumente. {1}', { 1: canEdit ? $t('Lieferscheine, Stundenzettel, Excel-Tabellen … hier ablegen oder einen OneDrive-Link anhängen.') : '' }) }}</p>

    <template v-if="canEdit">
      <div class="drop" :class="{ over, busy }" @dragover.prevent="over = true" @dragleave="over = false" @drop.prevent="onDrop" @click="input?.click()">
        {{ busy ? $t('Wird hochgeladen …') : $t('Dateien hierher ziehen oder klicken (mehrere möglich)') }}
        <input ref="input" type="file" multiple hidden @change="e => upload((e.target as HTMLInputElement).files ?? [])" />
      </div>
      <div class="row">
        <input v-model="comment" :placeholder="$t('Kommentar (optional, z. B. Lieferschein Nr. 4711)')" maxlength="300" />
        <button type="button" @click="link.open = !link.open">{{ $t('🔗 Link anhängen') }}</button>
      </div>
      <div v-if="link.open" class="linkform">
        <input v-model="link.url" :placeholder="$t('https://…sharepoint.com/… oder OneDrive-Freigabelink')" @keydown.enter.prevent="addLink" />
        <input v-model="link.title" :placeholder="$t('Titel (optional)')" maxlength="200" @keydown.enter.prevent="addLink" />
        <button type="button" class="primary" :disabled="busy || !link.url.trim()" @click="addLink">{{ $t('Anhängen') }}</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.docs { margin: 12px 0 4px; border-top: 1px solid var(--border); padding-top: 10px; }
.head { display: flex; gap: 8px; align-items: baseline; margin-bottom: 6px; } .dim { color: var(--fg-dim); font-size: 12px; }
.list { list-style: none; padding: 0; margin: 0 0 8px; }
.list li { display: flex; align-items: center; gap: 8px; padding: 5px 0; border-bottom: 1px solid var(--border); }
.ic { font-size: 18px; width: 24px; text-align: center; flex: none; }
.meta { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
.sm { font-size: 12px; padding: 2px 8px; flex: none; }
.empty { margin: 4px 0 8px; }
.drop { border: 2px dashed var(--border); border-radius: 8px; padding: 12px; text-align: center; color: var(--fg-dim); cursor: pointer; font-size: 13px; }
.drop.over { border-color: var(--accent); background: var(--row-sel); color: var(--fg); } .drop.busy { opacity: .6; cursor: progress; }
.row, .linkform { display: flex; gap: 6px; margin-top: 8px; } .row input { flex: 1; }
.linkform input:first-child { flex: 2; } .linkform input:nth-child(2) { flex: 1; }
</style>
