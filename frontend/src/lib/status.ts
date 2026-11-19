import { t } from './i18n'
import type { Status } from './types'

/** Statuslabels sind Getter, damit sie bei Sprachwechsel neu ausgewertet werden. */
export const STATUS: { value: Status; readonly label: string }[] = [
  { value: 'open', get label() { return t('Offen') } },
  { value: 'in_progress', get label() { return t('In Arbeit') } },
  { value: 'blocked', get label() { return t('Blockiert') } },
  { value: 'done', get label() { return t('Erledigt') } },
]
export const STATUS_LABEL: Record<Status, string> = {
  get open() { return t('Offen') }, get in_progress() { return t('In Arbeit') }, get blocked() { return t('Blockiert') }, get done() { return t('Erledigt') },
}
