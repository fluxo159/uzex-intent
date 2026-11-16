
export type Lang = 'ru' | 'uz'
export type RegionCode =
  | 'Andijan' | 'Bukhara' | 'Fergana' | 'Jizzakh' | 'Khorezm' | 'Namangan' | 'Navoiy'
  | 'Qashqadaryo' | 'Samarkand' | 'Sirdaryo' | 'Surkhandaryo' | 'Tashkent_region'
  | 'Tashkent_city' | 'Karakalpakstan'
export const REGIONS: RegionCode[] = [
  'Andijan', 'Bukhara', 'Fergana', 'Jizzakh', 'Khorezm', 'Namangan', 'Navoiy', 'Qashqadaryo',
  'Samarkand', 'Sirdaryo', 'Surkhandaryo', 'Tashkent_region', 'Tashkent_city', 'Karakalpakstan',
]

export type PrincipalKind = 'ip' | 'company' | 'person_2035' | 'guest'
export interface Principal { kind: PrincipalKind; inn?: string | null; display_name?: string | null; region?: string | null; principal_id?: string | null }

export interface IntakeFields {
  commodity?: string | null
  grade?: string | null
  qty_t?: number | null
  region?: string | null
  deadline?: string | null
  max_price_t?: number | null
  payment_terms?: string | null
}

export interface ParseResponse {
  fields: IntakeFields
  missing_fields: string[]
  transcript_norm: string
  source: string
  confidence_note?: string | null
}

export interface SttResponse { transcript: string; lang?: string; source?: string }

export interface GateCheck { name: string; passed: boolean; status?: 'ok' | 'warning' | 'blocked'; reason?: string | null; how_to_fix?: string | null; entity_name?: string | null; funds_available?: number | null }
export interface Gate { status: 'ok' | 'warning' | 'blocked' | 'pending'; checks: GateCheck[]; demo?: boolean; demo_label?: string | null }
export interface Code { code: string; params?: Record<string, unknown> }

export interface Preview {
  fields: IntakeFields
  gross_max: number
  fee_rate: number
  exchange_fee: number
  deposit_rate: number
  deposit_worst: number
  deposit_final?: boolean
  delivery_min_t: number | null
  delivery_max_t: number | null
  total_worst: number
  needed_now?: number
  gate: Gate
  next_basket: { basket_id: string; window?: string | null; close_time: string; open_time?: string | null }
  usual: { p10: number | null; p90: number | null } | null
  warnings: Code[]
  errors: Code[]
  mandate_draft: Record<string, unknown> | null
  hash: string | null
}

export interface SignResponse {
  mandate_id: string
  hash: string
  receipt: string
  receipt_mac?: string | null
  signed_at: string
  basket_id: string
  demo: boolean
}

export interface BasketView {
  basket_id: string
  commodity: string
  grade: string
  close_time: string
  open_time?: string | null
  window?: string | null
  status: 'open' | 'closed'
  n_buyers: number
  n_plants: number
  demand_t: number
  supply_t: number
  run_id?: string | null
}

export interface Allocation { mandate_id: string; offer_id: string; seller: string; qty_t: number; price_t: number; tariff_t: number; delivered_price_t: number; lot_group_id: string }
export interface Unfilled { mandate_id: string; qty_t: number; reason: 'price_below_clearing' | 'no_supply' | 'lot_not_formed' }
export interface LotGroup { lot_group_id: string; offer_id: string; seller: string; qty_t: number; n_mandates: number; min_lot_t: number; regions: Record<string, number> }
export interface Aggregates {
  demand_curve: [number, number][]
  supply_curve: [number, number][]
  total_demand: number
  total_supply: number
  n_bids: number
  n_asks: number
  n_executed_bids: number
  n_executed_asks?: number
  marginal_side?: string
  best_bid?: number | null
  best_ask?: number | null
}
export interface ClearingResult {
  run_id: string
  basket_id: string
  engine_version: string
  clearing_price_t: number | null
  executed_qty_t: number
  allocations: Allocation[]
  unfilled: Unfilled[]
  aggregates: Aggregates
  tie_break_used: string
  lot_groups?: LotGroup[]
  reference_price_t?: number | null
  inputs_hash: string
  closed_at?: string | null
}

export interface Explain {
  mandate_id: string
  run_id?: string
  outcome: 'filled' | 'partial' | 'unfilled'
  reason?: string | null
  your_qty: number
  your_filled_qty?: number
  your_price_delivered: number | null
  your_max: number
  clearing_price_base: number | null
  total_demand_t: number
  total_supply_t: number
  n_buyers: number
  n_plants: number
  why_in?: string | null
  why_out?: string | null
  vs_last_week?: string | null
  vs_last_week_pct?: number | null
  plant_region?: string | null
  counterfactual?: string | null
  counterfactual_overpay?: number | null
  sentences_ru?: string[]
  sentences_uz?: string[]
  seller?: string | null
  delivery_t?: number | null
  deal_id?: string | null
  needed_delivered?: number | null
  lot_collected_t?: number | null
  lot_needed_t?: number | null
  next_window?: string | null
}

export type EscrowState = 'CREATED' | 'DEPOSIT_HELD' | 'MATCHED' | 'PAID_IN_FULL' | 'DELIVERED' | 'RELEASED' | 'DISPUTED' | 'CANCELLED' | 'TIMEOUT_RELEASED'
export interface Escrow {
  deal_id: string
  state: EscrowState
  label?: { ru?: string | null; uz?: string | null }
  seller?: string | null
  deadline?: string | null
  allowed_events?: string[]
  history: { state: EscrowState; at: string; note?: string | null }[]
  amount?: number | null
  deposit?: number | null
  qty_t?: number | null
  demo: boolean
  dispute?: { reason?: string | null; days: number; draft?: string | null } | null
}
export type EscrowEvent = 'payment_confirmed' | 'ettn_signed' | 'ettn_rejected' | 'timeout'

export interface ChartPoint { date: string; vwap: number | null; volume_t: number | null; n_deals: number | null; min?: number | null; max?: number | null; open?: number | null; close?: number | null }
export interface Chart {
  points: ChartPoint[]
  grade?: string | null
  region?: string | null
  corridor?: { p10: number | null; p50: number | null; p90: number | null; n_deals?: number; from?: string; to?: string; days?: number } | null
  cancelled_excluded?: number
  n_gaps?: number
  data_cutoff?: string
  headline?: { last_vwap: number | null; last_from?: string | null; prev_vwap: number | null; prev_from?: string | null; change_pct: number | null; basis: unknown } | null
}

export interface CalendarWindow { date: string; start: string; end: string; label?: string; to_confirm?: boolean; is_open_now?: boolean }
export interface CalendarPlant { plant: string; daily_volume_t: number | null; base_price_t: number | null; base_price_date?: string | null }
export interface Calendar { now: string; windows: CalendarWindow[]; plants: CalendarPlant[]; note_ru?: string; note_uz?: string }

export interface Ai92 {
  commodity: string
  date: string
  contract: string
  seller: string
  deals: { price_t: number; qty_t: number; overpay: number }[]
  prices: number[]
  uniform_price_t: number
  overpay: number
  spread_t: number
  total_qty_t: number
  source?: string
  source_label_ru?: string
  source_label_uz?: string
  caption_ru?: string
  caption_uz?: string
  volumes_note?: string
}

export interface PlantDemand {
  seller: string
  warehouse_region: string | null
  price_t: number | null
  min_lot_t: number
  buy_at_price_t: number
  basket_total_t: number
  regions: { region: string; qty_t: number; n_mandates: number; deadline: string | null; lots: number; rest_t: number; sizes?: number[] }[]
  sellers?: string[]
  last_run?: { run_id: string; clearing_price_t: number | null; lot_groups: LotGroup[]; sold_t: number } | null
}

export interface RadarNode { id: string; name: string; role?: string; region?: string }
export interface RadarEdge { from: string; to: string; kind?: string; fact: string }
export interface RadarFlag { flag_id: string; participants: { id: string; name: string }[]; edges: RadarEdge[]; summary?: string; appeal?: string }
export interface RadarGraph { nodes: RadarNode[]; edges: RadarEdge[]; demo?: boolean; demo_label?: string }
export interface RadarFlags { run_id?: string; flags: RadarFlag[]; demo?: boolean; demo_label?: string; note?: string }

export interface Audit {
  deal_id: string
  mandate_hash: string | null
  inputs_hash: string | null
  engine_version: string | null
  tie_break_used: string | null
  clearing_price: number | null
  qty_t: number | null
  explanation_hash?: string | null
  signer_receipt?: string | null
  approved_by?: string | null
  decided_by?: string | null
  appeal_channel?: string | null
  appeal_channel_uz?: string | null
  reference_price?: number | null
}

export interface TapeItem { kind: 'mandate' | 'offer' | 'basket_closed'; who: string; qty_t: number; at: string; status?: 'filled' | 'waiting' | null; price_t?: number | null }
export interface Tape { now: string; items: TapeItem[] }

export interface LadderBand { price_from: number; price_to: number; qty_t: number }
export interface Ladder {
  basket_id?: string | null
  bands_demand: LadderBand[]
  bands_supply: LadderBand[]
  totals: { bids: number; bid_t: number; asks: number; ask_t: number }
  closed: boolean
  clearing_price_t: number | null
}

export type OrderStatus = 'in_basket' | 'filled' | 'partial' | 'unfilled' | 'expired'
export interface MyOrder {
  mandate_id: string
  status: OrderStatus
  run_id?: string | null
  deal_id?: string | null
  basket_id?: string | null
  window?: string | null
  window_start?: string | null
  commodity?: string | null
  grade?: string | null
  qty_t?: number | null
  region?: string | null
  max_price_t?: number | null
  deadline?: string | null
  phrase?: string | null
  signed_at?: string | null
  filled_t?: number | null
  clearing_price_t?: number | null
  delivered_price_t?: number | null
  sellers?: string[]
  fill_at_max_price_t?: number | null
  reason?: string | null
}

export interface PastBasket { run_id: string; date: string | null; window: string | null; clearing_price_t: number | null; executed_qty_t: number | null; n_bids: number | null; n_asks: number | null; demo?: boolean }
