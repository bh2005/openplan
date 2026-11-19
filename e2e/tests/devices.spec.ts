import path from 'node:path'
import { test, expect, ADMIN, adminToken, api, addTask, createProject, tab, uniq } from '../helpers/api'

const SAMPLE = path.resolve(__dirname, '../../docs/import-vorlagen/geraeteliste-vorlage.xlsx')

async function asAdmin(page: import('@playwright/test').Page, target: string) {
  await page.goto('/login')
  await page.locator('input[autocomplete=username]').fill(ADMIN.username)
  await page.locator('input[type=password]').fill(ADMIN.password)
  await page.locator('button.primary').click()
  await expect(page.getByRole('button', { name: 'Abmelden' })).toBeVisible()
  await page.goto(target)
}

test.describe('Vorlagen, Geräteliste-Import und Matrix', () => {
  test('Muster-Excel importieren (Vorschau → Import), Matrix, Spalte auf „erledigt“, Rückgängig', async ({ page }) => {
    const admin = await adminToken()
    const { pid } = await createProject(admin, 'E2E Geräte ' + uniq())
    await asAdmin(page, `/project/${pid}`)
    await tab(page, 'Geräte').click()
    await expect(page.getByText('Noch keine Geräte')).toBeVisible()
    await page.getByRole('button', { name: 'Geräteliste importieren …' }).first().click()
    await page.locator('input[type=file]').setInputFiles(SAMPLE)
    await expect(page.getByText('Spalten zuordnen')).toBeVisible()
    // Verantwortliche aus dem Muster gibt es hier nicht → nicht importieren; unbekannte Kostenstelle/-art anlegen lassen
    await page.locator('.map tr').filter({ has: page.getByRole('cell', { name: 'Verantwortlich (Benutzer)', exact: true }) }).locator('select').selectOption('')
    await page.getByLabel('unbekannte Kostenstellen/-arten anlegen').check()
    await page.getByRole('button', { name: 'Vorschau prüfen' }).click()
    const rep = page.locator('.rep')
    await expect(rep).toContainText('8 neue Geräte')
    await expect(rep).toContainText('53 Schritte')
    await expect(rep).toContainText('3 neue Standorte')
    await expect(rep).not.toContainText('Fehler')
    // Trockenlauf hat nichts geschrieben
    expect((await api('GET', `/projects/${pid}`, admin)).tasks.length).toBe(0)
    await page.getByRole('button', { name: 'Importieren', exact: true }).click()
    await expect(page.getByText('Import abgeschlossen')).toBeVisible()
    await page.getByRole('button', { name: 'Fertig' }).click()

    // Struktur im Plan: Standort → Gerät → Schritte; Plankosten + Fenster
    const d = await api('GET', `/projects/${pid}`, admin)
    expect(d.tasks.filter((t: any) => t.ext_key).length).toBe(8)
    expect(d.tasks.filter((t: any) => !t.parent_id && t.summary).map((t: any) => t.name).sort()).toEqual(['Werk Hattorf', 'Werk Nord', 'Zentrale Kassel'])
    const ex = d.tasks.find((t: any) => t.name === 'Austausch vor Ort' && t.constraint_date === '2026-11-02')
    expect(ex.deadline).toBe('2026-11-06')

    // Matrix: 6 Switche; Spalte „Bestellung“ per Kopfklick wählen und auf erledigt setzen
    await expect(page.locator('.mx tbody tr').filter({ hasText: 'sw-kas-z-01' })).toBeVisible()
    await page.locator('.mx thead th.st').first().click()
    await expect(page.locator('.sbar')).toContainText('6')
    await page.getByRole('button', { name: /✓ Erledigt/ }).click()
    await expect(page.locator('.cell.s-done')).toHaveCount(6)
    await expect(page.locator('.sbar')).toContainText('0')                                   // Auswahl geleert
    // Vorlagenwechsel: Firewall (1 Gerät), Zellen anderer Vorlage nicht sichtbar
    await page.locator('.dm .bar select').first().selectOption({ label: 'Firewall' })
    await expect(page.locator('.mx tbody tr', { hasText: 'fw-neu-01' })).toBeVisible()
    await expect(page.locator('.mx tbody tr', { hasText: 'sw-kas-z-01' })).toHaveCount(0)

    // Import rückgängig (ein Schritt)
    await tab(page, 'Gantt').click()
    await page.locator('body').click({ position: { x: 5, y: 5 } })
    await page.keyboard.press('Control+z')                                                   // zuerst der Statuswechsel …
    await expect.poll(async () => (await api('GET', `/projects/${pid}`, admin)).tasks.filter((t: any) => t.status === 'done' && t.tpl_step).length).toBe(0)
    await page.waitForTimeout(900)
    await page.keyboard.press('Control+z')                                                   // … dann der gesamte Import
    await expect.poll(async () => (await api('GET', `/projects/${pid}`, admin)).tasks.length).toBe(0)
  })

  test('Nachimport ergänzt nur Neues und lässt den Status unangetastet (CSV)', async ({ page }) => {
    const admin = await adminToken()
    const { pid } = await createProject(admin, 'E2E Nachimport ' + uniq())
    await asAdmin(page, `/project/${pid}`)
    const csv = (rows: string[]) => ({ name: 'liste.csv', mimeType: 'text/csv', buffer: Buffer.from(['Hostname;Standort;Gerätetyp;Neues Modell', ...rows].join('\n'), 'utf-8') })
    const imp = async (rows: string[]) => {
      await page.getByRole('button', { name: 'Geräteliste importieren …' }).first().click()
      await page.locator('input[type=file]').setInputFiles(csv(rows))
      await page.getByRole('button', { name: 'Vorschau prüfen' }).click()
      await page.getByRole('button', { name: 'Importieren', exact: true }).click()
      await expect(page.getByText('Import abgeschlossen')).toBeVisible()
      await page.getByRole('button', { name: 'Fertig' }).click()
    }
    await tab(page, 'Geräte').click()
    await imp(['sw-a;Halle 1;Switch;Alt'])
    await page.locator('.mx thead th.st').first().click()
    await page.getByRole('button', { name: /✓ Erledigt/ }).click()
    await expect(page.locator('.cell.s-done')).toHaveCount(1)
    await imp(['sw-a;Halle 1;Switch;Neu', 'sw-b;Halle 1;Switch;Nachlieferung'])
    await expect(page.locator('.mx tbody tr', { hasText: 'sw-b' })).toBeVisible()
    await expect(page.locator('.cell.s-done')).toHaveCount(1)                                // erledigter Schritt von sw-a blieb
    const d = await api('GET', `/projects/${pid}`, admin)
    expect(d.tasks.filter((t: any) => t.ext_key).length).toBe(2)
    expect(d.tasks.find((t: any) => t.ext_key === 'sw-a').attrs.modell).toBe('Neu')
  })

  test('Fehlerhafte Liste: Vorschau nennt Fehler, Import gesperrt', async ({ page }) => {
    const admin = await adminToken()
    const { pid } = await createProject(admin, 'E2E Fehler ' + uniq())
    await asAdmin(page, `/project/${pid}`)
    await tab(page, 'Geräte').click()
    await page.getByRole('button', { name: 'Geräteliste importieren …' }).first().click()
    await page.locator('input[type=file]').setInputFiles({ name: 'x.csv', mimeType: 'text/csv', buffer: Buffer.from('Hostname;Standort;Gerätetyp\nok-1;A;Switch\nbad-1;A;Drucker\n', 'utf-8') })
    await page.getByRole('button', { name: 'Vorschau prüfen' }).click()
    await expect(page.locator('.errs')).toContainText('Keine Vorlage für Gerätetyp „Drucker“')
    await expect(page.getByRole('button', { name: 'Importieren', exact: true })).toBeDisabled()
    await page.getByLabel('fehlerhafte Zeilen überspringen').check()
    await expect(page.getByRole('button', { name: 'Importieren', exact: true })).toBeEnabled()
  })

  test('Vorlagen-Bibliothek: neue Vorlage anlegen, Schritte ordnen, speichern', async ({ page }) => {
    await asAdmin(page, '/templates')
    await expect(page.locator('.side .item', { hasText: 'Switch' }).first()).toBeVisible()
    await page.getByRole('button', { name: '+ Neu' }).click()
    const name = 'E2E-Typ-' + uniq()
    await page.getByLabel('Name (= Gerätetyp)').fill(name)
    await page.locator('.steps tbody tr').nth(0).locator('input').nth(0).fill('Erster Schritt')
    await page.getByRole('button', { name: '+ Schritt' }).click()
    await page.locator('.steps tbody tr').nth(1).locator('input').nth(0).fill('Zweiter Schritt')
    await page.locator('.steps tbody tr').nth(1).getByTitle('nach oben').click()                  // Reihenfolge tauschen
    await page.getByRole('button', { name: 'Speichern', exact: true }).click()
    await expect(page.locator('.side .item', { hasText: name })).toBeVisible()
    await page.reload()
    await page.locator('.side .item', { hasText: name }).click()
    await expect(page.locator('.steps tbody tr').nth(0).locator('input').nth(0)).toHaveValue('Zweiter Schritt')
    page.once('dialog', dlg => dlg.accept())
    await page.getByRole('button', { name: 'Löschen' }).click()
    await expect(page.locator('.side .item', { hasText: name })).toHaveCount(0)
  })

  test('Muster-Excel herunterladen (Vorlagen und Import-Dialog)', async ({ page }) => {
    await asAdmin(page, '/templates')
    const [dl] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: /Muster-Excel herunterladen/ }).click()])
    expect(dl.suggestedFilename()).toBe('geraeteliste-vorlage.xlsx')
    const admin = await adminToken()
    const { pid } = await createProject(admin, 'E2E Muster ' + uniq())
    await page.goto(`/project/${pid}`)
    await tab(page, 'Geräte').click()
    await page.getByRole('button', { name: 'Geräteliste importieren …' }).first().click()
    const [dl2] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: /Muster-Excel herunterladen/ }).click()])
    expect(dl2.suggestedFilename()).toBe('geraeteliste-vorlage.xlsx')
  })

  test('Paket „gehört zu“ einem Vorgang anlegen', async ({ page }) => {
    const admin = await adminToken()
    const { pid } = await createProject(admin, 'E2E Einordnen ' + uniq())
    const phase = await addTask(admin, pid, 'Phase Umbau', { duration: 1 })
    await asAdmin(page, `/project/${pid}`)
    await tab(page, 'Pakete').click()
    await page.locator('.pk .new input').first().fill('Paket unter Phase')
    await page.locator('.pk .new select').first().selectOption({ index: 1 })
    await page.getByRole('button', { name: 'Anlegen', exact: true }).click()
    await expect.poll(async () => {
      const d = await api('GET', `/projects/${pid}`, admin)
      return d.tasks.find((t: any) => t.name === 'Paket unter Phase')?.parent_id
    }).toBe(phase)
  })
})
