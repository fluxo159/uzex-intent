import type { ReactNode } from 'react'
import { CountUp } from '../lib/motion'

export function BigNumber({ label, value, unit, source, lime = false, size = 38, testId }: {
  label?: ReactNode; value: number | null | undefined; unit?: ReactNode; source?: ReactNode; lime?: boolean; size?: 38 | 46; testId?: string
}) {
  return (
    <div>
      {label ? <div className="caption">{label}</div> : null}
      <div data-testid={testId} className={`num-xl mt-1 ${lime ? 'text-lime' : 'text-ink'} anim-rise`} style={{ fontSize: size }}>
        <CountUp value={value} from0={lime} duration={lime ? 600 : 400} />
      </div>
      {unit ? <div className="caption mt-1">{unit}</div> : null}
      {source ? <div className="text-[11px] text-mute mt-1">{source}</div> : null}
    </div>
  )
}
