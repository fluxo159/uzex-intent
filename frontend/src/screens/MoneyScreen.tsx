import { useEffect, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { api } from '../api/client'
import type { Escrow, MyOrder } from '../api/types'
import { useMyOrders } from '../app/hooks'
import { useStore, useViewport } from '../app/store'
import { Badge } from '../components/Badge'
import { MoneyTimeline } from '../features/MoneyTimeline'
import { StatusPill } from '../features/MarketParts'
import { useLang } from '../i18n'
import { fmtNum, shortId } from '../lib/format'
import { CountUp } from '../lib/motion'

const DEPOSIT_WORST = 0.10
const IN_DEAL = new Set(['MATCHED', 'PAID_IN_FULL', 'DELIVERED', 'DISPUTED'])

const dealOf = (o: MyOrder) => o.deal_id ?? (o.run_id && o.status !== 'unfilled' ? `${o.run_id}:${o.mandate_id}` : null)

export function MoneyScreen() {
  const { t } = useLang()
  const vp = useViewport()
  const { account, tick } = useStore()
  const { orders } = useMyOrders()
  const [esc, setEsc] = useState<Record<string, Escrow>>({})
  const [open, setOpen] = useState<string | null>(null)
  const deals = orders.filter((o) => dealOf(o))
  const dealKey = deals.map(dealOf).join(',')

  useEffect(() => {
    let alive = true
    Promise.all(deals.map((o) => api.escrow(dealOf(o)!).then((e) => [dealOf(o)!, e] as const).catch(() => null))).then((rs) => {
      if (!alive) return
      setEsc(Object.fromEntries(rs.filter(Boolean) as [string, Escrow][]))
    })
    return () => { alive = false }
  }, [dealKey, tick]) // eslint-disable-line react-hooks/exhaustive-deps

  const blockedInBasket = orders.filter((o) => o.status === 'in_basket').reduce((s, o) => s + Math.round((o.qty_t ?? 0) * (o.max_price_t ?? 0) * DEPOSIT_WORST), 0)
  const es = Object.values(esc)
  const blocked = blockedInBasket + es.filter((e) => e.state === 'DEPOSIT_HELD').reduce((s, e) => s + (e.deposit ?? 0), 0)
  const inDeals = es.filter((e) => IN_DEAL.has(e.state)).reduce((s, e) => s + (e.amount ?? 0), 0)
  const paid = es.filter((e) => e.state === 'RELEASED').reduce((s, e) => s + (e.amount ?? 0), 0)
  const free = account.funds != null ? account.funds - blocked - inDeals : null

  const tiles: [string, number | null][] = [['msum.blocked', blocked], ['msum.inDeals', inDeals], ['msum.paid', paid], ['msum.free', free]]
  return (
    <div className={vp === 'desktop' ? 'p-6' : 'pt-4'}>
      <h1 className="h-page mb-4">{t('money.title')}</h1>
      <div data-testid="money-summary" className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {tiles.map(([k, v]) => (
          <div key={k} className="bg-s2 rounded-card px-5 py-4">
            <div className="caption">{t(k)}</div>
            <div className="mono text-[22px] font-bold tracking-[-0.03em] mt-1"><CountUp value={v} /></div>
            <div className="text-[11px] text-mute">{t('common.sum')}</div>
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2 mt-3"><Badge kind="demo" testId="badge-demo-money" /><span className="caption">{t('money.note')} · {t('money.demoButtons')}</span></div>

      <h2 className="text-[13px] text-ink3 mt-6 mb-2">{t('money.deals')}</h2>
      {!deals.length ? <p className="caption">{t('money.none')}</p> : (
        <div className="flex flex-col gap-2">
          {deals.map((o) => {
            const id = dealOf(o)!
            const e = esc[id]
            const isOpen = open === id
            return (
              <div key={id} className="bg-s2 rounded-card">
                <button type="button" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : id)} className="focus-ring w-full text-left px-5 py-4 flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="mono text-[12px] text-ink3">№ {shortId(o.mandate_id)}</span>
                  <StatusPill s={o.status} />
                  <span className={`text-[13px] truncate ${vp === 'desktop' ? 'flex-1' : 'order-last basis-full'}`}>{e ? t(`money.st.${e.state}`) : '—'}</span>
                  <span className={`mono text-[14px] ${vp === 'desktop' ? '' : 'ml-auto'}`}>{fmtNum(e?.amount ?? null)}</span>
                  <ChevronDown size={16} strokeWidth={1.75} className={`text-mute transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                </button>
                {isOpen ? <div className="px-5 pb-4"><MoneyTimeline dealId={id} initial={e} onChange={(x) => setEsc((m) => ({ ...m, [id]: x }))} /></div> : null}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
