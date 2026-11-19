// Hilfen für Bild-/PDF-Export: SVG -> PNG, beliebiges HTML-Element -> PNG (immer im hellen Design) und PDF über den Druckdialog.

export function downloadBlob(blob: Blob, name: string) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = name
  a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 5000)
}
export const fileSlug = (s: string) => s.replace(/[^\wäöüÄÖÜß-]+/g, '_').replace(/^_+|_+$/g, '') || 'export'

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('Bild konnte nicht erzeugt werden'))
    img.src = src
  })
}
async function drawToPng(svg: string, w: number, h: number, scale: number): Promise<Blob> {
  const img = await loadImage('data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg))
  scale = Math.min(scale, 16000 / Math.max(w, h))            // Canvas-Grenze der Browser (ca. 16 384 px je Kante)
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(w * scale); canvas.height = Math.round(h * scale)
  const ctx = canvas.getContext('2d')!
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
  return new Promise((resolve, reject) => canvas.toBlob(b => (b ? resolve(b) : reject(new Error('PNG konnte nicht erzeugt werden'))), 'image/png'))
}
/** Fertiges SVG (mit width/height) als PNG; ``scale`` 2 = doppelte Auflösung (scharf auf Folien). */
export const svgToPngBlob = (svg: string, w: number, h: number, scale = 2) => drawToPng(svg, w, h, scale)

/** HTML-Element mit eingebrannten Stilen (immer helles Design, ohne Elemente mit ``data-noexport``). */
export function elementToInlinedHtml(el: HTMLElement): { html: string; w: number; h: number } {
  const root = document.documentElement
  const prev = root.getAttribute('data-theme')
  root.setAttribute('data-theme', 'light')                       // synchron: es wird kein Zwischenbild gemalt
  try {
    const clone = el.cloneNode(true) as HTMLElement
    const drop: Element[] = []
    const walk = (src: Element, dst: Element) => {
      if (src.hasAttribute('data-noexport')) { drop.push(dst); return }
      const cs = getComputedStyle(src)
      let s = ''
      for (let i = 0; i < cs.length; i++) { const p = cs[i]; s += `${p}:${cs.getPropertyValue(p)};` }
      dst.setAttribute('style', s)
      for (let i = 0; i < src.children.length; i++) walk(src.children[i], dst.children[i])
    }
    walk(el, clone)
    drop.forEach(d => d.remove())
    clone.querySelectorAll('script').forEach(n => n.remove())
    const w = Math.ceil(Math.max(el.scrollWidth, el.getBoundingClientRect().width)), h = Math.ceil(Math.max(el.scrollHeight, el.getBoundingClientRect().height))
    clone.style.width = w + 'px'; clone.style.height = 'auto'; clone.style.overflow = 'visible'; clone.style.maxHeight = 'none'
    clone.style.background = '#ffffff'; clone.style.margin = '0'
    return { html: new XMLSerializer().serializeToString(clone), w, h }
  } finally {
    if (prev === null) root.removeAttribute('data-theme'); else root.setAttribute('data-theme', prev)
  }
}
export function htmlToPngBlob(html: string, w: number, h: number, scale = 2): Promise<Blob> {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}"><foreignObject x="0" y="0" width="100%" height="100%">${html}</foreignObject></svg>`
  return drawToPng(svg, w, h, scale)
}

/** PDF über den Druckdialog des Browsers („Als PDF speichern“): vektorbasiert, ohne Zusatzbibliothek. */
export function printDocument(bodyHtml: string, css: string, title: string) {
  const frame = document.createElement('iframe')
  frame.setAttribute('aria-hidden', 'true')
  frame.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0'
  document.body.appendChild(frame)
  const doc = frame.contentDocument!
  doc.open()
  doc.write(`<!doctype html><html><head><meta charset="utf-8"><title>${title.replace(/[<&]/g, ' ')}</title><style>${css}</style></head><body>${bodyHtml}</body></html>`)
  doc.close()
  const done = () => setTimeout(() => frame.remove(), 1000)
  frame.contentWindow!.addEventListener('afterprint', done)
  setTimeout(() => { frame.contentWindow!.focus(); frame.contentWindow!.print() }, 250)
  setTimeout(done, 120000)
}
/** SVG-Seiten (je eine Druckseite) mit festem Papierformat in mm bzw. px. */
export function printSvgPages(pages: string[], size: { mm?: [number, number]; px?: [number, number] }, title: string) {
  const [w, h] = size.mm ? size.mm.map(v => v + 'mm') : size.px!.map(v => v + 'px')
  const css = `@page{size:${w} ${h};margin:0}html,body{margin:0;padding:0;background:#fff}.pg{width:${w};height:${h};overflow:hidden;page-break-after:always;break-after:page}.pg:last-child{page-break-after:auto;break-after:auto}.pg svg{display:block;width:100%;height:100%}`
  printDocument(pages.map(p => `<div class="pg">${p}</div>`).join(''), css, title)
}
/** Inhalt eines Elements (bereits mit eingebrannten Stilen) auf A4 quer, verkleinert auf Seitenbreite. */
export function printInlinedHtml(html: string, w: number, title: string) {
  const usable = 1047                                           // A4 quer (297 mm) abzüglich 2 × 10 mm Rand, in CSS-Pixeln
  const zoom = w > usable ? usable / w : 1
  printDocument(`<div style="zoom:${zoom}">${html}</div>`, '@page{size:A4 landscape;margin:10mm}html,body{margin:0;background:#fff}', title)
}
