import type { IntakeFields } from '../api/types'
import { addDays, fmtTime, parseYmd } from './format'

type T = (k: string, v?: Record<string, string | number | null | undefined>) => string

const env = (import.meta as unknown as { env: Record<string, string | undefined> }).env ?? {}
function localIso(): string {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:00`
}
export const DEMO_NOW = env.VITE_DEMO_NOW || localIso()

export function windowWords(t: T, start: string | null | undefined, end: string | null | undefined): string {
  const p = parseYmd(start)
  if (!p || !start) return '—'
  const wd = new Date(Date.UTC(p.y, p.m - 1, p.d)).getUTCDay()
  return `${t(`wd.${wd}`)}, ${dateLong(t, start)}, ${fmtTime(start)}${end ? `–${fmtTime(end)}` : ''}`
}

export function dateLong(t: T, iso: string | null | undefined): string {
  const p = parseYmd(iso)
  return p ? t('day.on', { d: p.d, m: t(`month.${p.m}`) }) : '—'
}

export function dayWord(t: T, iso: string | null | undefined): string {
  if (!iso) return '—'
  const today = DEMO_NOW.slice(0, 10)
  const d = iso.slice(0, 10)
  if (d === today) return t('common.today')
  if (d === addDays(today, 1)) return t('common.tomorrow')
  return dateLong(t, d)
}

export function whenLabel(t: T, iso: string | null | undefined): string {
  return iso ? `${dayWord(t, iso)} ${fmtTime(iso)}` : '—'
}

export function regionName(t: T, code: string | null | undefined): string {
  if (!code) return '—'
  const k = `region.${code}`
  const v = t(k)
  return v === k ? code : v
}

export function commodityName(t: T, f: IntakeFields | null | undefined): string {
  if (!f?.commodity) return '—'
  const k = `commodity.${f.commodity}`
  const base = t(k) === k ? f.commodity : t(k)
  if (f.commodity === 'cement' && f.grade) return `${base} ${t(`gradeShort.${f.grade}`)}`
  return base
}

export function wdTime(t: T, iso: string | null | undefined): string {
  const p = parseYmd(iso)
  if (!p || !iso) return '—'
  const wd = new Date(Date.UTC(p.y, p.m - 1, p.d)).getUTCDay()
  return `${t(`wd.${wd}`)} ${fmtTime(iso)}`
}
