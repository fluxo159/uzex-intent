import chartFx from './fixtures/chart.json'
import httpFx from './fixtures/http.json'
import scenarioFx from './fixtures/scenario.json'
import type { Chart, IntakeFields, Principal } from './types'

type Any = Record<string, any> // eslint-disable-line @typescript-eslint/no-explicit-any
const H = httpFx as unknown as Any
const SC = scenarioFx as unknown as { asks: { offer_id: string; seller: string; qty_t: number; min_price_t: number; warehouse_region: string; min_lot_t: number; deposit_rate: number }[]; tariff_rows: { from: string; to: string; t: number }[] }

const BUYER_FEE_RATE = 0.002016
const DEPOSIT_WORST = 0.10
const B1 = H.preview.b1 as Any
const B1_ID: string = H.ids.b1
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x)) as T
const roundHalfUp = (x: number) => Math.floor(x + 0.5)

export function tariff(from: string, to: string): number | null {
  if (from === to) return 0
  for (const r of SC.tariff_rows) if ((r.from === from && r.to === to) || (r.from === to && r.to === from)) return r.t
  return null
}

interface MockState { drafts: Record<string, Any>; closed: boolean; escrow: Record<string, Any>; user: string | null }
const KEY = 'intent.mock.state'
function load(): MockState {
  try {
    const s = sessionStorage.getItem(KEY)
    if (s) return JSON.parse(s) as MockState
  } catch {}
  return { drafts: {}, closed: false, escrow: {}, user: null }
}
let state: MockState = load()
function save() {
  try { sessionStorage.setItem(KEY, JSON.stringify(state)) } catch {}
}
export function mockReset() {
  state = { drafts: {}, closed: false, escrow: {}, user: null }
  save()
  return { ok: true, seed: 2035 }
}

const STEMS: [string, string][] = [
  ['наманган', 'Namangan'], ['намангон', 'Namangan'], ['namangan', 'Namangan'], ['namangon', 'Namangan'],
  ['андиж', 'Andijan'], ['andij', 'Andijan'], ['карши', 'Qashqadaryo'], ['қарши', 'Qashqadaryo'], ['qarshi', 'Qashqadaryo'],
  ['джизак', 'Jizzakh'], ['жиззах', 'Jizzakh'], ['jizzax', 'Jizzakh'], ['самарканд', 'Samarkand'], ['самарқанд', 'Samarkand'], ['samarqand', 'Samarkand'],
  ['бухар', 'Bukhara'], ['бухоро', 'Bukhara'], ['buxoro', 'Bukhara'], ['фергана', 'Fergana'], ['фарғона', 'Fergana'], ["farg'ona", 'Fergana'],
  ['навои', 'Navoiy'], ['navoiy', 'Navoiy'], ['сырдар', 'Sirdaryo'], ['сирдар', 'Sirdaryo'], ['термез', 'Surkhandaryo'], ['термиз', 'Surkhandaryo'],
  ['хорезм', 'Khorezm'], ['хоразм', 'Khorezm'], ['xorazm', 'Khorezm'], ['нукус', 'Karakalpakstan'], ['nukus', 'Karakalpakstan'],
  ['ташкент', 'Tashkent_city'], ['тошкент', 'Tashkent_city'], ['toshkent', 'Tashkent_city'],
]
const norm = (t: string) => t.trim().toLowerCase().replace(/\s+/g, ' ')
const toInt = (s: string) => parseInt(s.replace(/[\s  ]/g, ''), 10)

export function mockParse(text: string): Any {
  const n = norm(text || '')
  for (const [phrase, body] of Object.entries(H.parse as Record<string, Any>)) if (norm(phrase) === n) return clone(body)
  const f: IntakeFields = { commodity: null, grade: null, qty_t: null, region: null, deadline: null, max_price_t: null, payment_terms: 'after_delivery' }
  if (/цемент|cement|sement|семент|м400|м500|m400|m500|32[,.]5|42[,.]5/.test(n)) f.commodity = 'cement'
  if (/м\s?500|m\s?500|42[,.]5/.test(n)) f.grade = '42.5'
  else if (f.commodity) f.grade = '32.5'
  const q = /(\d[\d ]*?)\s*(т\b|тонн|тонна|tonna|t\b)/.exec(n)
  if (q) f.qty_t = toInt(q[1])
  const p = /(?:не дороже|максимум|не больше)\s*(\d[\d  ]*\d|\d)/.exec(n) || /(\d[\d  ]*\d)\s*(?:gacha|гача|дан ошмасин)/.exec(n)
  if (p) f.max_price_t = toInt(p[1])
  let best: { at: number; code: string } | null = null
  for (const [stem, code] of STEMS) { const at = n.lastIndexOf(stem); if (at >= 0 && (!best || at > best.at)) best = { at, code } }
  if (best) f.region = best.code
  const d = /до\s*(\d{1,2})(?:-?го)?\s*(ноябр|декабр)?|(\d{1,2})\s*(noyabr|dekabr|ноябр|декабр)/.exec(n)
  if (d) {
    const day = +(d[1] || d[3])
    const m = /декабр|dekabr/.test(d[2] || d[4] || '') ? 12 : 11
    f.deadline = `2026-${m}-${String(day).padStart(2, '0')}`
  }
  const missing = (['commodity', 'qty_t', 'region', 'max_price_t'] as const).filter((k) => f[k] === null)
  return { transcript_norm: n, fields: f, missing_fields: missing, source: 'offline', confidence_note: 'mock', lang: 'ru' }
}

export function mockStt(): Any {
  return { transcript: Object.keys(H.parse)[0], lang: 'ru', source: 'cache' }
}

function sameFields(a: IntakeFields, b: IntakeFields) {
  return a.qty_t === b.qty_t && a.max_price_t === b.max_price_t && a.region === b.region && (a.grade ?? '32.5') === (b.grade ?? '32.5')
}

function gateFor(principal: Principal, base: Any): Any {
  const g = clone(base)
  const reg = (H.registry.entities as Any[]).find((e) => e.inn === principal.inn)
  g.checks = (g.checks as Any[]).map((c) => {
    if (c.name === 'principal_kind' && principal.kind === 'person_2035') return (H.preview_person.gate.checks as Any[]).find((x) => x.name === 'principal_kind')
    if (c.name === 'company_status') {
      if (principal.kind === 'person_2035' || principal.kind === 'guest') return (H.preview_person.gate.checks as Any[]).find((x) => x.name === 'company_status')
      if (!reg) return { name: 'company_status', passed: false, level: 'blocked', reason: 'ИНН не найден в реестре', how_to_fix: 'проверьте ИНН', demo: true }
      return { ...c, entity_name: reg.name }
    }
    return c
  })
  const lv = (g.checks as Any[]).map((c) => c.level)
  g.status = lv.includes('blocked') ? 'blocked' : lv.includes('warning') ? 'warning' : 'ok'
  return g
}

export function mockPreview(fields: IntakeFields, principal: Principal): Any {
  const key = Object.keys(H.preview).find((k) => sameFields(H.preview[k].fields, fields))
  const base = clone(key ? H.preview[key] : B1)
  base.fields = fields
  base.principal = { ...base.principal, kind: principal.kind, inn: principal.inn ?? null }
  if (!key) {
    const qty = fields.qty_t ?? 0
    const max = fields.max_price_t ?? 0
    const gross = qty * max
    const ts = SC.asks.map((a) => (fields.region ? tariff(a.warehouse_region, fields.region) : null)).filter((x): x is number => x !== null)
    base.fees = {
      gross_max: gross, fee_rate: BUYER_FEE_RATE, exchange_fee: roundHalfUp(gross * BUYER_FEE_RATE), deposit_rate: DEPOSIT_WORST,
      deposit_worst: roundHalfUp(gross * DEPOSIT_WORST), deposit_final: false, delivery_min_t: ts.length ? Math.min(...ts) : null,
      delivery_max_t: ts.length ? Math.max(...ts) : null, total_worst: gross + roundHalfUp(gross * BUYER_FEE_RATE), needed_now: null,
    }
    base.warnings = max && (max < 200_000 || max > 3_000_000) ? [{ code: 'price_far_from_market', params: {} }] : []
    base.mandate_draft = { ...base.mandate_draft, mandate_id: null, line_items: [{ commodity: fields.commodity, grade: fields.grade, qty_t: qty }], amount_range: { max_price_t: max, currency: 'UZS' }, allowed_regions: [fields.region] }
  }
  base.gate = gateFor(principal, base.gate)
  base.errors = base.gate.status === 'blocked' ? [{ code: 'gate_blocked', params: {} }] : []
  if (base.errors.length) base.mandate_draft = null
  return base
}

function canonical(v: unknown): string {
  if (v === null || typeof v !== 'object') return JSON.stringify(v)
  if (Array.isArray(v)) return '[' + v.map(canonical).join(',') + ']'
  const o = v as Record<string, unknown>
  return '{' + Object.keys(o).sort().filter((k) => o[k] !== undefined).map((k) => JSON.stringify(k) + ':' + canonical(o[k])).join(',') + '}'
}

export async function sha256Hex(s: string): Promise<string> {
  const subtle = globalThis.crypto?.subtle
  if (!subtle) {
    let h = 0x811c9dc5
    for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0 }
    return h.toString(16).padStart(8, '0').repeat(8)
  }
  const buf = await subtle.digest('SHA-256', new TextEncoder().encode(s))
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, '0')).join('')
}

export async function mockSign(draft: Any): Promise<Any> {
  if (state.closed) { state.closed = false; state.escrow = {} }
  if (draft.mandate_id === B1_ID) {
    state.user = B1_ID
    state.drafts[B1_ID] = draft
    save()
    return clone(H.sign.b1)
  }
  const hash = await sha256Hex(canonical(draft))
  const id = `${hash.slice(0, 4)}-${hash.slice(4, 6)}`.toUpperCase()
  state.user = id
  state.drafts[id] = { ...draft, mandate_id: id }
  save()
  const s = clone(H.sign.b1)
  return { ...s, mandate_id: id, hash, receipt: { ...s.receipt, receipt_id: 'RC-' + hash.slice(-10).toUpperCase(), hash, mac: null } }
}

export function mockBasket(): Any {
  return clone(state.closed ? H.basket_after : H.basket_open)
}

function userOutcomes(): Any[] {
  return Object.keys(state.drafts).filter((id) => id !== B1_ID).map(userOutcome).filter(Boolean) as Any[]
}

function userOutcome(id: string): Any | null {
  const dr = state.drafts[id]
  const qty = dr?.line_items?.[0]?.qty_t ?? 0
  const max = dr?.amount_range?.max_price_t ?? 0
  const region = dr?.allowed_regions?.[0]
  const p = H.clearing.clearing_price_t as number
  let best: { a: (typeof SC.asks)[number]; t: number } | null = null
  for (const a of SC.asks) {
    const t = region ? tariff(a.warehouse_region, region) : null
    if (a.min_price_t <= p && t !== null && (!best || t < best.t)) best = { a, t }
  }
  if (!best) return { id, qty, max, filled: false, needed: null }
  return { id, qty, max, filled: max >= p + best.t, needed: p + best.t, ask: best.a, tariff: best.t }
}

export function mockRun(): Any {
  state.closed = true
  save()
  return mockResult()
}

export function mockResult(): Any {
  const r = clone(H.clearing)
  const us = userOutcomes()
  if (us.length && !state.drafts[B1_ID]) r.allocations = (r.allocations as Any[]).filter((a) => a.mandate_id !== B1_ID)
  for (const u of us) {
    if (u.filled) r.allocations.push({ mandate_id: u.id, offer_id: u.ask.offer_id, seller: u.ask.seller, qty_t: u.qty, price_t: r.clearing_price_t, tariff_t: u.tariff, delivered_price_t: r.clearing_price_t + u.tariff, lot_group_id: `LOT-${u.ask.offer_id}` })
    else r.unfilled.push({ mandate_id: u.id, qty_t: u.qty, reason: u.needed === null ? 'no_supply' : 'price_below_clearing', fill_at_max_price_t: u.needed })
  }
  return r
}

export function mockExplain(mid: string, lang: string): Any {
  const rec = H.explain[`${mid}|${lang}`]
  if (rec) return clone(rec)
  const base = clone(H.explain[`${B1_ID}|${lang}`] ?? H.explain[`${B1_ID}|ru`])
  const r = mockResult()
  const a = (r.allocations as Any[]).find((x) => x.mandate_id === mid)
  const un = (r.unfilled as Any[]).find((x) => x.mandate_id === mid)
  const dr = state.drafts[mid]
  const qty = dr?.line_items?.[0]?.qty_t ?? a?.qty_t ?? un?.qty_t ?? 0
  return {
    ...base, mandate_id: mid, your_qty: qty, your_max: dr?.amount_range?.max_price_t ?? null,
    outcome: a ? 'filled' : 'unfilled', reason: a ? null : un?.reason ?? 'price_below_clearing',
    your_filled_qty: a ? a.qty_t : 0, your_price_delivered: a ? a.delivered_price_t : null,
    needed_delivered: un?.fill_at_max_price_t ?? null, why_in: null, why_out: null, plant_region: null, sentences_ru: [], sentences_uz: [],
  }
}

const NEXT: Record<string, [string, string]> = { payment_confirmed: ['MATCHED', 'PAID_IN_FULL'], ettn_signed: ['PAID_IN_FULL', 'RELEASED'], ettn_rejected: ['PAID_IN_FULL', 'DISPUTED'], timeout: ['MATCHED', 'CANCELLED'] }

export function mockEscrow(dealId: string): Any {
  if (state.escrow[dealId]) return clone(state.escrow[dealId])
  const mid = dealId.split(':').pop() ?? ''
  const r = mockResult()
  const a = (r.allocations as Any[]).find((x) => x.mandate_id === mid)
  const e = clone(H.escrow_b1)
  e.deal_id = dealId
  e.mandate_id = mid
  if (a) {
    e.qty_t = a.qty_t
    e.amount = a.qty_t * a.delivered_price_t
    e.seller = a.seller
  } else {
    Object.assign(e, { state: 'DEPOSIT_HELD', qty_t: null, amount: null, seller: null, allowed_events: ['cleared'], history: e.history.slice(0, 1) })
  }
  return e
}

export function mockEscrowEvent(dealId: string, ev: string, reason?: string): Any {
  const e = mockEscrow(dealId)
  const step = NEXT[ev]
  if (step && e.state === step[0]) {
    const at = e.history[e.history.length - 1]?.at ?? null
    if (ev === 'ettn_signed') {
      e.history.push({ from: 'PAID_IN_FULL', event: ev, to: 'DELIVERED', at })
      e.history.push({ from: 'DELIVERED', event: 'auto_release', to: 'RELEASED', at })
    } else {
      e.history.push({ from: step[0], event: ev, to: step[1], at })
    }
    e.state = step[1]
    if (ev === 'ettn_rejected') e.dispute_reason = reason ?? 'груз не соответствует'
  }
  state.escrow[dealId] = e
  save()
  return { escrow: e, ignored: !step }
}

export async function mockAudit(dealId: string): Promise<Any> {
  const a = clone(H.audit_b1)
  const mid = dealId.split(':').pop() ?? ''
  if (mid === B1_ID) return a
  const r = mockResult()
  return { ...a, deal_id: dealId, mandate_id: mid, mandate_hash: null, allocations: (r.allocations as Any[]).filter((x) => x.mandate_id === mid), explanation_hash: await sha256Hex(canonical(mockExplain(mid, 'ru'))), signer_receipt: null }
}

export function mockRadarFlags(): Any { return clone(H.radar_flags) }
export function mockRadarGraph(): Any { return clone(H.radar_graph) }
export function mockPlants(): Any { return clone(H.plant_list) }

export function mockPlant(seller: string): Any {
  const p = clone(H.plant_before[seller] ?? H.plant_before['Toshkent Conch Cement'])
  if (!state.closed) return { ...p, last_run: null }
  const groups = (H.clearing.lot_groups as Any[]).filter((g) => g.seller === p.seller)
  return { ...p, regions: [], buy_at_price_t: 0, basket_total_t: H.basket_after.demand_t, last_run: { run_id: H.clearing.run_id, clearing_price_t: H.clearing.clearing_price_t, lot_groups: groups, sold_t: groups.reduce((s, g) => s + g.qty_t, 0) } }
}

export function mockTape(): Any {
  const t = clone(state.closed ? H.tape_after : H.tape_open)
  if (state.closed) t.items.unshift({ kind: 'basket_closed', who: H.basket_open.basket_id, qty_t: H.clearing.executed_qty_t, price_t: H.clearing.clearing_price_t, at: H.basket_open.window_end ?? t.now, status: null })
  return t
}
export function mockAi92(): Any { return clone(H.ai92) }
export function mockCalendar(): Any { return clone(H.calendar) }
export function mockChart(grade: string, region: string | null, bucket: 'day' | 'week' = 'week'): Chart {
  const c = (chartFx as unknown as Record<string, Chart>)[grade] ?? (chartFx as unknown as Record<string, Chart>)['32.5']
  if (region) return { ...c, points: [], region }
  if (bucket === 'day') return c
  const weeks = new Map<string, { pv: number; t: number; n: number; min: number; max: number }>()
  for (const p of c.points) {
    const d = new Date(p.date + 'T00:00:00Z')
    d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7))
    const k = d.toISOString().slice(0, 10)
    const w = weeks.get(k) ?? { pv: 0, t: 0, n: 0, min: Infinity, max: -Infinity }
    if (p.vwap !== null && p.volume_t) {
      w.pv += p.vwap * p.volume_t
      w.t += p.volume_t
      w.n += p.n_deals ?? 0
      w.min = Math.min(w.min, p.min ?? p.vwap)
      w.max = Math.max(w.max, p.max ?? p.vwap)
    }
    weeks.set(k, w)
  }
  const points = [...weeks.entries()].sort().map(([date, w]) => (w.t
    ? { date, vwap: Math.round(w.pv / w.t), volume_t: w.t, n_deals: w.n, min: w.min, max: w.max }
    : { date, vwap: null, volume_t: null, n_deals: null }))
  return { ...c, points }
}

const STEP = 10_000
function bands(curve: [number, number][], side: 'demand' | 'supply'): Any[] {
  const pts = [...curve].sort((a, b) => a[0] - b[0])
  const out = new Map<number, number>()
  pts.forEach(([p, q], i) => {
    const d = side === 'demand' ? q - (pts[i + 1]?.[1] ?? 0) : q - (pts[i - 1]?.[1] ?? 0)
    if (d > 0) {
      const from = Math.floor(p / STEP) * STEP
      out.set(from, (out.get(from) ?? 0) + d)
    }
  })
  return [...out.entries()].sort((a, b) => a[0] - b[0]).map(([from, q]) => ({ price_from: from, price_to: from + STEP, qty_t: q }))
}

export function mockLadder(): Any {
  const a = H.clearing.aggregates
  return {
    basket_id: H.basket_open.basket_id,
    bands_demand: bands(a.demand_curve, 'demand'),
    bands_supply: bands(a.supply_curve, 'supply'),
    totals: { bids: a.n_bids, bid_t: a.total_demand, asks: a.n_asks, ask_t: a.total_supply },
    closed: state.closed,
    clearing_price_t: state.closed ? H.clearing.clearing_price_t : null,
  }
}

export function mockMine(): Any {
  const r = state.closed ? mockResult() : null
  return {
    mandates: Object.values(state.drafts).map((d: Any) => {
      const id = d.mandate_id
      let status = 'in_basket'
      if (r) {
        const filled = (r.allocations as Any[]).filter((a) => a.mandate_id === id).reduce((s, a) => s + a.qty_t, 0)
        const qty = d.line_items?.[0]?.qty_t ?? 0
        status = filled >= qty && filled > 0 ? 'filled' : filled > 0 ? 'partial' : 'unfilled'
      }
      return {
        mandate_id: id, status, run_id: r ? r.run_id : null, deal_id: r && status !== 'unfilled' ? `${r.run_id}:${id}` : null,
        basket_id: H.basket_open.basket_id, window: H.basket_open.window, window_start: H.basket_open.window_start,
        commodity: d.line_items?.[0]?.commodity, grade: d.line_items?.[0]?.grade, qty_t: d.line_items?.[0]?.qty_t,
        region: d.allowed_regions?.[0], max_price_t: d.amount_range?.max_price_t, deadline: d.execution_window?.not_after,
        phrase: d.natural_language_description, signed_at: d.created_at,
      }
    }),
  }
}

export function mockHistory(): Any {
  if (!state.closed) return { baskets: [] }
  const r = H.clearing
  return { baskets: [{ run_id: r.run_id, date: H.basket_open.date, window: H.basket_open.window, clearing_price_t: r.clearing_price_t, executed_qty_t: r.executed_qty_t, n_bids: r.aggregates.n_bids, n_asks: r.aggregates.n_asks }] }
}
