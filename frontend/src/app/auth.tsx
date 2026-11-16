import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { api, ApiError, limitDetail, setAdminToken, type LimitDetail, type Me } from '../api/client'

export const ME_UNKNOWN: Me = {
  level: 'guest', principal_id: null, limits_left: {}, llm: false, voice: false, can_close_basket: false, protected: true,
}

interface AuthCtx {
  me: Me
  ready: boolean
  applyCode: (code: string) => Promise<LimitDetail | null>
  logout: () => Promise<void>
  refresh: () => Promise<void>
}
const C = createContext<AuthCtx | null>(null)

export const ME_OPEN: Me = {
  level: 'guest', principal_id: null, limits_left: {}, llm: true, voice: true, can_close_basket: true, protected: false,
}

function readParams(search: string): { k: string | null; adm: string | null } {
  const sp = new URLSearchParams(search)
  const k = sp.get('k')
  const adm = sp.get('admin')
  if (adm && adm !== '1') setAdminToken(adm)
  return { k, adm }
}

export function AuthProvider({ children, initial }: { children: ReactNode; initial?: Me }) {
  const [me, setMe] = useState<Me>(initial ?? ME_UNKNOWN)
  const [ready, setReady] = useState(!!initial)
  const loc = useLocation()
  const nav = useNavigate()
  const started = useRef(false)
  const [params] = useState(() => readParams(loc.search))

  const refresh = useCallback(async () => {
    try { setMe(await api.me()) } catch {} finally { setReady(true) }
  }, [])

  const applyCode = useCallback(async (code: string): Promise<LimitDetail | null> => {
    try {
      setMe(await api.enterCode(code.trim()))
      return null
    } catch (e) {
      return limitDetail(e) ?? { code: e instanceof ApiError && e.status === 401 ? 'bad_code' : 'code_failed' }
    } finally { setReady(true) }
  }, [])

  const logout = useCallback(async () => {
    try { await api.logout() } catch {}
    await refresh()
  }, [refresh])

  useEffect(() => {
    if (started.current) return
    started.current = true
    const { k, adm } = params
    const sp = new URLSearchParams(loc.search)
    sp.delete('admin')
    sp.delete('k')
    if (k !== null || adm !== null) {
      const qs = sp.toString()
      nav({ pathname: loc.pathname, search: qs ? `?${qs}` : '', hash: loc.hash }, { replace: true })
    }
    if (k) void applyCode(k)
    else if (!initial) void refresh()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const value = useMemo<AuthCtx>(() => ({ me, ready, applyCode, logout, refresh }), [me, ready, applyCode, logout, refresh])
  return <C.Provider value={value}>{children}</C.Provider>
}

export function useAuth(): AuthCtx {
  const c = useContext(C)
  if (!c) throw new Error('useAuth outside AuthProvider')
  return c
}

export function limitText(d: LimitDetail, lang: 'ru' | 'uz', t: (k: string, v?: Record<string, string | number>) => string, has: (k: string) => boolean): string {
  const s = Math.max(1, Math.round(d.retry_after ?? 0))
  const vars = { s, m: Math.max(1, Math.ceil(s / 60)), n: d.n ?? '' } as Record<string, string | number>
  if (has(`acc.err.${d.code}`)) return t(`acc.err.${d.code}`, vars)
  const own = lang === 'uz' ? d.message_uz : d.message_ru
  return own || t('acc.err.rate_limited', vars)
}
