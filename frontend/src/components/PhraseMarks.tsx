import { motion } from 'motion/react'
import type { IntakeFields } from '../api/types'
import { E } from '../lib/motion'
import { phrasePattern } from '../lib/phrase'

import type { PhraseKey as Key } from '../lib/phrase'
export const FIELD_ORDER: Key[] = ['grade', 'qty_t', 'deadline', 'region', 'max_price_t']
export const FIELD_STAGGER = 0.08

export function PhraseMarks({ text, fields, keys, regionLabel, className }: {
  text: string; fields: IntakeFields; keys: Set<Key>; regionLabel: string; className: string
}) {
  const ranges: { a: number; b: number; i: number }[] = []
  FIELD_ORDER.forEach((k, i) => {
    if (!keys.has(k)) return
    const re = phrasePattern(k, fields, regionLabel)
    if (!re) return
    const m = re.exec(text)
    if (!m || !m[0].trim()) return
    const a = m.index
    const b = a + m[0].length
    if (ranges.some((r) => a < r.b && b > r.a)) return
    ranges.push({ a, b, i })
  })
  if (!ranges.length) return null
  ranges.sort((x, y) => x.a - y.a)
  const parts: React.ReactNode[] = []
  let at = 0
  for (const r of ranges) {
    if (r.a > at) parts.push(text.slice(at, r.a))
    parts.push(
      <motion.span key={r.a} style={{ textDecorationLine: 'underline', textUnderlineOffset: 3, textDecorationThickness: 2 }}
        initial={{ textDecorationColor: 'rgba(199,250,88,0)' }} animate={{ textDecorationColor: 'rgba(199,250,88,1)' }}
        transition={{ duration: 0.25, delay: r.i * FIELD_STAGGER, ease: E }}>
        {text.slice(r.a, r.b)}
      </motion.span>,
    )
    at = r.b
  }
  if (at < text.length) parts.push(text.slice(at))
  return <div aria-hidden className={`${className} absolute inset-0 pointer-events-none whitespace-pre-wrap break-words text-transparent`}>{parts}</div>
}
