import type { IntakeFields } from '../api/types'

export type PhraseKey = 'grade' | 'qty_t' | 'region' | 'deadline' | 'max_price_t'

const MONTHS = [
  'янв|yanv|jan', 'фев|fev|feb', 'мар|mart|mar', 'апр|apr', 'ма[яй]|may', 'июн|iyun|jun',
  'июл|iyul|jul', 'авг|avg|aug', 'сен|sent|sep', 'окт|okt|oct', 'ноя|noy|nov', 'дек|dek|dec',
]

const esc = (x: string) => x.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const numRe = (n: number) => String(Math.round(n)).split('').map(esc).join('[\\s\\u00a0\\u202f.,]?')

export function phrasePattern(k: PhraseKey, f: IntakeFields, regionLabel: string): RegExp | null {
  const v = f[k]
  if (v === null || v === undefined || v === '') return null
  if (k === 'qty_t' || k === 'max_price_t') return new RegExp(`(?<![\\d])${numRe(Number(v))}(?![\\d])`, 'i')
  if (k === 'grade') return v === '42.5' ? /[мm]\s?-?500|42[.,]5/i : /[мm]\s?-?400|32[.,]5/i
  if (k === 'deadline') {
    const m = /^\d{4}-(\d{2})-(\d{2})/.exec(String(v))
    if (!m) return null
    const day = String(+m[2])
    return new RegExp(`(?<![\\d])0?${day}(?:\\s*(?:${MONTHS[+m[1] - 1]})[\\p{L}]*|[./]${m[1]}(?:[./]\\d{2,4})?)`, 'iu')
  }
  if (k === 'region') {
    const stem = regionLabel.split(/\s/)[0].slice(0, 5)
    return stem.length >= 4 ? new RegExp(`${esc(stem)}[\\p{L}]*`, 'iu') : null
  }
  return null
}

