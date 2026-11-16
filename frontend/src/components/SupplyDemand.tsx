import { useT } from '../i18n'

export function SupplyDemand({ demand, supply, price }: { demand: [number, number][]; supply: [number, number][]; price: number | null }) {
  const t = useT()
  if (!demand.length || !supply.length) return null
  const W = 320
  const H = 160
  const ps = [...demand.map((d) => d[0]), ...supply.map((s) => s[0])]
  const qs = [...demand.map((d) => d[1]), ...supply.map((s) => s[1])]
  const pMin = Math.min(...ps)
  const pMax = Math.max(...ps)
  const py = (p: number) => H - 8 - ((Math.log(p) - Math.log(pMin)) / (Math.log(pMax) - Math.log(pMin) || 1)) * (H - 16)
  const qMax = Math.max(...qs, 1)
  const qx = (q: number) => 8 + (q / qMax) * (W - 16)
  const step = (pts: [number, number][]) => {
    const s = [...pts].sort((a, b) => a[0] - b[0])
    let d = `M ${qx(s[0][1])} ${py(s[0][0])}`
    for (let i = 1; i < s.length; i++) {
      d += ` V ${py(s[i][0])} H ${qx(s[i][1])}`
    }
    return d
  }
  let cross: { x: number; y: number } | null = null
  if (price !== null) {
    const at = (pts: [number, number][]) => [...pts].sort((a, b) => a[0] - b[0]).filter((x) => x[0] <= price).pop()?.[1] ?? 0
    cross = { x: qx(Math.min(at(demand), at(supply))), y: py(price) }
  }
  return (
    <figure data-testid="supply-demand">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label={t('why.chart')}>
        <line x1="8" y1={H - 8} x2={W - 8} y2={H - 8} stroke="var(--s3)" />
        <line x1="8" y1="8" x2="8" y2={H - 8} stroke="var(--s3)" />
        <path d={step(demand)} fill="none" stroke="var(--ink-3)" strokeWidth="2" />
        <path d={step(supply)} fill="none" stroke="var(--mute)" strokeWidth="2" strokeDasharray="4 3" />
        {cross ? <circle cx={cross.x} cy={cross.y} r="6" fill="var(--lime)" stroke="var(--bg)" strokeWidth="2" /> : null}
      </svg>
      <figcaption className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-mute mt-1">
        <span><span className="inline-block w-3 h-[2px] bg-ink3 align-middle mr-1" />{t('why.chart.demand')}</span>
        <span><span className="inline-block w-3 h-[2px] bg-mute align-middle mr-1" />{t('why.chart.supply')}</span>
        <span><span className="inline-block w-2 h-2 rounded-full bg-lime align-middle mr-1" />{t('why.chart.cross')}</span>
      </figcaption>
    </figure>
  )
}
