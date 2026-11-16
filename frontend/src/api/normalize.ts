import type { Audit, BasketView, Code, Escrow, Explain, IntakeFields, Ladder, MyOrder, OrderStatus, ParseResponse, PastBasket, PlantDemand, Preview, SignResponse } from './types'

type Any = Record<string, unknown>
const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : typeof v === 'string' && v.trim() !== '' && !Number.isNaN(+v) ? +v : null)
const str = (v: unknown): string | null => (typeof v === 'string' ? v : v === null || v === undefined ? null : String(v))
const codes = (v: unknown): Code[] => ((v ?? []) as unknown[]).map((w) => (typeof w === 'string' ? { code: w } : { code: str((w as Any).code) ?? '', params: ((w as Any).params ?? {}) as Record<string, unknown> }))

export function normParse(d: unknown): ParseResponse {
  const o = (d ?? {}) as Any
  return {
    fields: (o.fields ?? {}) as IntakeFields,
    missing_fields: (o.missing_fields ?? o.missing ?? []) as string[],
    transcript_norm: str(o.transcript_norm) ?? '',
    source: str(o.source) ?? 'offline',
    confidence_note: str(o.confidence_note),
  }
}

export function normPreview(d: unknown, fields: IntakeFields): Preview {
  const o = (d ?? {}) as Any
  const fees = (o.fees ?? o) as Any
  const gate = (o.gate ?? { status: 'ok', checks: [] }) as Any
  const nb = (o.next_basket ?? {}) as Any
  const ur = (o.usual_range ?? o.usual ?? null) as Any | null
  return {
    fields: (o.fields as IntakeFields) ?? fields,
    gross_max: num(fees.gross_max) ?? 0,
    fee_rate: num(fees.fee_rate) ?? 0.002016,
    exchange_fee: num(fees.exchange_fee) ?? 0,
    deposit_rate: num(fees.deposit_rate) ?? 0.1,
    deposit_worst: num(fees.deposit_worst) ?? 0,
    deposit_final: Boolean(fees.deposit_final),
    delivery_min_t: num(fees.delivery_min_t),
    delivery_max_t: num(fees.delivery_max_t),
    total_worst: num(fees.total_worst) ?? 0,
    needed_now: num(fees.needed_now) ?? undefined,
    gate: {
      status: (str(gate.status) ?? 'ok') as Preview['gate']['status'],
      checks: ((gate.checks ?? []) as Any[]).map((c) => ({
        name: str(c.name) ?? '',
        passed: Boolean(c.passed),
        status: (str(c.level ?? c.status) ?? (c.passed ? 'ok' : 'blocked')) as 'ok' | 'warning' | 'blocked',
        reason: str(c.reason),
        how_to_fix: str(c.how_to_fix),
        entity_name: str(c.entity_name),
        funds_available: num(c.funds_available),
      })),
      demo: gate.demo !== false,
      demo_label: str(gate.demo_label),
    },
    next_basket: {
      basket_id: str(nb.basket_id ?? o.basket_id) ?? '',
      window: str(nb.window),
      close_time: str(nb.close_time ?? nb.window_end) ?? '',
      open_time: str(nb.window_start ?? nb.open_time),
    },
    usual: ur && ur.available !== false ? { p10: num(ur.p10 ?? ur.lo), p90: num(ur.p90 ?? ur.hi) } : null,
    warnings: codes(o.warnings),
    errors: codes(o.errors),
    mandate_draft: (o.mandate_draft as Record<string, unknown>) ?? null,
    hash: str(o.hash),
  }
}

export function normSign(d: unknown): SignResponse {
  const o = (d ?? {}) as Any
  const r = o.receipt
  const rec = r && typeof r === 'object' ? (r as Any) : null
  return {
    mandate_id: str(o.mandate_id) ?? '',
    hash: str(o.hash) ?? '',
    receipt: rec ? str(rec.receipt_id) ?? '' : str(r) ?? '',
    receipt_mac: rec ? str(rec.mac) : null,
    signed_at: str(o.signed_at ?? rec?.signed_at) ?? '',
    basket_id: str(o.basket_id) ?? '',
    demo: o.demo !== false,
  }
}

export function normBasket(d: unknown): BasketView {
  const o = (d ?? {}) as Any
  return {
    basket_id: str(o.basket_id) ?? '',
    commodity: str(o.commodity) ?? 'cement',
    grade: str(o.grade) ?? '32.5',
    close_time: str(o.close_time ?? o.window_end) ?? '',
    open_time: str(o.window_start),
    window: str(o.window),
    status: o.status === 'closed' || o.run_id ? 'closed' : 'open',
    n_buyers: num(o.n_buyers ?? o.n_bids) ?? 0,
    n_plants: num(o.n_plants ?? o.n_asks) ?? 0,
    demand_t: num(o.demand_t ?? o.total_demand) ?? 0,
    supply_t: num(o.supply_t ?? o.total_supply) ?? 0,
    run_id: str(o.run_id),
  }
}

export function normExplain(d: unknown): Explain {
  const o = (d ?? {}) as Any
  return {
    ...(o as unknown as Explain),
    deal_id: str(o.deal_id) ?? (o.run_id && o.mandate_id && o.outcome !== 'unfilled' ? `${String(o.run_id)}:${String(o.mandate_id)}` : null),
  }
}

export function normEscrow(d: unknown): Escrow {
  const w = (d ?? {}) as Any
  const o = (w.escrow && typeof w.escrow === 'object' ? w.escrow : w) as Any
  return {
    deal_id: str(o.deal_id) ?? '',
    state: (str(o.state) ?? 'CREATED') as Escrow['state'],
    label: { ru: str(o.label_ru), uz: str(o.label_uz) },
    seller: str(o.seller),
    deadline: str(o.deadline),
    allowed_events: (o.allowed_events as string[]) ?? undefined,
    history: ((o.history ?? []) as Any[]).map((h) => ({ state: str(h.to ?? h.state) as Escrow['state'], at: str(h.at) ?? '', note: str(h.event) })),
    amount: num(o.amount),
    deposit: num(o.deposit),
    qty_t: num(o.qty_t),
    demo: o.demo !== false,
    dispute: o.dispute_reason ? { reason: str(o.dispute_reason), days: 3 } : null,
  }
}

export function normAudit(d: unknown): Audit {
  const o = (d ?? {}) as Any
  const r = o.signer_receipt
  const alloc = ((o.allocations ?? []) as Any[])
  return {
    deal_id: str(o.deal_id) ?? '',
    mandate_hash: str(o.mandate_hash),
    inputs_hash: str(o.inputs_hash),
    engine_version: str(o.engine_version),
    tie_break_used: str(o.tie_break_used),
    clearing_price: num(o.clearing_price),
    qty_t: num(o.qty_t) ?? (alloc.length ? alloc.reduce((s, a) => s + (num(a.qty_t) ?? 0), 0) : null),
    explanation_hash: str(o.explanation_hash),
    signer_receipt: r && typeof r === 'object' ? str((r as Any).receipt_id) : str(r),
    approved_by: str(o.approved_by),
    decided_by: str(o.decided_by),
    appeal_channel: str(o.appeal_channel),
    appeal_channel_uz: str(o.appeal_channel_uz),
    reference_price: num(o.reference_price),
  }
}

export function normPlant(d: unknown): PlantDemand {
  const o = (d ?? {}) as Any
  return {
    seller: str(o.seller) ?? '',
    warehouse_region: str(o.warehouse_region),
    price_t: num(o.price_t ?? o.min_price_t),
    min_lot_t: num(o.min_lot_t) ?? 50,
    buy_at_price_t: num(o.buy_at_price_t ?? o.ready_at_your_price_t) ?? 0,
    basket_total_t: num(o.basket_total_t ?? o.basket_demand_t) ?? 0,
    regions: ((o.regions ?? []) as Any[]).map((r) => ({
      region: str(r.region) ?? '',
      qty_t: num(r.qty_t) ?? 0,
      n_mandates: num(r.n_mandates) ?? 0,
      deadline: str(r.deadline ?? r.earliest_deadline),
      lots: num(r.lots) ?? 0,
      rest_t: num(r.rest_t ?? r.remainder_t) ?? 0,
      sizes: (r.sizes as number[]) ?? undefined,
    })),
    sellers: (o.sellers as string[]) ?? undefined,
    last_run: (o.last_run as PlantDemand['last_run']) ?? null,
  }
}

const bandsOf = (v: unknown) => ((v ?? []) as Any[]).map((b) => ({ price_from: num(b.price_from) ?? 0, price_to: num(b.price_to) ?? 0, qty_t: num(b.qty_t) ?? 0 })).filter((b) => b.qty_t > 0)

export function normLadder(d: unknown): Ladder {
  const o = (d ?? {}) as Any
  const tt = (o.totals ?? {}) as Any
  return {
    basket_id: str(o.basket_id),
    bands_demand: bandsOf(o.bands_demand),
    bands_supply: bandsOf(o.bands_supply),
    totals: { bids: num(tt.bids) ?? 0, bid_t: num(tt.bid_t) ?? 0, asks: num(tt.asks) ?? 0, ask_t: num(tt.ask_t) ?? 0 },
    closed: Boolean(o.closed),
    clearing_price_t: o.closed ? num(o.clearing_price_t) : null,
  }
}

const STATUSES: OrderStatus[] = ['in_basket', 'filled', 'partial', 'unfilled', 'expired']
export function normMine(d: unknown): MyOrder[] {
  const arr = (Array.isArray(d) ? d : ((d as Any)?.items ?? (d as Any)?.mandates ?? [])) as Any[]
  return arr.map((m) => {
    const li = ((m.line_items as Any[] | undefined)?.[0] ?? {}) as Any
    const bk = (m.basket ?? {}) as Any
    const st = str(m.status) as OrderStatus
    return {
      mandate_id: str(m.mandate_id) ?? '',
      status: STATUSES.includes(st) ? st : 'in_basket',
      run_id: str(m.run_id),
      deal_id: str(m.deal_id),
      basket_id: str(m.basket_id ?? bk.basket_id),
      window: str(m.window ?? bk.window),
      window_start: str(m.window_start ?? bk.window_start),
      commodity: str(m.commodity ?? li.commodity),
      grade: str(m.grade ?? li.grade),
      qty_t: num(m.qty_t ?? li.qty_t),
      region: str(m.region ?? (m.allowed_regions as string[] | undefined)?.[0]),
      max_price_t: num(m.max_price_t ?? (m.amount_range as Any | undefined)?.max_price_t),
      deadline: str(m.deadline ?? (m.execution_window as Any | undefined)?.not_after),
      phrase: str(m.phrase ?? m.natural_language_description),
      signed_at: str(m.signed_at ?? m.created_at),
      filled_t: num(m.filled_t),
      clearing_price_t: num(m.clearing_price_t),
      delivered_price_t: num(m.delivered_price_t),
      sellers: (m.sellers as string[]) ?? [],
      fill_at_max_price_t: num(m.fill_at_max_price_t),
      reason: str(m.reason),
    }
  })
}

export function normHistory(d: unknown): PastBasket[] {
  const arr = (Array.isArray(d) ? d : ((d as Any)?.baskets ?? (d as Any)?.items ?? (d as Any)?.runs ?? [])) as Any[]
  return arr.map((r) => ({
    run_id: str(r.run_id) ?? '', date: str(r.date), window: str(r.window), clearing_price_t: num(r.clearing_price_t),
    executed_qty_t: num(r.executed_qty_t), n_bids: num(r.n_bids), n_asks: num(r.n_asks), demo: Boolean(r.demo),
  }))
}
