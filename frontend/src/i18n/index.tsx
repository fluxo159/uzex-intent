import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import ru from './ru.json'
import uz from './uz.json'

export type Lang = 'ru' | 'uz'
export type Vars = Record<string, string | number | null | undefined>
type Dict = Record<string, string>

export const DICTS: Record<Lang, Dict> = { ru: ru as Dict, uz: uz as Dict }
const KEY = 'intent.lang'

function readLang(): Lang {
  try {
    const v = localStorage.getItem(KEY)
    if (v === 'ru' || v === 'uz') return v
  } catch {}
  return 'ru'
}

export function translate(lang: Lang, key: string, vars?: Vars): string {
  const raw = DICTS[lang][key] ?? DICTS.ru[key] ?? key
  if (!vars) return raw
  return raw.replace(/\{(\w+)\}/g, (_, k: string) => {
    const v = vars[k]
    return v === null || v === undefined || v === '' ? '—' : String(v)
  })
}

interface LangCtx {
  lang: Lang
  setLang: (l: Lang) => void
  t: (key: string, vars?: Vars) => string
  has: (key: string) => boolean
}
const Ctx = createContext<LangCtx | null>(null)

export function LangProvider({ children, initial }: { children: ReactNode; initial?: Lang }) {
  const [lang, setLangState] = useState<Lang>(initial ?? readLang())
  const setLang = useCallback((l: Lang) => {
    setLangState(l)
    try { localStorage.setItem(KEY, l) } catch {}
  }, [])
  useEffect(() => { document.documentElement.lang = lang === 'uz' ? 'uz-Latn' : 'ru' }, [lang])
  const value = useMemo<LangCtx>(() => ({
    lang,
    setLang,
    t: (key, vars) => translate(lang, key, vars),
    has: (key) => key in DICTS[lang],
  }), [lang, setLang])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useLang(): LangCtx {
  const c = useContext(Ctx)
  if (!c) throw new Error('useLang outside LangProvider')
  return c
}

export function useT() {
  return useLang().t
}
