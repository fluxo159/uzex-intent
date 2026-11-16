import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { ChartPoint } from '../api/types'
import { useT } from '../i18n'
import { fmtNum, parseYmd } from '../lib/format'

export type ChartStyle = 'line' | 'candles'

interface Props {
  points: ChartPoint[]
  ours?: { date: string; price: number } | null
  height?: number
  bucket?: 'day' | 'week'
  style?: ChartStyle
  pinnedTip?: boolean
  onZoomReset?: (reset: (() => void) | null) => void
}

const M0 = { top: 8, right: 8, bottom: 22 }
const VOL_SHARE = 0.22
const MAX_SLOT = 48
const MIN_WINDOW = 8
const MINIMAP_H = 24

export function niceTicks(lo: number, hi: number, min = 5, exact?: number): number[] {
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return []
  if (hi <= lo) { hi = lo + 1; lo = lo - 1 }
  const mag = 10 ** Math.floor(Math.log10(hi - lo))
  const steps = [5, 2.5, 2, 1, 0.5, 0.25, 0.2, 0.1, 0.05, 0.025, 0.02, 0.01].map((m) => m * mag)
  if (exact) {
    const extra = [1.5, 0.75, 0.4, 0.3, 0.15].map((m) => m * mag)
    let best: number[] | null = null
    for (const s of [...steps, ...extra]) {
      const out: number[] = []
      for (let v = Math.ceil(lo / s) * s; v <= hi + 1e-6; v += s) out.push(Math.round(v))
      if (out.length >= exact - 1 && (!best || Math.abs(out.length - exact) < Math.abs(best.length - exact))) best = out
      if (best && best.length === exact) break
    }
    if (best && Math.abs(best.length - exact) <= 1) return best
  }
  for (const s of steps) {
    const out: number[] = []
    for (let v = Math.ceil(lo / s) * s; v <= hi + 1e-6; v += s) out.push(Math.round(v))
    if (out.length >= min) return out
  }
  return [lo, hi]
}

export const ddmm = (d: string) => {
  const p = parseYmd(d)
  return p ? `${String(p.d).padStart(2, '0')}.${String(p.m).padStart(2, '0')}` : d
}

function useSize<T extends HTMLElement>(): [React.RefObject<T>, { w: number; h: number }] {
  const ref = useRef<T>(null)
  const [size, setSize] = useState({ w: 0, h: 0 })
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const read = () => setSize({ w: el.clientWidth, h: el.clientHeight })
    read()
    if (typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(read)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, size]
}

const has = (p: ChartPoint) => p.vwap !== null && p.vwap !== undefined

export function PriceChart({ points, ours, height = 260, bucket = 'week', style = 'line', pinnedTip = false, onZoomReset }: Props) {
  const t = useT()
  const [ref, { w, h: hAll }] = useSize<HTMLDivElement>()
  const svgRef = useRef<SVGSVGElement>(null)
  const total = points.length
  const minN = Math.min(MIN_WINDOW, total)
  const [view, setView] = useState({ a: 0, n: total })
  const [hover, setHover] = useState<number | null>(null)
  useEffect(() => { setView({ a: 0, n: total }); setHover(null) }, [points, total])
  useEffect(() => setHover(null), [style])

  const clampView = useCallback((a: number, n: number) => {
    const nn = Math.max(minN, Math.min(total, Math.round(n)))
    const aa = Math.max(0, Math.min(total - nn, Math.round(a)))
    return { a: aa, n: nn }
  }, [minN, total])

  const tipH = pinnedTip ? 18 : 0
  const h = Math.max(0, hAll - (total > minN ? MINIMAP_H + 6 : 0) - tipH)

  const a = Math.min(view.a, Math.max(0, total - view.n))
  const n = Math.min(view.n, total)
  const vis = points.slice(a, a + n)
  const visFilled = vis.filter(has)

  const lowOf = (p: ChartPoint) => (style === 'candles' ? p.min ?? Math.min(p.open ?? p.vwap!, p.close ?? p.vwap!) : p.vwap!)
  const highOf = (p: ChartPoint) => (style === 'candles' ? p.max ?? Math.max(p.open ?? p.vwap!, p.close ?? p.vwap!) : p.vwap!)
  const oursIdx = ours ? points.findIndex((p) => p.date === ours.date) : -1
  const oursVisible = ours && oursIdx >= a && oursIdx < a + n
  const lo0 = Math.min(...(visFilled.length ? visFilled : points.filter(has)).map(lowOf), oursVisible ? ours.price : Infinity)
  const hi0 = Math.max(...(visFilled.length ? visFilled : points.filter(has)).map(highOf), oursVisible ? ours.price : -Infinity)
  const pad = Math.max((hi0 - lo0) * 0.05, hi0 * 0.01)
  const y0 = lo0 - pad
  const y1 = hi0 + pad
  const ticks = niceTicks(y0, y1, 5, pinnedTip ? 5 : undefined)

  const M = { ...M0, left: Math.ceil(Math.max(...ticks.map((v) => fmtNum(v).length), 3) * 6.7) + 14 }
  const plotW = Math.max(0, w - M.left - M.right)
  const plotH = Math.max(0, h - M.top - M.bottom)
  const priceH = plotH * (1 - VOL_SHARE * 0.35)
  const step = n ? Math.min(plotW / n, MAX_SLOT) : 0
  const x = (i: number) => M.left + step * (i - a + 0.5)
  const y = (v: number) => M.top + priceH - ((v - y0) / (y1 - y0 || 1)) * priceH
  const maxVol = Math.max(1, ...vis.map((p) => p.volume_t ?? 0))
  const volBase = M.top + plotH
  const volY = (v: number) => volBase - (v / maxVol) * plotH * VOL_SHARE
  const barW = Math.max(1, Math.min(step * 0.6, 10))
  const zoomed = n < total
  useEffect(() => { onZoomReset?.(zoomed ? () => setView({ a: 0, n: total }) : null) }, [zoomed, total, onZoomReset])

  const st = useRef({ view: { a, n }, step, left: M.left })
  st.current = { view: { a, n }, step, left: M.left }
  const ptrs = useRef(new Map<number, number>())
  const drag = useRef<{ x0: number; a0: number; d0?: number; n0?: number; c0?: number; moved: boolean } | null>(null)
  const lastTap = useRef(0)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      const svg = svgRef.current
      if (total <= minN || !svg) return
      e.preventDefault()
      const { view: v, step: s, left } = st.current
      const r = svg.getBoundingClientRect()
      const c = v.a + Math.max(0, Math.min(v.n, (e.clientX - r.left - left) / (s || 1)))
      const nn = v.n * (e.deltaY > 0 ? 1.15 : 1 / 1.15)
      const k = Math.max(minN, Math.min(total, nn)) / v.n
      setView(clampView(c - (c - v.a) * k, v.n * k))
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [total, minN, clampView, ref])

  const idxAt = (clientX: number) => {
    const r = svgRef.current?.getBoundingClientRect()
    if (!r) return null
    const i = a + Math.floor((clientX - r.left - M.left) / (step || 1))
    return i >= a && i < a + n ? i : null
  }
  const onDown = (e: React.PointerEvent<SVGSVGElement>) => {
    ptrs.current.set(e.pointerId, e.clientX)
    e.currentTarget.setPointerCapture?.(e.pointerId)
    if (ptrs.current.size === 2) {
      const [p1, p2] = [...ptrs.current.values()]
      const r = e.currentTarget.getBoundingClientRect()
      drag.current = { x0: 0, a0: a, d0: Math.abs(p1 - p2) || 1, n0: n, c0: a + ((p1 + p2) / 2 - r.left - M.left) / (step || 1), moved: true }
    } else {
      drag.current = { x0: e.clientX, a0: a, moved: false }
    }
  }
  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (ptrs.current.has(e.pointerId)) ptrs.current.set(e.pointerId, e.clientX)
    const d = drag.current
    if (d && ptrs.current.size === 2 && d.d0 && d.n0 && d.c0 !== undefined) {
      const [p1, p2] = [...ptrs.current.values()]
      const k = d.d0 / (Math.abs(p1 - p2) || 1)
      const nn = Math.max(minN, Math.min(total, d.n0 * k))
      setView(clampView(d.c0 - (d.c0 - d.a0) * (nn / d.n0), nn))
      setHover(null)
      return
    }
    if (d && ptrs.current.size === 1) {
      const dx = e.clientX - d.x0
      if (Math.abs(dx) > 4) d.moved = true
      if (d.moved && zoomed) { setView(clampView(d.a0 - dx / (step || 1), n)); setHover(null); return }
    }
    setHover(idxAt(e.clientX))
  }
  const onUp = (e: React.PointerEvent<SVGSVGElement>) => {
    ptrs.current.delete(e.pointerId)
    const d = drag.current
    if (ptrs.current.size === 0) {
      if (d && !d.moved && e.pointerType !== 'mouse') {
        const now = Date.now()
        if (now - lastTap.current < 300) { setView({ a: 0, n: total }); lastTap.current = 0 } else lastTap.current = now
      }
      drag.current = null
    }
  }

  const mini = (clientX: number, el: Element) => {
    const r = el.getBoundingClientRect()
    const c = ((clientX - r.left) / (r.width || 1)) * total
    setView(clampView(c - n / 2, n))
  }

  if (!points.some(has)) return <p className="text-[14px] text-ink3 py-8 text-center">{t('market.empty')}</p>

  const gaps: [number, number][] = []
  for (let i = a; i < a + n; i++) {
    if (has(points[i])) continue
    const last = gaps[gaps.length - 1]
    if (last && last[1] === i - 1) last[1] = i
    else gaps.push([i, i])
  }
  const line = vis.map((p, j) => (has(p) ? `${x(a + j).toFixed(1)},${y(p.vwap!).toFixed(1)}` : null)).filter(Boolean).join(' L')
  const every = Math.max(1, Math.ceil(52 / (step || 1)))
  const xTicks: number[] = []
  for (let i = a + n - 1; i >= a; i -= every) if (x(i) - 18 >= M.left && x(i) + 18 <= M.left + plotW) xTicks.push(i)

  const tipDate = (d: string) => {
    const p = parseYmd(d)
    const full = p ? `${ddmm(d)}.${String(p.y).slice(2)}` : d
    return bucket === 'week' ? t('market.tip.week', { date: full }) : t('market.tip.day', { date: full })
  }
  const hp = hover !== null ? points[hover] : null

  const allFilled = points.map((p, i) => [i, p.vwap] as const).filter(([, v]) => v !== null && v !== undefined) as [number, number][]
  const mLo = Math.min(...allFilled.map(([, v]) => v))
  const mHi = Math.max(...allFilled.map(([, v]) => v))
  const mx = (i: number) => ((i + 0.5) / total) * w
  const my = (v: number) => 3 + (1 - (v - mLo) / (mHi - mLo || 1)) * (MINIMAP_H - 6)
  const miniLine = allFilled.map(([i, v]) => `${mx(i).toFixed(1)},${my(v).toFixed(1)}`).join(' L')

  const tipBody = hp ? (
    has(hp) ? (
      <>
        <span className="text-ink">{tipDate(hp.date)}</span>{' · '}<span className="mono text-ink">{fmtNum(hp.vwap)}</span> {t('common.perT')}
        {style === 'candles' ? <>{' · '}<span className="mono">{fmtNum(hp.open ?? hp.vwap)} → {fmtNum(hp.close ?? hp.vwap)}</span></> : null}
        {hp.volume_t ? <>{' · '}<span className="mono">{fmtNum(hp.volume_t)}</span> {t('common.t')}</> : null}
      </>
    ) : <><span className="text-ink">{tipDate(hp.date)}</span>{' · '}{t('market.noDeals')}</>
  ) : null

  return (
    <div ref={ref} data-testid="price-chart" data-style={style} data-window={`${a}:${n}`} style={{ height: height ? height + tipH + (total > minN ? MINIMAP_H + 6 : 0) : '100%' }} className="relative w-full select-none flex flex-col">
      {pinnedTip ? <div data-testid="chart-tip-row" className="h-[18px] text-[11px] text-ink3 truncate">{tipBody}</div> : null}
      {w > 0 && h > 0 ? (
        <svg ref={svgRef} width={w} height={h} role="img" aria-label={t('mkt.chart')} style={{ touchAction: 'pan-y', cursor: zoomed ? 'grab' : 'default' }}
          onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp} onPointerLeave={() => setHover(null)}
          onDoubleClick={() => setView({ a: 0, n: total })}>
          {gaps.map(([g0, g1]) => (
            <rect key={`g${g0}`} data-gap x={M.left + step * (g0 - a)} y={M.top} width={step * (g1 - g0 + 1)} height={plotH} fill="var(--s1)" opacity={0.4} />
          ))}
          {ticks.map((v) => (
            <g key={v}>
              <line x1={M.left} x2={M.left + plotW} y1={y(v)} y2={y(v)} stroke="var(--line)" />
              <text x={M.left - 8} y={y(v) + 4} textAnchor="end" fontSize={11} fontFamily="Geist, system-ui, sans-serif" fill="var(--ink-3)">{fmtNum(v)}</text>
            </g>
          ))}
          {vis.map((p, j) => (p.volume_t ? <rect key={`v${a + j}`} x={x(a + j) - barW / 2} y={volY(p.volume_t)} width={barW} height={volBase - volY(p.volume_t)} fill="var(--s3)" /> : null))}
          {hover !== null ? <line x1={x(hover)} x2={x(hover)} y1={M.top} y2={volBase} stroke="var(--s3)" /> : null}
          {style === 'line'
            ? <path d={`M${line}`} fill="none" stroke="var(--chart-hist)" strokeWidth={1.5} strokeLinejoin="round" />
            : vis.map((p, j) => {
              if (!has(p)) return null
              const i = a + j
              const o = p.open ?? p.vwap!
              const c = p.close ?? p.vwap!
              const up = c >= o
              const col = up ? 'var(--lime)' : 'var(--mute)'
              const bw = Math.max(1, step * 0.6)
              return (
                <g key={`c${i}`} data-candle={up ? 'up' : 'down'}>
                  <line x1={x(i)} x2={x(i)} y1={y(p.max ?? Math.max(o, c))} y2={y(p.min ?? Math.min(o, c))} stroke={col} />
                  <rect x={x(i) - bw / 2} y={y(Math.max(o, c))} width={bw} height={Math.max(1, Math.abs(y(o) - y(c)))} fill={up ? 'var(--bg)' : 'var(--mute)'} stroke={col} strokeWidth={bw > 2 ? 1 : 0} />
                </g>
              )
            })}
          {ours && oursVisible ? (
            <path data-testid="chart-ours" d={`M${x(oursIdx)},${y(ours.price) - 6} l6,6 l-6,6 l-6,-6 Z`} fill="var(--chart-ours)" stroke="var(--bg)" strokeWidth={1.5} />
          ) : null}
          {xTicks.map((i) => (
            <text key={`x${i}`} x={x(i)} y={h - 6} textAnchor="middle" fontSize={11} fontFamily="Geist, system-ui, sans-serif" fill="var(--ink-3)">{ddmm(points[i].date)}</text>
          ))}
        </svg>
      ) : <div className="flex-1" />}
      {w > 0 && total > minN ? (
        <svg data-testid="chart-minimap" width={w} height={MINIMAP_H} className="mt-[6px] cursor-pointer" style={{ touchAction: 'none' }}
          onPointerDown={(e) => { e.currentTarget.setPointerCapture?.(e.pointerId); mini(e.clientX, e.currentTarget) }}
          onPointerMove={(e) => { if (e.buttons) mini(e.clientX, e.currentTarget) }}>
          <rect x={0} y={0} width={w} height={MINIMAP_H} rx={6} fill="var(--s1)" />
          <path d={`M${miniLine}`} fill="none" stroke="var(--mute)" strokeWidth={1} />
          <rect x={(a / total) * w} y={0.5} width={Math.max(4, (n / total) * w)} height={MINIMAP_H - 1} rx={6} fill="rgba(199,250,88,.08)" stroke="var(--lime)" strokeWidth={1} />
        </svg>
      ) : null}
      {!pinnedTip && hp && hover !== null ? (
        <div className="absolute pointer-events-none bg-s1 rounded-chip px-3 py-2 text-[12px] text-ink3 whitespace-nowrap z-10"
          style={{ top: M.top, ...(x(hover) > w / 2 ? { right: w - x(hover) + 10 } : { left: x(hover) + 10 }) }}>
          <div className="text-ink">{tipDate(hp.date)}</div>
          {has(hp) ? (
            <>
              <div><span className="mono text-ink">{fmtNum(hp.vwap)}</span> {t('common.perT')}</div>
              {style === 'candles' ? <div className="mono">{fmtNum(hp.open ?? hp.vwap)} → {fmtNum(hp.close ?? hp.vwap)}</div> : null}
              {hp.volume_t ? <div><span className="mono">{fmtNum(hp.volume_t)}</span> {t('common.t')} · <span className="mono">{fmtNum(hp.n_deals)}</span> {t('market.deals')}</div> : null}
            </>
          ) : <div>{t('market.noDeals')}</div>}
        </div>
      ) : null}
    </div>
  )
}
