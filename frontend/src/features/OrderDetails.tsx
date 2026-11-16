import { useNavigate } from 'react-router-dom'
import { CircleCheck, CircleX, Factory, Scale, Target, TrendingUp, X } from 'lucide-react'
import { ApiError, api } from '../api/client'
import type { MyOrder } from '../api/types'
import { useStore, useViewport } from '../app/store'
import { BigNumber } from '../components/BigNumber'
import { KV } from '../components/Card'
import { Disclosure } from '../components/Disclosure'
import { PillButton } from '../components/PillButton'
import { ErrorBox, Loading } from '../components/States'
import { SupplyDemand } from '../components/SupplyDemand'
import { Num, Tx } from '../components/Tx'
import { useLang } from '../i18n'
import { fmtNum, shortHash, shortId } from '../lib/format'
import { regionName, windowWords } from '../lib/labels'
import { useAsync } from '../lib/useAsync'
import { StatusPill } from './MarketParts'
import { MoneyTimeline } from './MoneyTimeline'

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

function Block({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="bg-s2 rounded-card px-5 py-4 scroll-mt-16">
      <h3 className="text-[13px] text-ink3 mb-2">{title}</h3>
      {children}
    </section>
  )
}

export function OrderDetails({ order, onClose }: { order: MyOrder; onClose?: () => void }) {
  const { t, lang } = useLang()
  const nav = useNavigate()
  const vp = useViewport()
  const { setPrefill, tick } = useStore()
  const done = order.status === 'filled' || order.status === 'partial' || order.status === 'unfilled'
  const ex = useAsync(async () => {
    if (!done) return null
    try { return await api.explain(order.mandate_id, lang) } catch (e) { if (e instanceof ApiError && e.status === 404) return null; throw e }
  }, [order.mandate_id, order.status, lang, tick])
  const run = useAsync(async () => (order.run_id ? api.result(order.run_id) : null), [order.run_id])
  const dealId = order.deal_id ?? (order.run_id && order.status !== 'unfilled' ? `${order.run_id}:${order.mandate_id}` : null)
  const audit = useAsync(async () => (dealId ? api.audit(dealId) : null), [dealId])
  const e = ex.data
  const mine = (run.data?.allocations ?? []).filter((a) => a.mandate_id === order.mandate_id).reduce<NonNullable<typeof run.data>['allocations']>((acc, a) => {
    const same = acc.find((x) => x.offer_id === a.offer_id && x.delivered_price_t === a.delivered_price_t)
    if (same) same.qty_t += a.qty_t
    else acc.push({ ...a })
    return acc
  }, [])
  const I = { size: 18, strokeWidth: 1.75 }
  const fields = { commodity: order.commodity ?? 'cement', grade: order.grade ?? '32.5', qty_t: order.qty_t ?? null, region: order.region ?? null, deadline: order.deadline ?? null, max_price_t: order.max_price_t ?? null }
  const goPanel = (max?: number | null) => {
    setPrefill({ text: order.phrase ?? '', fields: { ...fields, max_price_t: max ?? fields.max_price_t } })
    nav(vp === 'desktop' ? '/market' : '/buy')
  }
  const needed = order.fill_at_max_price_t ?? e?.needed_delivered ?? null

  return (
    <div data-testid="order-details" className="flex flex-col gap-4">
      <header>
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-3"><span className="mono text-[13px]">№ {shortId(order.mandate_id)}</span><StatusPill s={order.status} /></span>
          {onClose ? <button type="button" onClick={onClose} aria-label={t('detail.close')} className="focus-ring w-8 h-8 rounded-full bg-s2 inline-flex items-center justify-center text-ink3 hover:text-ink"><X size={16} strokeWidth={1.75} /></button> : null}
        </div>
        <h2 className="h2 mt-2"><Tx k="card.head" vars={{ commodity: <>{t('commodity.cement')} {t(`gradeShort.${order.grade ?? '32.5'}`)}</>, qty: fmtNum(order.qty_t) }} /></h2>
        <p className="text-[13px] text-ink3"><Tx k="detail.capLine" vars={{ region: regionName(t, order.region), max: fmtNum(order.max_price_t) }} /></p>
        {order.phrase ? <p className="text-[13px] text-ink3 italic mt-2">«{order.phrase}»</p> : null}
      </header>

      {order.status === 'in_basket' ? (
        <Block id="d-result" title={t('detail.result')}>
          <p className="text-[14px]">{t('detail.waiting', { when: order.window ? `${windowWords(t, order.window_start, null).replace(/, \d\d:\d\d$/, '')}, ${order.window}` : windowWords(t, order.window_start, null) })}</p>
        </Block>
      ) : null}

      {done ? (
        <Block id="d-result" title={t('detail.result')}>
          {ex.loading && !e ? <Loading /> : ex.error ? <ErrorBox detail={ex.error} onRetry={ex.reload} /> : e ? (
            e.outcome !== 'unfilled' ? (
              <>
                <BigNumber value={e.your_price_delivered} unit={mine.length > 1 ? t('result.avg') : t('result.price')} lime size={38} testId="result-price" />
                {mine.length > 1 ? (
                  <ul className="text-[13px] text-ink3 mt-2 leading-[1.7]" data-testid="result-parts">
                    {mine.map((a) => <li key={`${a.offer_id}-${a.delivered_price_t}`}><Tx k="result.part" vars={{ qty: fmtNum(a.qty_t), plant: a.seller, price: fmtNum(a.delivered_price_t), base: fmtNum(a.price_t), delivery: fmtNum(a.tariff_t) }} /></li>)}
                  </ul>
                ) : (
                  <p className="text-[13px] text-ink3 mt-2"><Tx k="result.split" vars={{ base: fmtNum(e.clearing_price_base), delivery: fmtNum(mine[0]?.tariff_t ?? (e.your_price_delivered != null && e.clearing_price_base != null ? e.your_price_delivered - e.clearing_price_base : null)) }} /></p>
                )}
                <p className="text-[13px] mt-2">{mine.map((a) => a.seller).filter((v, i, arr) => arr.indexOf(v) === i).join(' + ')} · <span className="mono">{fmtNum(e.your_filled_qty)}</span> {t('common.t')}</p>
              </>
            ) : (
              <>
                {e.clearing_price_base !== null ? <BigNumber label={t('result.oneForAll')} value={e.clearing_price_base} unit={t('common.perT')} size={38} /> : null}
                {e.why_out ? <p className="text-[14px] text-ink2 mt-2">{cap(e.why_out)}.</p> : null}
                {needed ? <p className="text-[13px] text-ink3 mt-1"><Tx k="detail.wouldEnter" vars={{ price: fmtNum(needed) }} /></p> : null}
                {needed ? <PillButton block={false} className="mt-3" arrow onClick={() => goPanel(needed)}>{t('detail.raise', { price: fmtNum(needed) })}</PillButton> : null}
              </>
            )
          ) : <Loading />}
        </Block>
      ) : null}

      {done && e ? (
        <Block id="d-why" title={t('detail.why')}>
          <ul className="flex flex-col gap-2 text-[14px]" data-testid="why-facts">
            <li className="flex gap-2"><Scale {...I} className="text-lime shrink-0 mt-[2px]" /><span><Tx k="why.demand" vars={{ demand: fmtNum(e.total_demand_t), supply: fmtNum(e.total_supply_t) }} /></span></li>
            {e.clearing_price_base !== null ? <li className="flex gap-2"><Target {...I} className="text-lime shrink-0 mt-[2px]" /><span><Tx k="why.price" vars={{ price: fmtNum(e.clearing_price_base) }} /></span></li> : null}
            {e.outcome !== 'unfilled'
              ? <li className="flex gap-2"><CircleCheck {...I} className="text-lime shrink-0 mt-[2px]" /><span><Tx k="why.in" vars={{ max: fmtNum(e.your_max) }} /></span></li>
              : <li className="flex gap-2"><CircleX {...I} className="text-bad shrink-0 mt-[2px]" /><span>{e.why_out ? cap(e.why_out) + '.' : '—'}</span></li>}
            {e.vs_last_week ? <li className="flex gap-2"><TrendingUp {...I} className="text-lime shrink-0 mt-[2px]" /><span>{cap(e.vs_last_week)}.</span></li> : null}
            {e.plant_region ? <li className="flex gap-2"><Factory {...I} className="text-lime shrink-0 mt-[2px]" /><span>{t('why.from', { text: [e.seller, e.plant_region].filter(Boolean).join(', ') })}{e.plant_region.endsWith('.') ? '' : '.'}</span></li> : null}
          </ul>
          {e.counterfactual ? <p className="text-[13px] text-ink2 mt-3" data-testid="counterfactual">{/[.!?]$/.test(e.counterfactual) ? e.counterfactual : `${e.counterfactual}.`}</p> : null}
          {run.data ? <div className="mt-3 w-full"><SupplyDemand demand={run.data.aggregates.demand_curve} supply={run.data.aggregates.supply_curve} price={run.data.clearing_price_t} /></div> : null}
          <p className="caption mt-2">{t('why.private')}</p>
        </Block>
      ) : null}

      {dealId ? (
        <Block id="d-money" title={t('detail.money')}>
          <MoneyTimeline dealId={dealId} note />
        </Block>
      ) : null}

      {dealId && audit.data ? (
        <section className="bg-s2 rounded-card px-5 py-2">
          <Disclosure label={t('detail.passport')}>
            <div data-testid="passport">
              <KV k={t('passport.mandate')} v={<Num className="text-[12px]">{shortHash(audit.data.mandate_hash)}</Num>} />
              <KV k={t('passport.rule')} v={<Num className="text-[12px]">{audit.data.engine_version ?? '—'}</Num>} />
              <KV k={t('passport.tiebreak')} v={audit.data.tie_break_used ? t(`passport.tb.${audit.data.tie_break_used}`) : '—'} />
              <KV k={t('passport.price')} v={<Num>{fmtNum(audit.data.clearing_price)}</Num>} />
              <KV k={t('passport.qty')} v={<Num>{fmtNum(audit.data.qty_t)} {t('common.t')}</Num>} />
              <KV k={t('passport.inputs')} v={<Num className="text-[12px]">{shortHash(audit.data.inputs_hash)}</Num>} />
              <KV k={t('passport.explain')} v={<Num className="text-[12px]">{shortHash(audit.data.explanation_hash)}</Num>} />
              <KV k={t('passport.receipt')} v={<Num className="text-[12px]">{shortHash(audit.data.signer_receipt)}</Num>} />
              <KV k={t('passport.approved')} v={t('passport.approvedValue')} />
              <KV k={t('passport.appeal')} v={<span className="text-[12px]">{(lang === 'uz' ? audit.data.appeal_channel_uz : audit.data.appeal_channel) ?? t('passport.appealValue')}</span>} />
              <p className="caption py-2 text-lime">{t('passport.ai')}</p>
            </div>
          </Disclosure>
        </section>
      ) : null}

      <PillButton variant="ghost" arrow onClick={() => goPanel()}>{t('detail.repeat')}</PillButton>
    </div>
  )
}
