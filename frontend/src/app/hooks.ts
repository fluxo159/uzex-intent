import { useEffect, useRef, useState } from 'react'
import { ApiError, api } from '../api/client'
import type { MyOrder, OrderStatus } from '../api/types'
import { useLang } from '../i18n'
import { useAuth } from './auth'
import { useStore, type LocalOrder } from './store'

const POLL_MS = 6000

function fromLocal(o: LocalOrder): MyOrder {
  return {
    mandate_id: o.mandate_id, status: 'in_basket', basket_id: o.basket_id, window: o.window, window_start: o.window_start,
    commodity: o.fields.commodity ?? null, grade: o.fields.grade ?? null, qty_t: o.fields.qty_t ?? null, region: o.fields.region ?? null,
    max_price_t: o.fields.max_price_t ?? null, deadline: o.fields.deadline ?? null, phrase: o.phrase, signed_at: o.signed_at,
  }
}

export function useMyOrders(): { orders: MyOrder[]; loading: boolean } {
  const { orders: local, principalId: localId, tick } = useStore()
  const { me } = useAuth()
  const principalId = me.protected ? null : localId
  const who = me.protected ? `cookie:${me.principal_id ?? ''}:${me.level}` : localId
  const { lang } = useLang()
  const [list, setList] = useState<MyOrder[]>(() => local.map(fromLocal))
  const [loading, setLoading] = useState(true)
  const localRef = useRef(local)
  localRef.current = local

  useEffect(() => {
    let alive = true
    const load = async () => {
      const loc = localRef.current
      let backend: MyOrder[] | null = null
      try { backend = await api.mine(principalId) } catch { backend = null }
      const byId = new Map<string, MyOrder>()
      const known = backend ? new Set(backend.map((b) => b.mandate_id)) : null
      for (const o of loc) if (!known || known.has(o.mandate_id)) byId.set(o.mandate_id, fromLocal(o))
      if (backend) {
        for (const b of backend) {
          const prev = byId.get(b.mandate_id)
          byId.set(b.mandate_id, { ...prev, ...Object.fromEntries(Object.entries(b).filter(([, v]) => v !== null && v !== undefined)), phrase: prev?.phrase || b.phrase } as MyOrder)
        }
      } else {
        await Promise.all([...byId.values()].map(async (o) => {
          try {
            const e = await api.explain(o.mandate_id, lang)
            const st: OrderStatus = e.outcome === 'filled' ? 'filled' : e.outcome === 'partial' ? 'partial' : 'unfilled'
            byId.set(o.mandate_id, { ...o, status: st, run_id: e.run_id ?? null, deal_id: e.deal_id ?? null })
          } catch (err) {
            if (!(err instanceof ApiError && err.status === 404)) return
          }
        }))
      }
      const today = new Date().toISOString().slice(0, 10)
      const out = [...byId.values()].map((o) => (o.status === 'in_basket' && o.deadline && o.deadline < today ? { ...o, status: 'expired' as const } : o))
      out.sort((a, b) => (a.signed_at ?? '') !== (b.signed_at ?? '') ? ((a.signed_at ?? '') < (b.signed_at ?? '') ? 1 : -1) : (a.mandate_id < b.mandate_id ? 1 : -1))
      if (alive) { setList(out); setLoading(false) }
    }
    void load()
    const id = setInterval(load, POLL_MS)
    return () => { alive = false; clearInterval(id) }
  }, [who, tick, local.length, lang]) // eslint-disable-line react-hooks/exhaustive-deps

  return { orders: list, loading }
}

export function useNow(interval = 1000): Date {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), interval)
    return () => clearInterval(id)
  }, [interval])
  return now
}

export function minutesUntil(iso: string | null | undefined, now: Date): number | null {
  if (!iso) return null
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso)
  if (!m) return null
  const target = new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5])
  const diff = Math.round((target.getTime() - now.getTime()) / 60000)
  return diff > 0 ? diff : null
}
