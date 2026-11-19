import { test, expect, adminToken, api, createProject, uniq } from '../helpers/api'

// Regression: Das Commit der DB-Verbindung lief früher erst NACH dem Senden der Antwort. Ein schneller Client sah seine eigene Änderung dann
// nicht (404 „Projekt nicht gefunden“ beim sofortigen Folgezugriff). Nur über echtes HTTP reproduzierbar, daher hier statt in pytest.
test.describe('Konsistenz', () => {
  test('eben angelegte Objekte sind sofort für Folgeanfragen sichtbar (Lesen-nach-Schreiben)', async () => {
    const admin = await adminToken()
    const { pid } = await createProject(admin, 'E2E Konsistenz ' + uniq())
    let failures = 0
    for (let i = 0; i < 60; i++) {
      const d = await api('POST', `/projects/${pid}/tasks`, admin, { name: 'T' + i })
      const tid = Math.max(...d.tasks.map((t: any) => t.id))
      try { await api('PATCH', `/tasks/${tid}`, admin, { notes: 'sofort' }) } catch { failures++ }
      const c = await api('POST', `/tasks/${tid}/comments`, admin, { body: 'direkt danach' }).catch(() => null)
      if (!c) failures++
    }
    expect(failures).toBe(0)
  })

  test('Ereignisstrom liefert die aktuelle Revision und hält keine Datenbankverbindung offen', async () => {
    const admin = await adminToken()
    const { pid } = await createProject(admin, 'E2E Stream ' + uniq())
    const ctl = new AbortController()
    const base = process.env.E2E_BASE_URL ?? 'http://localhost:5173'
    const res = await fetch(`${base}/api/projects/${pid}/events`, { headers: { Authorization: 'Bearer ' + admin }, signal: ctl.signal })
    expect(res.headers.get('content-type')).toContain('text/event-stream')
    const reader = res.body!.getReader()
    const first = new TextDecoder().decode((await reader.read()).value)
    expect(first).toContain('event: revision')
    // Während der Strom offen ist, müssen normale Schreibzugriffe weiter funktionieren
    await api('POST', `/projects/${pid}/tasks`, admin, { name: 'während des Streams' })
    ctl.abort()
  })
})
