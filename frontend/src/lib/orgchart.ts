// Organigramm eines Projekts: Baum aus Projektleitung, Ressourcen („berichtet an“) und Mitgliedern ohne Ressource + SVG-Layout (immer helles Design).
import type { ProjectData } from './types'
import { dname } from './people'
import { t as tr } from './i18n'

export interface OrgNode {
  key: string; title: string; sub: string; note: string
  kind: 'root' | 'person' | 'extern' | 'member'
  children: OrgNode[]; x: number; y: number; stack: boolean
}
export const NW = 184, NH = 62, GX = 18, GY = 40, IND = 26, SGAP = 10, STACK_MIN = 7

const mk = (key: string, title: string, sub: string, note: string, kind: OrgNode['kind']): OrgNode =>
  ({ key, title, sub, note, kind, children: [], x: 0, y: 0, stack: false })

/** Baum aufbauen. Wurzel = Verantwortlicher (mit seiner eigenen Ressource verschmolzen); ohne „berichtet an“ hängt eine Ressource an der Wurzel. */
export function buildOrg(d: ProjectData): OrgNode | null {
  const owner = d.project.owner
  if (!owner) return null
  const ownerRes = d.resources.filter(r => r.user_id === owner.id)
  const root = mk('root', dname(owner), ownerRes.find(r => r.funktion)?.funktion || tr('Projektleitung'), owner.username, 'root')
  const byRes = new Map<number, OrgNode>()
  const resById = new Map(d.resources.map(r => [r.id, r]))
  for (const r of ownerRes) byRes.set(r.id, root)
  for (const r of d.resources) {
    if (!byRes.has(r.id)) byRes.set(r.id, mk('r' + r.id, r.name, r.funktion ?? '', r.user_id ? '' : tr('extern'), r.user_id ? 'person' : 'extern'))
  }
  for (const r of d.resources) {
    const n = byRes.get(r.id)!
    if (n === root) continue
    let loop = false
    const seen = new Set<number>()
    for (let c = r; c && c.reports_to;) {                    // Schutz vor Zirkeln (das Backend verhindert sie ohnehin)
      if (seen.has(c.id)) { loop = true; break }
      seen.add(c.id)
      const up = resById.get(c.reports_to)
      if (!up) break
      c = up
    }
    const p = !loop && r.reports_to ? byRes.get(r.reports_to) ?? root : root
    ;(p === n ? root : p).children.push(n)
  }
  const roleName = (r: string) => (r === 'editor' ? tr('Editor') : tr('Leser'))
  for (const m of d.members) {
    if (m.user_id === owner.id || d.resources.some(r => r.user_id === m.user_id)) continue
    root.children.push(mk('m' + m.user_id, dname(m), tr('Mitglied'), roleName(m.role), 'member'))
  }
  return root
}

/** Platz vergeben: Blätter nebeneinander, Eltern mittig; viele Blätter unter einem Knoten hängen als Liste darunter. */
export function layoutOrg(root: OrgNode): { w: number; h: number } {
  let cursor = 0, bottom = 0
  const place = (n: OrgNode, y: number): number => {
    n.y = y
    bottom = Math.max(bottom, y + NH)
    const kids = n.children
    if (!kids.length) { n.x = cursor + NW / 2; cursor += NW + GX; return n.x }
    if (kids.length >= STACK_MIN && kids.every(k => !k.children.length)) {
      n.stack = true
      const left = cursor
      n.x = left + NW / 2
      kids.forEach((k, i) => { k.x = left + IND + NW / 2; k.y = y + NH + 22 + i * (NH + SGAP); bottom = Math.max(bottom, k.y + NH) })
      cursor += NW + IND + GX
      return n.x
    }
    const cs = kids.map(k => place(k, y + NH + GY))
    n.x = (cs[0] + cs[cs.length - 1]) / 2
    return n.x
  }
  place(root, 0)
  return { w: Math.max(NW, cursor - GX), h: bottom }
}

const esc = (s: string) => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!)
const clip = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1) + '…' : s)
/** Text in Zeilen von höchstens ``max`` Zeichen umbrechen (an Leerzeichen; überlange Wörter werden hart getrennt). */
function wrap(text: string, max: number): string[] {
  const out: string[] = []
  let cur = ''
  for (let word of text.split(/\s+/).filter(Boolean)) {
    while (word.length > max) {
      if (cur) { out.push(cur); cur = '' }
      out.push(word.slice(0, max)); word = word.slice(max)
    }
    if (cur && (cur + ' ' + word).length > max) { out.push(cur); cur = word } else cur = cur ? cur + ' ' + word : word
  }
  if (cur) out.push(cur)
  return out
}

export interface OrgSvg { svg: string; w: number; h: number }
/** Fertiges SVG (mit Titelzeile) für Anzeige, PNG- und PDF-Export. */
export function orgSvg(root: OrgNode, title: string): OrgSvg {
  const { w: cw, h: ch } = layoutOrg(root)
  const PAD = 24, MINW = 560                                   // Mindestbreite, damit auch lange Titel Platz haben (Diagramm wird mittig gesetzt)
  const innerW = Math.max(cw, MINW)
  const titleLines = title ? wrap(title, Math.floor(innerW / 10.5)) : []   // 18 px fett ≈ 10,5 px je Zeichen
  const HEAD = titleLines.length ? titleLines.length * 24 + 16 : 0
  const W = innerW + 2 * PAD, H = ch + 2 * PAD + HEAD
  const ox = PAD + (innerW - cw) / 2, oy = PAD + HEAD
  const lines: string[] = [], boxes: string[] = []
  const walk = (n: OrgNode) => {
    const nx = ox + n.x, ny = oy + n.y
    const left = nx - NW / 2
    if (n.children.length) {
      if (n.stack) {
        const sx = left + IND / 2
        const last = n.children[n.children.length - 1]
        lines.push(`<path d="M${sx} ${ny + NH}V${oy + last.y + NH / 2}"/>`)
        for (const k of n.children) lines.push(`<path d="M${sx} ${oy + k.y + NH / 2}H${ox + k.x - NW / 2}"/>`)
      } else {
        const my = ny + NH + GY / 2
        lines.push(`<path d="M${nx} ${ny + NH}V${my}"/>`)
        const xs = n.children.map(k => ox + k.x)
        lines.push(`<path d="M${Math.min(...xs)} ${my}H${Math.max(...xs)}"/>`)
        for (const x of xs) lines.push(`<path d="M${x} ${my}V${ny + NH + GY}"/>`)
      }
    }
    const isRoot = n.kind === 'root'
    const fill = isRoot ? '#1d4ed8' : n.kind === 'member' ? '#f1f5f9' : n.kind === 'extern' ? '#f8fafc' : '#ffffff'
    const stroke = isRoot ? '#1e40af' : n.kind === 'member' ? '#cbd5e1' : '#94a3b8'
    boxes.push(`<g data-key="${esc(n.key)}"><title>${esc([n.title, n.sub, n.note].filter(Boolean).join(' · '))}</title>`
      + `<rect x="${left}" y="${ny}" width="${NW}" height="${NH}" rx="8" fill="${fill}" stroke="${stroke}" stroke-width="1.5"${n.kind === 'extern' ? ' stroke-dasharray="5 3"' : ''}/>`
      + `<text x="${left + 10}" y="${ny + 22}" font-size="13" font-weight="700" fill="${isRoot ? '#ffffff' : '#0f172a'}">${esc(clip(n.title, 22))}</text>`
      + (n.sub ? `<text x="${left + 10}" y="${ny + 40}" font-size="12" fill="${isRoot ? '#dbeafe' : '#2563eb'}">${esc(clip(n.sub, 25))}</text>` : '')
      + (n.note ? `<text x="${left + 10}" y="${ny + 55}" font-size="11" fill="${isRoot ? '#bfdbfe' : '#64748b'}">${esc(clip(n.note, 28))}</text>` : '')
      + '</g>')
    n.children.forEach(walk)
  }
  walk(root)
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" font-family="'Segoe UI', Arial, sans-serif">`
    + `<rect width="${W}" height="${H}" fill="#ffffff"/>`
    + titleLines.map((l, i) => `<text x="${PAD}" y="${PAD + 18 + i * 24}" font-size="18" font-weight="700" fill="#0f172a">${esc(l)}</text>`).join('')
    + `<g fill="none" stroke="#94a3b8" stroke-width="1.5">${lines.join('')}</g>${boxes.join('')}</svg>`
  return { svg, w: W, h: H }
}
