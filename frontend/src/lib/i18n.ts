import { ref } from 'vue'
import { en } from '../locales/en'

/**
 * Mehrsprachigkeit ohne Fremdbibliothek: Der deutsche Text ist zugleich der Schlüssel (Standardsprache).
 * `t('Abmelden')` liefert bei Sprache „en“ den Eintrag aus locales/en.ts, fehlt er, bleibt der deutsche Text stehen –
 * so lässt sich Datei für Datei umstellen. Platzhalter: `t('{n} Vorgänge', { n: 3 })`.
 */
export type Lang = 'de' | 'en'
export type Theme = 'auto' | 'light' | 'dark'

const LS_LANG = 'openplan.lang', LS_THEME = 'openplan.theme'
const read = (k: string) => { try { return localStorage.getItem(k) } catch { return null } }
const write = (k: string, v: string | null) => { try { v === null ? localStorage.removeItem(k) : localStorage.setItem(k, v) } catch { /* Speicher gesperrt */ } }

const asLang = (v: unknown): Lang => (v === 'en' ? 'en' : 'de')
const asTheme = (v: unknown): Theme => (v === 'light' || v === 'dark' ? v : 'auto')

export const lang = ref<Lang>(asLang(read(LS_LANG)))
export const theme = ref<Theme>(asTheme(read(LS_THEME)))

export function t(s: string, params?: Record<string, string | number | null | undefined>): string {
  let out = (lang.value === 'en' && en[s]) || s
  if (params) for (const [k, v] of Object.entries(params)) out = out.split(`{${k}}`).join(String(v ?? ""))
  return out
}

/** Locale für Datums- und Zahlenformate */
export const locale = () => (lang.value === 'en' ? 'en-GB' : 'de-DE')

const MON_DE = ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez']
const MONL_DE = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']
const WD_DE = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
const WDS_DE = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
const intl = (d: Date, o: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat('en-GB', { ...o, timeZone: 'UTC' }).format(d)
/** Kurzer Monatsname (i = 0..11) in der aktuellen Sprache */
export const monthShort = (i: number) => (lang.value === 'en' ? intl(new Date(Date.UTC(2000, i, 1)), { month: 'short' }) : MON_DE[i])
export const monthLong = (i: number) => (lang.value === 'en' ? intl(new Date(Date.UTC(2000, i, 1)), { month: 'long' }) : MONL_DE[i])
/** Wochentag (i = 0 = Montag) */
export const weekdayLong = (i: number) => (lang.value === 'en' ? intl(new Date(Date.UTC(2024, 0, 1 + i)), { weekday: 'long' }) : WD_DE[i])
export const weekdayShort = (i: number) => (lang.value === 'en' ? intl(new Date(Date.UTC(2024, 0, 1 + i)), { weekday: 'short' }) : WDS_DE[i])

export function setLang(l: Lang) { lang.value = l; write(LS_LANG, l); document.documentElement.lang = l }

export function setTheme(th: Theme) {
  theme.value = th; write(LS_THEME, th)
  if (th === 'auto') document.documentElement.removeAttribute('data-theme')
  else document.documentElement.setAttribute('data-theme', th)
}

/** Einstellungen des angemeldeten Benutzers übernehmen (null = Standard: Deutsch / Systemmodus). */
export function applyPrefs(p: { lang?: string | null; theme?: string | null }) {
  setLang(asLang(p.lang)); setTheme(asTheme(p.theme))
}

setLang(lang.value); setTheme(theme.value)

declare module 'vue' { interface ComponentCustomProperties { $t: typeof t } }
