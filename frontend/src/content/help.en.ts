import { helpEnA } from './help.en.a'
import { helpEnB } from './help.en.b'
import { helpEnC } from './help.en.c'

/** Englischer Handbuchtext je Themen-ID (Titel, Kurzbeschreibung, HTML). Neue/geänderte Themen in help.ts hier nachziehen. */
export interface HelpText { title: string; summary: string; html: string }
export const helpEn: Record<string, HelpText> = { ...helpEnA, ...helpEnB, ...helpEnC }
