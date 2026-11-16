import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Escrow, EscrowEvent, EscrowState } from '../api/types'
import { Badge } from '../components/Badge'
import { PillButton } from '../components/PillButton'
import { ErrorBox, Loading } from '../components/States'
import { Timeline, type TimelineItem } from '../components/Timeline'
import { Tx } from '../components/Tx'
import { useT } from '../i18n'
import { fmtNum, fmtTime } from '../lib/format'

const ORDER: EscrowState[] = ['CREATED', 'DEPOSIT_HELD', 'MATCHED', 'PAID_IN_FULL', 'DELIVERED', 'RELEASED']

export function MoneyTimeline({ dealId, onChange, initial, note = false }: { dealId: string; onChange?: (e: Escrow) => void; initial?: Escrow | null; note?: boolean }) {
  const t = useT()
  const [e, setE] = useState<Escrow | null>(initial ?? null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<unknown>(null)
  useEffect(() => {
    let alive = true
    if (!initial) api.escrow(dealId).then((r) => { if (alive) { setE(r); onChange?.(r) } }, (x) => { if (alive) setErr(x) })
    return () => { alive = false }
  }, [dealId]) // eslint-disable-line react-hooks/exhaustive-deps

  const fire = async (ev: EscrowEvent) => {
    setBusy(true)
    setErr(null)
    try {
      const r = await api.escrowEvent(dealId, ev, ev === 'ettn_rejected' ? t('money.reject') : undefined)
      setE(r)
      onChange?.(r)
    } catch (x) { setErr(x) } finally { setBusy(false) }
  }
  if (err && !e) return <ErrorBox detail={err} />
  if (!e) return <Loading />
  const at = (st: EscrowState) => e.history.find((h) => h.state === st)?.at ?? null
  const idx = ORDER.indexOf(e.state)
  const disputed = e.state === 'DISPUTED'
  const cancelled = e.state === 'CANCELLED'
  const reached = (st: EscrowState) => idx >= ORDER.indexOf(st) || (disputed && ORDER.indexOf(st) <= 3)
  const demo = (node: React.ReactNode) => (
    <div>
      <div className="flex flex-wrap gap-2">{node}</div>
    </div>
  )
  const items: TimelineItem[] = [
    { key: 'held', title: t('money.held'), time: fmtTime(at('DEPOSIT_HELD')), state: 'done', hint: e.deposit ? <Tx k="money.amount" vars={{ sum: fmtNum(e.deposit) }} /> : undefined },
    { key: 'matched', title: t('money.matched'), time: reached('MATCHED') ? fmtTime(at('MATCHED')) : null, state: reached('MATCHED') ? 'done' : 'pending', hint: e.amount ? <Tx k="money.amount" vars={{ sum: fmtNum(e.amount) }} /> : undefined },
    cancelled ? { key: 'cancel', title: t('money.cancelled'), state: 'bad' } : {
      key: 'paid', title: reached('PAID_IN_FULL') ? t('money.paid') : t('money.pay'), time: reached('PAID_IN_FULL') ? fmtTime(at('PAID_IN_FULL')) : null,
      state: reached('PAID_IN_FULL') ? 'done' : e.state === 'MATCHED' ? 'current' : 'pending',
      action: e.state === 'MATCHED' ? demo(<PillButton block={false} className="!py-2" disabled={busy} onClick={() => fire('payment_confirmed')}>{t('money.payBtn')}</PillButton>) : undefined,
    },
    ...(cancelled ? [] : disputed ? [{ key: 'dispute', title: t('money.disputed'), hint: t('money.disputedHint'), state: 'bad' as const, time: fmtTime(at('DISPUTED')) }] : [
      {
        key: 'deliv', title: reached('DELIVERED') ? t('money.delivered') : t('money.waitSign'), time: reached('DELIVERED') ? fmtTime(at('DELIVERED')) : null,
        state: reached('DELIVERED') ? 'done' as const : e.state === 'PAID_IN_FULL' ? 'current' as const : 'pending' as const,
        action: e.state === 'PAID_IN_FULL' ? demo(<>
          <PillButton block={false} className="!py-2" disabled={busy} onClick={() => fire('ettn_signed')}>{t('money.accept')}</PillButton>
          <PillButton block={false} className="!py-2" variant="ghost" disabled={busy} onClick={() => fire('ettn_rejected')}>{t('money.reject')}</PillButton>
        </>) : undefined,
      },
      { key: 'rel', title: t('money.released'), hint: reached('RELEASED') ? undefined : t('money.releasedHint'), time: reached('RELEASED') ? fmtTime(at('RELEASED')) : null, state: reached('RELEASED') ? 'done' as const : 'pending' as const },
    ]),
  ]
  return (
    <div>
      <Timeline items={items} />
      {err ? <ErrorBox detail={err} /> : null}
      {note ? <div className="flex items-center gap-2 mt-3"><Badge kind="demo" /><span className="caption">{t('money.note')} · {t('money.demoButtons')}</span></div> : null}
    </div>
  )
}
