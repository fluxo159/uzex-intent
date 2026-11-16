import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { motion } from 'motion/react'
import { E } from '../lib/motion'
import { ArrowLeft } from 'lucide-react'
import type { MyOrder } from '../api/types'
import { useMyOrders } from '../app/hooks'
import { useViewport } from '../app/store'
import { Loading } from '../components/States'
import { OrderDetails } from '../features/OrderDetails'
import { OrderRow, StatusPill } from '../features/MarketParts'
import { useT } from '../i18n'
import { fmtNum, shortId } from '../lib/format'
import { dayWord, regionName } from '../lib/labels'
import { pluralForm } from '../lib/numwords'

type Filter = 'all' | 'active' | 'done'
const ACTIVE = new Set(['in_basket'])
const GRID = 'grid grid-cols-[110px_minmax(0,1fr)_90px_160px_130px_200px_140px] gap-x-6'
const AFTER_NUM = new Set(['region', 'basket'])
const COLS: [string, 'l' | 'r'][] = [['no', 'l'], ['commodity', 'l'], ['qty', 'r'], ['region', 'l'], ['cap', 'r'], ['basket', 'l'], ['status', 'l']]

function filterOrders(list: MyOrder[], f: Filter) {
  if (f === 'active') return list.filter((o) => ACTIVE.has(o.status))
  if (f === 'done') return list.filter((o) => o.status === 'filled' || o.status === 'partial')
  return list
}

export function OrdersScreen() {
  const t = useT()
  const nav = useNavigate()
  const vp = useViewport()
  const { id } = useParams()
  const { orders, loading } = useMyOrders()
  const [f, setF] = useState<Filter>('all')
  const list = filterOrders(orders, f)
  const doneT = list.filter((o) => o.status === 'filled' || o.status === 'partial').reduce((a, o) => a + (o.filled_t ?? (o.status === 'filled' ? o.qty_t ?? 0 : 0)), 0)
  const total = t(`orders.total.${pluralForm(list.length)}`, { n: list.length, t: fmtNum(doneT) })
  const sel = id ? orders.find((o) => o.mandate_id === id) ?? null : null

  if (id && vp !== 'desktop') {
    return (
      <motion.div className="pt-3" initial={{ opacity: 0, y: typeof window === 'undefined' ? 400 : window.innerHeight * 0.6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, ease: E }}>
        <button type="button" onClick={() => nav('/orders')} className="link tap inline-flex items-center gap-1 mb-3 h-11"><ArrowLeft size={16} strokeWidth={1.75} />{t('detail.back')}</button>
        {sel ? <OrderDetails order={sel} /> : loading ? <Loading /> : <p className="caption">{t('notfound.title')}</p>}
      </motion.div>
    )
  }

  const filters = (
    <div role="tablist" className="flex gap-1">
      {(['all', 'active', 'done'] as const).map((k) => (
        <button key={k} role="tab" type="button" aria-selected={f === k} onClick={() => setF(k)}
          className={`tap focus-ring rounded-full px-3 py-1 text-[12px] ${f === k ? 'bg-ink text-bg' : 'bg-s3 text-ink3'}`}>{t(`orders.f.${k}`)}</button>
      ))}
    </div>
  )

  return (
    <div className={vp === 'desktop' ? 'relative h-full p-6 overflow-y-auto' : 'pt-4'}>
      <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
        <h1 className="h-page">{t('orders.title')}</h1>
        {filters}
      </div>
      {loading && !orders.length ? <Loading /> : null}
      {!loading && !list.length ? <p className="caption" data-testid="orders-empty">{t('orders.empty')}</p> : null}
      {vp === 'desktop' && list.length ? (
        <div data-testid="orders-table" role="table" className="text-[13px]">
          <div role="row" className={`${GRID} text-[12px] text-mute h-9 items-center border-b border-line`}>
            {COLS.map(([c, align]) => <span key={c} role="columnheader" className={align === 'r' ? 'text-right' : AFTER_NUM.has(c) ? 'pl-4' : ''}>{t(`col.${c}`)}</span>)}
          </div>
          {list.map((o) => (
            <div key={o.mandate_id} role="row" data-testid="order-row" onClick={() => nav(`/orders/${encodeURIComponent(o.mandate_id)}`)}
              className={`${GRID} h-11 items-center border-b border-line cursor-pointer hover:bg-s2 ${o.mandate_id === id ? 'bg-s2' : ''}`}>
              <span role="cell" className="mono text-[12px]"><Link to={`/orders/${encodeURIComponent(o.mandate_id)}`} className="focus-ring" onClick={(e) => e.stopPropagation()}>{shortId(o.mandate_id)}</Link></span>
              <span role="cell" className="truncate">{t('commodity.cement')} {o.grade ? t(`gradeShort.${o.grade}`) : ''}</span>
              <span role="cell" className="mono text-right">{fmtNum(o.qty_t)}</span>
              <span role="cell" className="truncate pl-4">{regionName(t, o.region)}</span>
              <span role="cell" className="mono text-right">{fmtNum(o.max_price_t)}</span>
              <span role="cell" className="truncate pl-4">{o.window_start ? `${dayWord(t, o.window_start)} ` : ''}<span className="mono">{o.window ?? '—'}</span></span>
              <span role="cell"><StatusPill s={o.status} /></span>
            </div>
          ))}
          <p data-testid="orders-total" className="text-[12px] text-mute mt-3">{total}</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {list.map((o) => <OrderRow key={o.mandate_id} o={o} />)}
          {list.length ? <p data-testid="orders-total" className="text-[12px] text-mute mt-1">{total}</p> : null}
        </div>
      )}
    </div>
  )
}
