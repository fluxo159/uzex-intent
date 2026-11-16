import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from '../api/client'
import type { BasketView, ClearingResult, IntakeFields, Principal } from '../api/types'

export type Door = 'business' | 'person' | 'guest' | null
export type Instrument = '32.5' | '42.5' | 'ai92'

export interface Account { door: Door; inn: string; guestId: string; name?: string | null; funds?: number | null }

export interface LocalOrder {
  mandate_id: string
  fields: IntakeFields
  phrase: string
  signed_at: string
  basket_id: string
  window: string | null
  window_start: string | null
  hash: string
  receipt: string
}

export interface Prefill { text?: string; fields?: IntakeFields; key: number }

const ACC_KEY = 'intent.account'
const read = <T,>(k: string, store: Storage | null, d: T): T => {
  try {
    const v = store?.getItem(k)
    return v ? (JSON.parse(v) as T) : d
  } catch { return d }
}
const write = (k: string, store: Storage | null, v: unknown) => {
  try { store?.setItem(k, JSON.stringify(v)) } catch {}
}
const ls = typeof localStorage !== 'undefined' ? localStorage : null
const ss = typeof sessionStorage !== 'undefined' ? sessionStorage : null

export function principalOf(a: Account): Principal {
  if (a.door === 'person') return { kind: 'person_2035', inn: null, principal_id: 'person_2035' }
  if (a.door === 'guest') return { kind: 'guest', inn: null, principal_id: a.guestId }
  return { kind: 'ip', inn: a.inn || null, principal_id: a.inn || null }
}
export function principalIdOf(a: Account): string {
  if (a.door === 'person') return 'person_2035'
  if (a.door === 'guest') return a.guestId
  return a.inn || 'anon'
}

interface Ctx {
  account: Account
  setAccount: (a: Partial<Account>) => void
  principal: Principal
  principalId: string
  instrument: Instrument
  setInstrument: (i: Instrument) => void
  orders: LocalOrder[]
  addOrder: (o: LocalOrder) => void
  runs: Record<string, ClearingResult>
  addRun: (r: ClearingResult) => void
  prefill: Prefill | null
  setPrefill: (p: Omit<Prefill, 'key'> | null) => void
  basket: BasketView | null
  refreshBasket: () => void
  tick: number
  bump: () => void
  resetAll: () => void
}
const C = createContext<Ctx | null>(null)

const newGuestId = () => 'guest-' + Math.random().toString(36).slice(2, 10)

export function StoreProvider({ children, initial }: { children: ReactNode; initial?: { account?: Partial<Account>; orders?: LocalOrder[]; instrument?: Instrument } }) {
  const [account, setAcc] = useState<Account>(() => ({ door: null, inn: '900000005', guestId: newGuestId(), ...read<Partial<Account>>(ACC_KEY, ls, {}), ...(initial?.account ?? {}) }))
  const principalId = principalIdOf(account)
  const ordersKey = `intent.orders.${principalId}`
  const [orders, setOrders] = useState<LocalOrder[]>(() => initial?.orders ?? read<LocalOrder[]>(ordersKey, ls, []))
  const [instrument, setInstrument] = useState<Instrument>(initial?.instrument ?? '32.5')
  const [runs, setRuns] = useState<Record<string, ClearingResult>>(() => read(`intent.runs`, ss, {}))
  const [prefill, setPf] = useState<Prefill | null>(null)
  const [basket, setBasket] = useState<BasketView | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => { setOrders(initial?.orders ?? read<LocalOrder[]>(ordersKey, ls, [])) }, [ordersKey]) // eslint-disable-line react-hooks/exhaustive-deps

  const setAccount = useCallback((a: Partial<Account>) => {
    setAcc((prev) => {
      const next = { ...prev, ...a }
      write(ACC_KEY, ls, next)
      return next
    })
  }, [])
  const addOrder = useCallback((o: LocalOrder) => {
    setOrders((prev) => {
      const next = [o, ...prev.filter((x) => x.mandate_id !== o.mandate_id)]
      write(ordersKey, ls, next)
      return next
    })
  }, [ordersKey])
  const addRun = useCallback((r: ClearingResult) => {
    setRuns((prev) => {
      const next = { ...prev, [r.run_id]: r }
      write('intent.runs', ss, next)
      return next
    })
  }, [])
  const setPrefill = useCallback((p: Omit<Prefill, 'key'> | null) => setPf(p ? { ...p, key: Date.now() } : null), [])
  const bump = useCallback(() => setTick((x) => x + 1), [])

  const refreshBasket = useCallback(() => {
    api.basket('open').then(setBasket).catch(() => undefined)
  }, [])
  useEffect(() => {
    refreshBasket()
    const id = setInterval(refreshBasket, 5000)
    return () => clearInterval(id)
  }, [refreshBasket, tick])

  const resetAll = useCallback(() => {
    setOrders([])
    write(ordersKey, ls, [])
    setRuns({})
    write('intent.runs', ss, {})
    setPf(null)
    setTick((x) => x + 1)
  }, [ordersKey])

  const value = useMemo<Ctx>(() => ({
    account, setAccount, principal: principalOf(account), principalId, instrument, setInstrument,
    orders, addOrder, runs, addRun, prefill, setPrefill, basket, refreshBasket, tick, bump, resetAll,
  }), [account, setAccount, principalId, instrument, orders, addOrder, runs, addRun, prefill, setPrefill, basket, refreshBasket, tick, bump, resetAll])
  return <C.Provider value={value}>{children}</C.Provider>
}

export function useStore(): Ctx {
  const c = useContext(C)
  if (!c) throw new Error('useStore outside StoreProvider')
  return c
}

export function useViewport(): 'desktop' | 'tablet' | 'phone' {
  const get = (): 'desktop' | 'tablet' | 'phone' => {
    const w = typeof window !== 'undefined' ? window.innerWidth : 1440
    return w >= 1024 ? 'desktop' : w >= 768 ? 'tablet' : 'phone'
  }
  const [v, setV] = useState(get)
  useEffect(() => {
    const on = () => setV(get())
    window.addEventListener('resize', on)
    return () => window.removeEventListener('resize', on)
  }, [])
  return v
}
