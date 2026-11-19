/** Anzeige von Benutzern: Anzeigename (aus AD bzw. vom Admin gepflegt), sonst die Benutzer-ID. */
export interface Named { username: string; display_name?: string | null }

/** Kurzform für Beschriftungen: „Anna Müller“ bzw. „jdoe“. */
export const dname = (u?: Named | null): string => (u ? u.display_name || u.username : '')

/** Langform für Auswahllisten: „Anna Müller (jdoe)“ – so findet man beides per Suche. */
export const dfull = (u: Named): string => (u.display_name && u.display_name !== u.username ? `${u.display_name} (${u.username})` : u.username)
