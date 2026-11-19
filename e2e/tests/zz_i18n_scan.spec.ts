import { test, ADMIN, api, adminToken } from '../helpers/api'

// Hilfsprüfung (nicht Teil der regulären Suite): findet deutsche Texte, die bei Sprache „en“ noch sichtbar sind.
const GERMAN = /[äöüÄÖÜß]|\b(und|nicht|keine?|noch|oder|für|von|bis|mit|der|die|das|zum|zur|alle|neu|Neu|Lade|Speichern|Löschen|Abbrechen|Vorgang|Vorgänge|Ressource|Projekt|Fortschritt|Einstellungen|Bearbeiten|Ende|Beginn|Dauer|Hinzufügen)\b/

async function leaks(page: import('@playwright/test').Page, where: string) {
  const found: string[] = await page.evaluate(() => {
    const out = new Set<string>()
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
    let n: Node | null
    while ((n = walker.nextNode())) {
      const el = (n as Text).parentElement
      if (!el || ['SCRIPT', 'STYLE'].includes(el.tagName)) continue
      const style = getComputedStyle(el)
      if (style.display === 'none' || style.visibility === 'hidden') continue
      const t = (n.textContent ?? '').replace(/\s+/g, ' ').trim()
      if (t.length > 1) out.add('T: ' + t)
    }
    document.querySelectorAll('[title],[placeholder],[aria-label]').forEach(e => {
      for (const a of ['title', 'placeholder', 'aria-label']) { const v = e.getAttribute(a); if (v) out.add('A: ' + v) }
    })
    return [...out]
  })
  const DATA = /Cisco|Werk |Werk$|Standort Zentrale|Logistik|Abnahme|Bestandsaufnahme|Rückbau|Staging|Wartungsfenster mit|Teillieferung|Austausch von|E2E|Rollout für|Ganz anderes|Abschluss|Beispielprojekt|Cisco/
  const bad = found.filter(s => GERMAN.test(s.slice(3)) && !DATA.test(s))
  if (bad.length) console.log(`\n## ${where}\n` + bad.map(b => '  ' + b.slice(0, 160)).join('\n'))
}

async function closeModal(page: import('@playwright/test').Page) {
  for (let i = 0; i < 3; i++) {
    if (!(await page.locator('.modal-back').count())) return
    await page.locator('.modal-back').first().click({ position: { x: 4, y: 4 }, timeout: 1500 }).catch(() => {})
    await page.keyboard.press('Escape')
    await page.waitForTimeout(200)
  }
}

test('Sprache en: übrig gebliebene deutsche Texte', async ({ page }) => {
  test.setTimeout(240000)
  const tok = await adminToken()
  const demo = await api('POST', '/projects/demo', tok)
  const pid = demo.project.id
  await api('PUT', '/auth/profile', tok, { lang: 'en' })
  await page.goto('/login')
  await page.locator('input[autocomplete=username]').fill(ADMIN.username)
  await page.locator('input[type=password]').fill(ADMIN.password)
  await page.locator('button.primary').click()
  await page.waitForURL(/\/$/)
  await page.waitForTimeout(800)
  await leaks(page, 'Projektliste')
  await page.goto(`/project/${pid}`)
  await page.waitForSelector('nav.tabs > button', { timeout: 15000 })
  const tabs = page.locator('.tabs button, nav button, .views button')
  await leaks(page, 'Projekt/Gantt')
  const count = await page.locator('nav.tabs > button').count()
  console.log('Tabs gefunden:', count)
  for (let i = 0; i < count; i++) {
    const b = page.locator('nav.tabs > button').nth(i)
    const label = (await b.textContent())?.trim()
    await b.click(); await page.waitForTimeout(700)
    await leaks(page, 'Tab ' + label)
    // Budget-Unterreiter
    const subs = page.locator('nav.sub button')
    const sc = await subs.count()
    for (let j = 0; j < sc; j++) { await subs.nth(j).click(); await page.waitForTimeout(400); await leaks(page, `Tab ${label} / Sub ${j}`) }
  }
  // Vorgangsdialog
  await page.locator('nav.tabs > button').first().click()
  await page.waitForTimeout(500)
  await page.getByText('Wartungsfenster mit Fachbereichen abstimmen').first().dblclick({ timeout: 4000 }).catch(() => {})
  await page.waitForTimeout(800)
  await leaks(page, 'Vorgangsdialog')
  await closeModal(page)
  await page.getByRole('button', { name: 'Settings' }).click({ timeout: 3000 }).catch(() => {})
  await page.waitForTimeout(600)
  await leaks(page, 'Projekteinstellungen')
  await closeModal(page)
  for (const name of ['Devices', 'Budget']) {
    await page.locator('nav.tabs > button', { hasText: name }).click()
    await page.waitForTimeout(500)
    for (const btn of ['Import device list …', '+ Device from template', 'Import CSV …', '+ Posting']) {
      const b = page.getByRole('button', { name: btn })
      if (await b.count()) { await b.first().click({ timeout: 2000 }).catch(() => {}); await page.waitForTimeout(500); await leaks(page, name + ' → ' + btn); await closeModal(page) }
    }
  }
  await page.getByRole('button', { name: '?' }).first().click({ timeout: 2000 }).catch(() => {})
  await page.waitForTimeout(500)
  await leaks(page, 'Hilfepanel')
  await page.keyboard.press('Escape')
  await page.goto('/help'); await page.waitForTimeout(700); await leaks(page, '/help')
  for (const path of ['/templates', '/reports', '/admin']) { await page.goto(path); await page.waitForTimeout(800); await leaks(page, path) }
  await page.goto('/admin')
  const n = await page.locator('.tabs button').count()
  for (let i = 0; i < n; i++) { const b = page.locator('.tabs button').nth(i); const l = (await b.textContent())?.trim(); await b.click(); await page.waitForTimeout(600); await leaks(page, 'Admin ' + l) }
  await api('PUT', '/auth/profile', tok, { lang: 'de' })
  await api('DELETE', `/projects/${pid}`, tok)
})
