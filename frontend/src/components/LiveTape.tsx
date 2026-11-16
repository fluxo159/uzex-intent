import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { E } from '../lib/motion'
import { api } from '../api/client'
import type { Tape, TapeItem } from '../api/types'
import { useT } from '../i18n'
import { fmtNum } from '../lib/format'
import { Tx } from './Tx'

function minutesBetween(a: string, b: string): number {
  return Math.max(0, Math.round((Date.parse(b + (b.endsWith('Z') ? '' : 'Z')) - Date.parse(a + (a.endsWith('Z') ? '' : 'Z'))) / 60000))
}

export function LiveTape({ rows = 3, refreshKey, scroll = false }: { rows?: number; refreshKey?: unknown; scroll?: boolean }) {
  const t = useT()
  const [tape, setTape] = useState<Tape | null>(null)
  const [offset, setOffset] = useState(0)
  useEffect(() => {
    let alive = true
    const load = () => api.tape().then((x) => { if (alive) setTape(x) }).catch(() => undefined)
    load()
    const id = setInterval(() => { load(); setOffset((o) => o + 1) }, 7000)
    return () => { alive = false; clearInterval(id) }
  }, [refreshKey])
  if (!tape || tape.items.length === 0) return null
  const n = Math.min(rows, tape.items.length)
  const start = scroll ? 0 : tape.items.length > n ? offset % (tape.items.length - n + 1) : 0
  const shown = scroll ? tape.items : tape.items.slice(start, start + n)
  const who = (it: TapeItem) => (it.kind === 'mandate' ? (t(`region.${it.who}`) === `region.${it.who}` ? it.who : t(`region.${it.who}`)) : it.who)
  const ago = (it: TapeItem) => {
    const ref = tape.items.reduce((mx, x) => (x.at > mx ? x.at : mx), tape.now)
    const m = minutesBetween(it.at, ref)
    return m < 1 ? t('common.justNow') : m < 60 ? t('common.minAgo', { n: m }) : t('common.hAgo', { n: Math.round(m / 60) })
  }
  const seen = new Map<string, number>()
  const keyOf = (it: TapeItem) => {
    const base = `${it.kind}|${it.at}|${it.who}|${it.qty_t}|${it.status ?? ''}`
    const n = seen.get(base) ?? 0
    seen.set(base, n + 1)
    return `${base}#${n}`
  }
  return (
    <ul data-testid="live-tape" aria-live="polite" className="relative text-[12px] text-ink3 leading-[1.9]">
      <AnimatePresence initial={false} mode="popLayout">
      {shown.map((it) => (
        <motion.li key={keyOf(it)} layout="position" className="truncate"
          initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, transition: { duration: 0.2, ease: E } }} transition={{ duration: 0.3, ease: E }}>
          {it.kind === 'basket_closed' ? <span className="text-lime"><Tx k="tape.closed" vars={{ price: fmtNum(it.price_t), qty: fmtNum(it.qty_t) }} /></span> : <>
          {it.status ? <span className={it.status === 'filled' ? 'text-lime' : 'text-ink3'}>{it.status === 'filled' ? '●' : '○'} </span> : null}
          <b className="text-ink font-medium">{who(it)}</b>
          {' · '}
          {it.status === 'filled'
            ? <Tx k="tape.filled" vars={{ qty: fmtNum(it.qty_t) }} />
            : it.status === 'waiting'
              ? <Tx k="tape.waiting" vars={{ qty: fmtNum(it.qty_t) }} />
              : <><Tx k={it.kind === 'mandate' ? 'tape.mandate' : 'tape.offer'} vars={{ qty: fmtNum(it.qty_t) }} /> · {ago(it)}</>}
          </>}
        </motion.li>
      ))}
      </AnimatePresence>
    </ul>
  )
}
