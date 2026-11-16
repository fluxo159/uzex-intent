import { useEffect, useState } from 'react'
import type { PlantDemand } from '../api/types'
import { useT } from '../i18n'
import { pluralForm } from '../lib/numwords'
import { fmtNum, parseYmd } from '../lib/format'
import { Tx } from './Tx'
import { AnimatePresence, motion } from 'motion/react'
import { E, NO_ANIM } from '../lib/motion'

export function DemandMap({ data }: { data: PlantDemand }) {
  const t = useT()
  const [packed, setPacked] = useState(false)
  useEffect(() => {
    setPacked(false)
    const id = setTimeout(() => setPacked(true), 900)
    return () => clearTimeout(id)
  }, [data.seller])
  if (!data.regions.length) return <p className="caption">{t('plant.empty')}</p>
  const date = (d: string | null) => {
    const p = parseYmd(d)
    return p ? `${p.d} ${t(`monthShort.${p.m}`)}` : '—'
  }
  return (
    <div data-testid="demand-map" className={`grid gap-4 ${data.regions.length >= 3 ? 'sm:grid-cols-2 lg:grid-cols-3' : data.regions.length === 2 ? 'sm:grid-cols-2' : ''}`}>
      {data.regions.map((r) => (
        <article key={r.region} className="bg-s2 rounded-card px-5 py-4">
          <div className="text-[15px] font-medium">
            {r.n_mandates < 0
              ? <Tx k="plant.regionSold" vars={{ region: t(`region.${r.region}`), qty: fmtNum(r.qty_t) }} />
              : <Tx k="plant.region" vars={{ region: t(`region.${r.region}`), qty: fmtNum(r.qty_t), n: fmtNum(r.n_mandates), date: date(r.deadline) }} />}
          </div>
          <div className="text-[13px] text-lime mt-1">
            {r.lots > 0
              ? <Tx k={r.rest_t ? 'plant.lots' : 'plant.lotsExact'} vars={{ lots: fmtNum(r.lots), lotsW: t(`plant.batch.${pluralForm(r.lots)}`), lot: fmtNum(data.min_lot_t), rest: fmtNum(r.rest_t) }} />
              : <span className="text-ink3"><Tx k="plant.lotsNone" vars={{ lot: fmtNum(data.min_lot_t), need: fmtNum(data.min_lot_t - r.qty_t) }} /></span>}
          </div>
          <div className="mt-3 relative flex flex-wrap gap-1 min-h-[22px]" aria-label={t('plant.compress')}>
            {}
            <AnimatePresence initial={false}>
              {packed && r.lots > 0 ? null : Array.from({ length: Math.min(Math.max(r.n_mandates, r.lots + (r.rest_t ? 1 : 0)), 12) }).map((_, i) => (
                <motion.span key={i} className="h-[22px] w-[22px] rounded-[6px] bg-s3"
                  exit={{ x: -i * 26, opacity: 0, transition: { duration: 0.5, delay: i * 0.03, ease: E } }} />
              ))}
            </AnimatePresence>
            {packed && r.lots > 0
              ? <motion.span className="absolute left-0 top-0 h-[22px] rounded-[6px] bg-lime" style={{ width: `${Math.min(100, 30 + r.lots * 30)}%`, transformOrigin: 'left center' }}
                initial={NO_ANIM ? false : { scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ duration: 0.4, delay: 0.4, ease: E }} />
              : null}
          </div>
        </article>
      ))}
    </div>
  )
}
