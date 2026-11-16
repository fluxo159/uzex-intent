import type { ReactNode } from 'react'
import { fmtNum } from '../lib/format'

export function StruckPrices({ prices, single, topLabel, singleLabel, unit }: {
  prices: number[]; single: number | null; topLabel: ReactNode; singleLabel: ReactNode; unit?: ReactNode
}) {
  return (
    <div data-testid="struck-prices">
      <div className="caption">{topLabel}</div>
      <div className="mono flex flex-wrap gap-2 mt-2">
        {prices.map((p, i) => (
          <span key={i} className="bg-s1 text-mute rounded-chip px-[10px] py-[6px] text-[13px] line-through">{fmtNum(p)}</span>
        ))}
      </div>
      <div className="caption mt-[26px]">{singleLabel}</div>
      <div className="num-xl text-lime mt-[6px] anim-rise" style={{ fontSize: 46, lineHeight: 1 }}>{fmtNum(single)}</div>
      {unit ? <div className="caption mt-[6px]">{unit}</div> : null}
    </div>
  )
}
