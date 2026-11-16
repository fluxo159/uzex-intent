import { useCallback, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { api } from '../api/client'
import type { Chart, MyOrder, OrderStatus } from '../api/types'
import { minutesUntil, useMyOrders, useNow } from '../app/hooks'
import { leftText } from '../app/Shell'
import { useAuth } from '../app/auth'
import { useStore, useViewport, type Instrument } from '../app/store'
import { Badge } from '../components/Badge'
import { Ladder } from '../components/Ladder'
import { PillButton } from '../components/PillButton'
import { PriceChart, type ChartStyle } from '../components/PriceChart'
import { ErrorBox, Loading } from '../components/States'
import { Tx } from '../components/Tx'
import { useLang } from '../i18n'
import { fmtNum, fmtSignedPct, shortId } from '../lib/format'
import { dayWord, regionName, wdTime } from '../lib/labels'
import { useAsync } from '../lib/useAsync'
import { CountUp, E } from '../lib/motion'
import { motion, stagger } from 'motion/react'
import { pluralForm } from '../lib/numwords'

export const MIN_REF_DEALS = 10

function basisDate(b: unknown): string | null {
  const s = typeof b === 'string' ? b : b && typeof b === 'object' ? String((b as Record<string, unknown>).date ?? (b as Record<string, unknown>).prev_date ?? (b as Record<string, unknown>).week ?? '') : ''
  return /^\d{4}-\d{2}-\d{2}/.test(s) ? s.slice(0, 10) : null
}

export function weekStats(c: Chart | null): { price: number | null; pct: number | null; basis: string | null } {
  const h = c?.headline
  if (h) return { price: h.last_vwap, pct: h.change_pct, basis: h.change_pct === null ? null : basisDate(h.prev_from) ?? basisDate(h.basis) }
  const pts = (c?.points ?? []).filter((p) => p.vwap !== null)
  const last = pts[pts.length - 1]
  if (!last) return { price: null, pct: null, basis: null }
  const ref = [...pts.slice(0, -1)].reverse().find((p) => (p.n_deals ?? 0) >= MIN_REF_DEALS)
  if (!ref || !ref.vwap) return { price: last.vwap, pct: null, basis: null }
  return { price: last.vwap, pct: ((last.vwap! - ref.vwap) / ref.vwap) * 100, basis: ref.date }
}

export function InstrumentList({ compact = false }: { compact?: boolean }) {
  const { t } = useLang()
  const { instrument, setInstrument, basket, tick } = useStore()
  const c32 = useAsync(() => api.chart('32.5', null, 'week'), [])
  const c42 = useAsync(() => api.chart('42.5', null, 'week'), [])
  const ai = useAsync(() => api.ai92(), [tick])
  const rows: { k: Instrument; name: string; sub: string; price: number | null; pct: number | null; basis: string | null; label: string; win: string; vol: string }[] = [
    { k: '32.5', name: t('instr.cement32'), sub: t('instr.sub32'), ...weekStats(c32.data), label: '', win: basket ? wdTime(t, basket.open_time ?? basket.close_time) : '—', vol: basket ? t(`mkt.inBasket.${pluralForm(basket.n_buyers ?? 0)}`, { n: basket.n_buyers, t: fmtNum(basket.demand_t) }) : '—' },
    { k: '42.5', name: t('instr.cement42'), sub: t('instr.sub42'), ...weekStats(c42.data), label: '', win: '—', vol: t('mkt.noBasket') },
    { k: 'ai92', name: t('instr.ai92'), sub: t('instr.subAi92'), price: ai.data?.uniform_price_t ?? null, pct: null, basis: null, label: t('mkt.uniform'), win: '—', vol: t('mkt.noBasket') },
  ]
  const shown = compact ? rows.filter((r) => r.k === instrument) : rows
  return (
    <ul data-testid="instrument-list" className="flex flex-col gap-4">
      {shown.map((r) => {
        const active = instrument === r.k && !compact
        return (
          <li key={r.k}>
            <button type="button" onClick={() => setInstrument(r.k)} aria-pressed={instrument === r.k}
              className={`focus-ring w-full text-left rounded-card px-5 py-4 transition-colors ${active ? 'bg-s3' : 'bg-s2 hover:bg-[#1d211b]'}`}>
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-[14px] font-medium truncate">{r.name} <span className="text-ink3 text-[12px] font-normal">{r.sub}</span></span>
                {r.pct !== null ? <span className={`mono text-[12px] shrink-0 ${r.pct >= 0 ? 'text-lime' : 'text-bad'}`}>{fmtSignedPct(r.pct)}</span> : null}
              </div>
              <div className="flex items-baseline justify-between gap-2 mt-1">
                <CountUp className="mono text-[20px] font-bold tracking-[-0.03em]" value={r.price} />
                {r.basis ? <span className="text-[11px] text-mute shrink-0">{t('mkt.vs', { date: `${r.basis.slice(8, 10)}.${r.basis.slice(5, 7)}` })}</span> : null}
              </div>
              <div className="flex justify-between gap-2 text-[11px] text-mute mt-1">
                <span data-testid={`instr-label-${r.k}`} className="shrink-0">{r.label || t('mkt.weekAvg')}</span>
                <span className="truncate text-right">{r.win !== '—' ? `${r.win} · ` : ''}{r.vol}</span>
              </div>
            </button>
          </li>
        )
      })}
    </ul>
  )
}

export function NoBasket() {
  const { t } = useLang()
  const { basket, setInstrument } = useStore()
  const at = basket?.open_time ?? basket?.close_time
  return (
    <div data-testid="no-basket" className="bg-s2 rounded-card px-5 py-4 shrink-0 flex items-center justify-between gap-3 flex-wrap">
      <p className="text-[14px] text-ink3">{t('lad.empty')}</p>
      {at ? <button type="button" className="link focus-ring" onClick={() => setInstrument('32.5')}>{t('lad.nearest', { when: wdTime(t, at) })} ↗</button> : null}
    </div>
  )
}

function usePersisted<T extends string>(key: string, allowed: readonly T[], d: T): [T, (v: T) => void] {
  const [v, setV] = useState<T>(() => {
    try { const x = localStorage.getItem(key) as T | null; return x && allowed.includes(x) ? x : d } catch { return d }
  })
  const set = (x: T) => { setV(x); try { localStorage.setItem(key, x) } catch {} }
  return [v, set]
}

function Seg<T extends string>({ items, value, onChange, label }: { items: readonly T[]; value: T; onChange: (v: T) => void; label: (v: T) => string }) {
  return (
    <div role="group" className="flex items-center gap-1 bg-s1 rounded-full p-[2px]">
      {items.map((b) => (
        <button key={b} type="button" aria-pressed={value === b} onClick={() => onChange(b)}
          className={`tap focus-ring rounded-full px-3 py-[3px] text-[12px] ${value === b ? 'bg-s3 text-ink' : 'text-mute hover:text-ink3'}`}>{label(b)}</button>
      ))}
    </div>
  )
}

function Ai92Marks() {
  const { t, lang } = useLang()
  const ai = useAsync(() => api.ai92(), [])
  if (!ai.data) return ai.loading ? <Loading /> : <ErrorBox detail={ai.error} onRetry={ai.reload} />
  const prices = [...ai.data.prices].sort((a, b) => b - a)
  const lo = Math.min(...prices)
  const hi = Math.max(...prices)
  const pos = (v: number) => (hi === lo ? 50 : 8 + ((hi - v) / (hi - lo)) * 84)
  return (
    <div data-testid="ai92-panel" className="flex flex-col h-full min-h-0">
      {}
      <motion.div className="relative flex-1 min-h-[160px]" initial="all" animate="one" variants={{ all: {}, one: { transition: { delayChildren: stagger(0.06) } } }}>
        {prices.map((v, i) => {
          const one = v === ai.data!.uniform_price_t
          return (
            <motion.div key={i} data-testid="ai92-mark" className="absolute inset-x-0 flex items-center gap-3" style={{ top: `${pos(v)}%`, y: '-50%', transformOrigin: 'left center' }}
              variants={{ all: { opacity: 1, scale: 1 }, one: one ? { opacity: 1, scale: 1 } : { opacity: 0.5, scale: 0.92, transition: { duration: 0.4, ease: E } } }}>
              <span className={`mono text-[12px] w-[96px] text-right ${one ? 'text-lime' : 'text-ink3'}`}>{fmtNum(v)}</span>
              <span className={`h-[2px] flex-1 rounded-full ${one ? 'bg-lime' : 'bg-mute'}`} />
            </motion.div>
          )
        })}
      </motion.div>
      <motion.p className="text-[14px] mt-3" data-testid="ai92-overpay" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.06 * prices.length + 0.3, ease: E }}><Tx k="market.ai92.overpay" vars={{ sum: <CountUp className="mono" value={ai.data.overpay} from0 duration={600} delay={(0.06 * prices.length + 0.3) * 1000} /> }} /> <span className="text-ink3">· {lang === 'uz' ? ai.data.caption_uz : ai.data.caption_ru}</span></motion.p>
      <p className="text-[12px] text-mute mt-1" data-testid="ai92-source">{t('market.ai92.only')} · {lang === 'uz' ? ai.data.source_label_uz ?? ai.data.source : ai.data.source_label_ru ?? ai.data.source}</p>
    </div>
  )
}

export function ChartPanel({ height = 260 }: { height?: number }) {
  const { t } = useLang()
  const { instrument, runs } = useStore()
  const vp = useViewport()
  const [bucket, setBucket] = usePersisted('intent.chart.bucket', ['week', 'day'] as const, 'week')
  const [style, setStyle] = usePersisted<ChartStyle>('intent.chart.style', ['line', 'candles'] as const, 'line')
  const grade = instrument === '42.5' ? '42.5' : '32.5'
  const chart = useAsync(() => api.chart(grade, null, bucket), [grade, bucket])
  const [zoomReset, setZoomReset] = useState<(() => void) | null>(null)
  const onZoomReset = useCallback((r: (() => void) | null) => setZoomReset(() => r), [])
  const pts = chart.data?.points ?? []
  const lastRun = Object.values(runs).sort((a, b) => ((a.closed_at ?? '') < (b.closed_at ?? '') ? 1 : -1))[0]
  const ours = grade === '32.5' && lastRun?.clearing_price_t && pts.length ? { date: pts[pts.length - 1].date, price: lastRun.clearing_price_t } : null
  const head = (
    <div className="flex items-center justify-between gap-2 mb-2 flex-wrap">
      <h2 className="text-[13px] text-ink3">{instrument === 'ai92' ? `${t('instr.ai92')} · 06.11.2026` : t('mkt.chart')}</h2>
      {instrument === 'ai92' ? null : (
        <div className="flex items-center gap-2 flex-wrap">
          {zoomReset ? (
            <button type="button" data-testid="chart-all" onClick={zoomReset} className="tap focus-ring rounded-full bg-s1 px-3 py-[3px] text-[12px] text-ink3 hover:text-ink">{t('market.all')}</button>
          ) : null}
          <Seg items={['week', 'day'] as const} value={bucket} onChange={setBucket} label={(b) => t(`market.bucket.${b}`)} />
          <Seg items={['line', 'candles'] as const} value={style} onChange={setStyle} label={(b) => t(`market.style.${b}`)} />
        </div>
      )}
    </div>
  )
  if (instrument === 'ai92') return <div className="flex flex-col h-full min-h-0">{head}<Ai92Marks /></div>
  return (
    <div className="flex flex-col h-full min-h-0">
      {head}
      <div className="flex-1 min-h-0">
        {chart.loading && !chart.data ? <Loading /> : chart.error ? <ErrorBox detail={chart.error} onRetry={chart.reload} /> : <PriceChart points={pts} ours={ours} height={height} bucket={bucket} style={style} pinnedTip={vp !== 'desktop'} onZoomReset={onZoomReset} />}
      </div>
      <div className="flex flex-wrap gap-x-4 text-[11px] text-mute mt-2">
        {style === 'line'
          ? <span><span className="inline-block w-3 h-[2px] bg-mute align-middle mr-1" />{t(bucket === 'week' ? 'market.vwap' : 'market.vwapDay')}</span>
          : <span><span className="inline-block w-[6px] h-[10px] border border-lime align-middle mr-1" /><span className="inline-block w-[6px] h-[10px] bg-mute align-middle mr-1" />{t(bucket === 'week' ? 'market.candleWeek' : 'market.candleDay')}</span>}
        <span><span className="inline-block w-[6px] h-[8px] bg-s3 align-middle mr-1" />{t(bucket === 'week' ? 'market.volume' : 'market.volumeDay')}</span>
        <span><span className="inline-block w-3 h-[10px] bg-s1 border border-mute align-middle mr-1" />{t('market.noDeals')}</span>
        {ours ? <span><span className="text-lime">◆</span> {t('market.ours')}</span> : null}
      </div>
    </div>
  )
}

export function LadderPanel({ maxRows }: { maxRows?: number }) {
  const { t } = useLang()
  const { instrument, basket, account, addRun, bump, refreshBasket, tick } = useStore()
  const { me } = useAuth()
  const [tab, setTab] = useState<'this' | 'past'>('this')
  const [closing, setClosing] = useState(false)
  const [closedId, setClosedId] = useState<string | null>(null)
  const [justClosed, setJustClosed] = useState(false)
  const [err, setErr] = useState<unknown>(null)
  const lad = useAsync(() => api.ladder(closedId ?? 'open'), [tick, closedId, basket?.basket_id, basket?.status])
  const hist = useAsync(() => api.history('32.5'), [tick, tab])
  const now = useNow(30000)
  const left = minutesUntil(basket?.close_time, now)
  const close = async () => {
    if (!basket) return
    setClosing(true)
    setErr(null)
    try {
      const r = await api.runClearing(basket.basket_id)
      addRun({ ...r, closed_at: r.closed_at ?? basket.close_time })
      setJustClosed(true)
      setClosedId(r.basket_id || basket.basket_id)
      refreshBasket()
      bump()
    } catch (e) { setErr(e) } finally { setClosing(false) }
  }
  if (instrument !== '32.5') return <p className="caption py-6 text-center">{t('lad.empty')}</p>
  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
        <div role="tablist" className="flex gap-1">
          {(['this', 'past'] as const).map((k) => (
            <button key={k} role="tab" type="button" aria-selected={tab === k} onClick={() => setTab(k)}
              className={`tap focus-ring rounded-full px-3 py-1 text-[12px] whitespace-nowrap ${tab === k ? 'bg-ink text-bg' : 'bg-s3 text-ink3'}`}>{t(`lad.${k}`)}</button>
          ))}
        </div>
        {tab === 'this' && closedId ? (
          <button type="button" className="link text-[12px]" onClick={() => { setJustClosed(false); setClosedId(null) }} data-testid="next-basket">{t('lad.next')} ↗</button>
        ) : tab === 'this' && (account.door !== 'guest' || me.level === 'admin') && me.can_close_basket && basket?.status !== 'closed' ? (
          <span className="flex items-center gap-2">
            <Badge kind="demo" />
            <PillButton block={false} variant="ghost" className="!py-1 !px-3 !text-[12px] whitespace-nowrap tap" disabled={closing} onClick={close} data-testid="close-basket">{closing ? t('common.loading') : t('wait.close')}</PillButton>
          </span>
        ) : null}
      </div>
      {err ? <ErrorBox detail={err} /> : null}
      {tab === 'this' ? (
        lad.data ? <Ladder data={lad.data} maxRows={maxRows} animateClose={justClosed} centerNote={left !== null ? t('lad.closesIn', { left: leftText(t, left) }) : null} /> : lad.loading ? <Loading /> : <ErrorBox detail={lad.error} onRetry={lad.reload} />
      ) : (
        <div className="overflow-auto">
          {hist.data && hist.data.length ? (
            <table data-testid="past-baskets" className="w-full text-[12px]">
              <thead className="text-mute text-left"><tr>
                <th className="font-normal py-1">{t('past.date')}</th><th className="font-normal">{t('past.window')}</th><th className="font-normal text-right">{t('past.price')}</th>
                <th className="font-normal text-right">{t('past.qty')}</th><th className="font-normal text-right">{t('past.buyers')}</th><th className="font-normal text-right">{t('past.plants')}</th><th />
              </tr></thead>
              <tbody>
                {hist.data.map((h) => (
                  <tr key={h.run_id} className="border-t border-line">
                    <td className="py-1">{dayWord(t, h.date)}</td><td className="mono">{h.window ?? '—'}</td>
                    <td className="mono text-right">{fmtNum(h.clearing_price_t)}</td><td className="mono text-right">{fmtNum(h.executed_qty_t)}</td>
                    <td className="mono text-right">{fmtNum(h.n_bids)}</td><td className="mono text-right">{fmtNum(h.n_asks)}</td>
                    <td className="text-right">{h.demo ? <Badge kind="demo" /> : null}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p className="caption py-4">{t('past.empty')}</p>}
        </div>
      )}
    </div>
  )
}

export const STATUS_KIND: Record<OrderStatus, 'waiting' | 'filled' | 'partial' | 'unfilled' | 'demo'> = {
  in_basket: 'waiting', filled: 'filled', partial: 'partial', unfilled: 'demo', expired: 'waiting',
}
export function StatusPill({ s }: { s: OrderStatus }) {
  const { t } = useLang()
  return <Badge kind={STATUS_KIND[s]} text={t(`st.${s}`)} testId={`status-${s}`} />
}

export function OrderRow({ o, compact = false }: { o: MyOrder; compact?: boolean }) {
  const { t } = useLang()
  const loc = useLocation()
  const vp = useViewport()
  const to = vp === 'desktop' ? `${loc.pathname}?order=${encodeURIComponent(o.mandate_id)}` : `/orders/${encodeURIComponent(o.mandate_id)}`
  return (
    <Link to={to} className="focus-ring block bg-s2 rounded-[16px] px-4 py-3 hover:bg-[#1d211b]" data-testid="order-row">
      <div className="flex items-center justify-between gap-2">
        <span className="mono text-[12px] text-ink3">№ {shortId(o.mandate_id)}</span>
        <StatusPill s={o.status} />
      </div>
      <div className="text-[13px] mt-1 truncate">
        <Tx k="card.head" vars={{ commodity: <>{t('commodity.cement')} {o.grade ? t(`gradeShort.${o.grade}`) : ''}</>, qty: fmtNum(o.qty_t) }} />
        {compact ? null : <> · {regionName(t, o.region)}</>}
      </div>
    </Link>
  )
}

export function RecentOrders({ n = 3 }: { n?: number }) {
  const { t } = useLang()
  const { orders } = useMyOrders()
  if (!orders.length) return null
  return (
    <div data-testid="recent-orders">
      <div className="flex items-baseline justify-between mb-2">
        <h2 className="text-[13px] text-ink3">{t('order.recent')}</h2>
        <Link to="/orders" className="link focus-ring">{t('order.all')} ↗</Link>
      </div>
      <div className="flex flex-col gap-2">{orders.slice(0, n).map((o) => <OrderRow key={o.mandate_id} o={o} compact />)}</div>
    </div>
  )
}
