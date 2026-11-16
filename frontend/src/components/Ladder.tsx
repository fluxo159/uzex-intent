import { useEffect, useRef, useState } from 'react'
import { motion, useReducedMotion } from 'motion/react'
import type { Ladder as LadderT, LadderBand } from '../api/types'
import { CountUp, E, NO_ANIM } from '../lib/motion'
import { useT } from '../i18n'
import { fmtNum } from '../lib/format'
import { Tx } from './Tx'
import { pluralForm } from '../lib/numwords'

type Phase = 'idle' | 'collapse' | 'line' | 'regrow'
const COLLAPSE_MS = 650
const LINE_MS = 400
const NUM_DELAY_MS = 300
const NUM_MS = 600

function BandRow({ b, side, p, maxQ, phase, edge, unit }: { b: LadderBand; side: 'demand' | 'supply'; p: number | null; maxQ: number; phase: Phase; edge: number; unit: string }) {
  const at = p !== null && b.price_from <= p && p < b.price_to
  const inDeal = p !== null && (side === 'demand' ? b.price_to > p : b.price_from <= p)
  const shut = phase === 'collapse' || phase === 'line'
  const greyOut = p !== null && !inDeal && !shut
  const prev = useRef(b.qty_t)
  const [flash, setFlash] = useState(0)
  useEffect(() => {
    if (prev.current === b.qty_t) return
    prev.current = b.qty_t
    const id = setTimeout(() => setFlash((x) => x + 1), 100)
    return () => clearTimeout(id)
  }, [b.qty_t])
  return (
    <li data-testid={`band-${side}`} className={`relative grid grid-cols-[52px_minmax(24px,1fr)_42px] gap-[6px] pl-1 sm:grid-cols-[72px_minmax(0,1fr)_56px] sm:gap-2 sm:pl-2 items-center h-6 rounded-[6px] ${at && !shut ? 'ring-1 ring-lime' : ''}`}>
      {flash ? <motion.span key={flash} aria-hidden className="absolute inset-0 rounded-[6px] bg-s3 pointer-events-none" initial={{ opacity: 1 }} animate={{ opacity: 0 }} transition={{ duration: 0.3, ease: E }} /> : null}
      <span className="relative mono text-[11px] sm:text-[12px] text-ink2 whitespace-nowrap">{fmtNum(b.price_from)}</span>
      <span className="relative h-full">
        <motion.span
          aria-hidden
          className={`absolute inset-y-1 rounded-[4px] ${side === 'demand' ? 'right-0' : 'left-0'}`}
          style={{ width: `${(b.qty_t / maxQ) * 100}%`, transformOrigin: side === 'demand' ? 'right center' : 'left center', background: greyOut ? 'var(--s3)' : side === 'demand' ? 'rgba(199,250,88,.28)' : 'rgba(180,185,174,.22)' }}
          initial={false}
          animate={{ scaleX: shut ? 0 : 1 }}
          transition={{ duration: shut ? 0.5 : 0.4, delay: edge * 0.03, ease: E }}
        />
      </span>
      <span className="relative mono text-[11px] sm:text-[12px] text-ink3 text-right pr-1 whitespace-nowrap">{fmtNum(b.qty_t)} {unit}</span>
    </li>
  )
}

function PriceLine({ draw }: { draw: boolean }) {
  return (
    <div aria-hidden className="flex w-full h-[2px] mb-2">
      {(['right center', 'left center'] as const).map((o) => (
        <motion.span key={o} className="flex-1 h-full bg-lime" style={{ transformOrigin: o }}
          initial={draw ? { scaleX: 0 } : false} animate={{ scaleX: 1 }} transition={{ duration: LINE_MS / 1000, delay: draw ? COLLAPSE_MS / 1000 : 0, ease: E }} />
      ))}
    </div>
  )
}

export function Ladder({ data, maxRows, centerNote, animateClose = false }: { data: LadderT; maxRows?: number; centerNote?: React.ReactNode; animateClose?: boolean }) {
  const t = useT()
  const reduce = useReducedMotion()
  const p = data.closed ? data.clearing_price_t : null
  const play = animateClose && p !== null && !reduce && !NO_ANIM
  const [phase, setPhase] = useState<Phase>(play ? 'collapse' : 'idle')
  const played = useRef(false)
  useEffect(() => {
    if (!play || played.current) return
    played.current = true
    setPhase('collapse')
    const a = setTimeout(() => setPhase('line'), COLLAPSE_MS)
    const b = setTimeout(() => setPhase('regrow'), COLLAPSE_MS + NUM_DELAY_MS + NUM_MS)
    return () => { clearTimeout(a); clearTimeout(b); played.current = false }
  }, [play])
  const pick = (bands: LadderBand[]) => {
    let b = [...bands]
    if (maxRows && b.length > maxRows) b = [...b].sort((x, y) => y.qty_t - x.qty_t).slice(0, maxRows)
    return b.sort((x, y) => y.price_from - x.price_from)
  }
  const dem = pick(data.bands_demand)
  const sup = pick(data.bands_supply)
  const maxQ = Math.max(1, ...dem.map((b) => b.qty_t), ...sup.map((b) => b.qty_t))
  const unit = t('common.t')
  const edge = (i: number, n: number) => Math.min(i, n - 1 - i)
  const ph: Phase = play && phase === 'idle' ? 'collapse' : phase
  const drawing = play
  return (
    <div data-testid="ladder" className="flex flex-col h-full min-h-0">
      <div className="grid grid-cols-2 gap-3 sm:gap-4 caption mb-1">
        <span>{t('lad.want')}</span>
        <span>{t('lad.sell')}</span>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:gap-4 min-h-0 overflow-y-auto">
        <ul className="flex flex-col gap-[2px]">{dem.map((b, i) => <BandRow key={`d${b.price_from}`} b={b} side="demand" p={p} maxQ={maxQ} phase={ph} edge={edge(i, dem.length)} unit={unit} />)}</ul>
        <ul className="flex flex-col gap-[2px]">{sup.map((b, i) => <BandRow key={`s${b.price_from}`} b={b} side="supply" p={p} maxQ={maxQ} phase={ph} edge={edge(i, sup.length)} unit={unit} />)}</ul>
      </div>
      <div className="mt-3 text-center shrink-0">
        {p !== null
          ? <>
            <PriceLine draw={drawing} />
            <p data-testid="ladder-price" className="text-[14px] text-lime"><Tx k="lad.oneForAll" vars={{ price: <CountUp className="mono" value={p} from0={drawing} duration={NUM_MS} delay={drawing ? COLLAPSE_MS + NUM_DELAY_MS : 0} /> }} /></p>
          </>
          : <p data-testid="ladder-unknown" className="text-[13px] text-ink3">{t('lad.unknown')}{centerNote ? <> · {centerNote}</> : null}</p>}
        <p className="caption mt-1"><Tx k="lad.totals" vars={{ bids: fmtNum(data.totals.bids), bidsW: t(`lad.buyers.${pluralForm(data.totals.bids ?? 0)}`), bid_t: fmtNum(data.totals.bid_t), asks: fmtNum(data.totals.asks), asksW: t(`lad.plants.${pluralForm(data.totals.asks ?? 0)}`), ask_t: fmtNum(data.totals.ask_t) }} /></p>
      </div>
    </div>
  )
}
