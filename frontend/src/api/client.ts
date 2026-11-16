import * as mock from './mock'
import type {
  Ai92, Audit, BasketView, Calendar, Chart, ClearingResult, Escrow, EscrowEvent, Explain, IntakeFields,
  Ladder, Lang, MyOrder, ParseResponse, PastBasket, PlantDemand, Preview, Principal, RadarFlags, RadarGraph, SignResponse, SttResponse, Tape,
} from './types'
import { normHistory, normLadder, normMine } from './normalize'
import { normAudit, normBasket, normEscrow, normExplain, normParse, normPlant, normPreview, normSign } from './normalize'

const env = (import.meta as unknown as { env: Record<string, string | undefined> }).env ?? {}
export const MOCK_ONLY = env.VITE_MOCK === '1'
const BASE = (env.VITE_API_URL || '/api').replace(/\/$/, '')

type Listener = (used: boolean) => void
const mockPaths = new Set<string>()
const listeners = new Set<Listener>()
const mockOn = () => MOCK_ONLY || mockPaths.size > 0
export function onMockUsed(fn: Listener) {
  listeners.add(fn)
  fn(mockOn())
  return () => { listeners.delete(fn) }
}
function setMock(key: string, used: boolean) {
  const before = mockOn()
  if (used) mockPaths.add(key)
  else mockPaths.delete(key)
  const after = mockOn()
  if (before !== after) listeners.forEach((l) => l(after))
}

export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : `HTTP ${status}`)
    this.status = status
    this.detail = detail
  }
}

class Unavailable extends Error {}

const ADMIN_KEY = 'intent.adminToken'
export function adminToken(): string | null {
  try { return sessionStorage.getItem(ADMIN_KEY) } catch { return null }
}
export function setAdminToken(tok: string | null) {
  try { if (tok) sessionStorage.setItem(ADMIN_KEY, tok); else sessionStorage.removeItem(ADMIN_KEY) } catch {}
}

export interface LimitDetail { code: string; retry_after?: number; n?: number; message_ru?: string; message_uz?: string }
export function limitDetail(e: unknown): LimitDetail | null {
  const d = e instanceof ApiError ? e.detail : e
  return d && typeof d === 'object' && typeof (d as LimitDetail).code === 'string' ? d as LimitDetail : null
}
type LimitListener = (d: LimitDetail) => void
const limitListeners = new Set<LimitListener>()
export function onLimit(fn: LimitListener) {
  limitListeners.add(fn)
  return () => { limitListeners.delete(fn) }
}

async function http(method: string, path: string, body?: unknown, timeoutMs = 12000): Promise<unknown> {
  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), timeoutMs)
  let res: Response
  try {
    const headers: Record<string, string> = {}
    if (body !== undefined && !(body instanceof FormData)) headers['Content-Type'] = 'application/json'
    const adm = adminToken()
    if (adm) headers['X-Admin-Token'] = adm
    res = await fetch(BASE + path, {
      method,
      headers,
      credentials: 'include',
      body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
      signal: ctl.signal,
    })
  } catch {
    throw new Unavailable('network')
  } finally {
    clearTimeout(timer)
  }
  if (res.status === 502 || res.status === 503 || res.status === 504) throw new Unavailable('proxy')
  const text = await res.text()
  if (res.status === 500 && !text) throw new Unavailable('proxy')
  let data: unknown = null
  try { data = text ? JSON.parse(text) : null } catch { data = text }
  if (!res.ok) {
    const detail = (data as { detail?: unknown } | null)?.detail ?? data
    if ((res.status === 404 && detail === 'Not Found') || res.status === 405 || res.status === 501) throw new Unavailable('route')
    if (res.status === 429) {
      const d = limitDetail(detail) ?? { code: 'rate_limited' }
      const ra = Number(res.headers.get('Retry-After'))
      if (d.retry_after === undefined && ra > 0) d.retry_after = ra
      limitListeners.forEach((l) => l(d))
    }
    throw new ApiError(res.status, detail)
  }
  return data
}

async function call(real: () => Promise<unknown>, fallback: () => unknown, any404 = false): Promise<unknown> {
  if (MOCK_ONLY) return fallback()
  const key = real.toString()
  try {
    const r = await real()
    setMock(key, false)
    return r
  } catch (e) {
    if (e instanceof Unavailable || (any404 && e instanceof ApiError && e.status === 404)) {
      setMock(key, true)
      return fallback()
    }
    if (e instanceof ApiError) setMock(key, false)
    throw e
  }
}

const q = (o: Record<string, string | number | null | undefined>) => {
  const s = Object.entries(o).filter(([, v]) => v !== null && v !== undefined && v !== '').map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&')
  return s ? '?' + s : ''
}
const enc = encodeURIComponent

export type Level = 'guest' | 'jury' | 'admin'
export interface Me {
  level: Level
  principal_id: string | null
  limits_left: Record<string, number>
  llm: boolean
  voice: boolean
  can_close_basket: boolean
  protected: boolean
}
const meOffline = (): Me => ({
  level: adminToken() ? 'admin' : 'guest', principal_id: null, limits_left: {},
  llm: true, voice: true, can_close_basket: true, protected: false,
})

export const api = {
  me: async (): Promise<Me> => (await call(() => http('GET', '/auth/me'), meOffline)) as Me,
  enterCode: async (code: string): Promise<Me> => (await call(() => http('POST', '/auth/code', { code }), meOffline)) as Me,
  logout: async (): Promise<void> => { await call(() => http('POST', '/auth/logout'), () => ({})) },

  parse: async (text: string, lang: Lang): Promise<ParseResponse> =>
    normParse(await call(() => http('POST', '/intake/parse', { text, lang }), () => mock.mockParse(text))),

  stt: async (audio: Blob, lang: Lang): Promise<SttResponse> =>
    (await call(() => {
      const fd = new FormData()
      fd.append('file', audio, 'voice.webm')
      fd.append('lang', lang)
      return http('POST', '/intake/stt', fd, 30000)
    }, () => mock.mockStt())) as SttResponse,

  preview: async (fields: IntakeFields, principal: Principal, lang: Lang, transcript: string): Promise<Preview> =>
    normPreview(await call(
      () => http('POST', '/mandate/preview', { fields, principal: { kind: principal.kind, inn: principal.inn ?? null, region: principal.region ?? fields.region ?? null, principal_id: principal.principal_id ?? undefined }, transcript_norm: transcript, lang }),
      () => mock.mockPreview(fields, principal),
    ), fields),

  sign: async (draft: Record<string, unknown>): Promise<SignResponse> =>
    normSign(await call(() => http('POST', '/mandate/sign', { mandate: draft }), () => mock.mockSign(draft))),

  basket: async (id: string): Promise<BasketView> =>
    normBasket(await call(() => http('GET', `/book/basket/${enc(id || 'open')}`), () => mock.mockBasket())),

  runClearing: async (basketId: string): Promise<ClearingResult> =>
    (await call(() => http('POST', `/clearing/run/${enc(basketId || 'open')}`), () => mock.mockRun())) as ClearingResult,

  result: async (runId: string): Promise<ClearingResult> =>
    (await call(() => http('GET', `/clearing/result/${enc(runId)}`), () => mock.mockResult())) as ClearingResult,

  explain: async (mandateId: string, lang: Lang): Promise<Explain> =>
    normExplain(await call(() => http('GET', `/explain/${enc(mandateId)}${q({ lang })}`), () => mock.mockExplain(mandateId, lang))),

  escrow: async (dealId: string): Promise<Escrow> =>
    normEscrow(await call(() => http('GET', `/escrow/${enc(dealId)}`), () => mock.mockEscrow(dealId))),

  escrowEvent: async (dealId: string, event: EscrowEvent, reason?: string): Promise<Escrow> =>
    normEscrow(await call(() => http('POST', `/escrow/${enc(dealId)}/event`, { type: event, reason }), () => mock.mockEscrowEvent(dealId, event, reason))),

  chart: async (grade: string, region: string | null, bucket: 'day' | 'week' = 'week'): Promise<Chart> =>
    (await call(() => http('GET', `/market/chart${q({ commodity: 'cement', grade, region, bucket })}`), () => mock.mockChart(grade, region, bucket))) as Chart,

  calendar: async (): Promise<Calendar> => (await call(() => http('GET', '/market/calendar'), () => mock.mockCalendar())) as Calendar,

  ai92: async (): Promise<Ai92> => (await call(() => http('GET', '/market/counterfactual/ai92'), () => mock.mockAi92())) as Ai92,

  plants: async (): Promise<string[]> => {
    const r = (await call(() => http('GET', '/plant'), () => mock.mockPlants())) as { plants?: { seller: string }[] }
    return (r.plants ?? []).map((p) => p.seller)
  },

  plant: async (seller: string): Promise<PlantDemand> =>
    normPlant(await call(() => http('GET', `/plant/${enc(seller)}/demand`), () => mock.mockPlant(seller))),

  radarFlags: async (runId: string): Promise<RadarFlags> =>
    (await call(() => http('GET', `/radar/flags/${enc(runId)}`), () => mock.mockRadarFlags())) as RadarFlags,

  radarGraph: async (): Promise<RadarGraph> => (await call(() => http('GET', '/radar/graph'), () => mock.mockRadarGraph())) as RadarGraph,

  audit: async (dealId: string): Promise<Audit> => normAudit(await call(() => http('GET', `/audit/${enc(dealId)}`), () => mock.mockAudit(dealId))),

  tape: async (n = 50): Promise<Tape> => (await call(() => http('GET', `/book/tape${q({ n })}`), () => mock.mockTape())) as Tape,

  ladder: async (basket = 'open', step = 10000): Promise<Ladder> =>
    normLadder(await call(() => http('GET', `/book/ladder${q({ basket, step })}`), () => mock.mockLadder())),

  mine: async (principalId: string | null): Promise<MyOrder[] | null> => {
    const r = await call(() => http('GET', `/mandate/mine${q({ principal_id: principalId })}`), () => ({ _missing: true, ...(mock.mockMine() as object) }), true)
    return (r as { _missing?: boolean })._missing && !MOCK_ONLY ? null : normMine(r)
  },

  history: async (grade = '32.5'): Promise<PastBasket[]> =>
    normHistory(await call(() => http('GET', `/clearing/history${q({ commodity: 'cement', grade })}`), () => mock.mockHistory())),

  reset: () => call(() => http('POST', '/demo/reset'), () => mock.mockReset()),
}

export function resetLocalMock() {
  mock.mockReset()
}
