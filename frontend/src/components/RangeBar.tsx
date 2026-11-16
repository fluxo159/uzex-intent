import { useT } from '../i18n'
import { fmtNum } from '../lib/format'
import { Tx } from './Tx'

export function RangeBar({ from, to, cap }: { from: number | null | undefined; to: number | null | undefined; cap?: number | null }) {
  const t = useT()
  if (from == null || to == null || to <= from) return <p className="caption mt-3">{t('card.usuallyNone')}</p>
  const lo = Math.min(from, cap ?? from)
  const hi = Math.max(to, cap ?? to)
  const pad = (hi - lo) * 0.08
  const a = lo - pad
  const b = hi + pad
  const pos = (v: number) => ((v - a) / (b - a)) * 100
  return (
    <div className="mt-[14px]" data-testid="range-bar">
      <div className="relative h-1 rounded-[2px] bg-s3">
        <i className="absolute top-0 h-full bg-lime rounded-[2px]" style={{ left: `${pos(from)}%`, width: `${pos(to) - pos(from)}%` }} />
        {cap != null ? <i aria-hidden className="absolute -top-[4px] h-3 w-[2px] bg-ink rounded" style={{ left: `calc(${pos(cap)}% - 1px)` }} /> : null}
      </div>
      <div className="flex justify-between text-[11px] text-mute mt-[6px]">
        <span><Tx k="card.usually" vars={{ from: fmtNum(from) }} /></span>
        <span className="mono">{fmtNum(to)}</span>
      </div>
    </div>
  )
}
