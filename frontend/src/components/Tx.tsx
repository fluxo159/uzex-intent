import { Fragment, isValidElement, type ReactElement } from 'react'
import { DICTS, useLang, type Vars } from '../i18n'

export function Tx({ k, vars, numClass = '' }: { k: string; vars?: Vars | Record<string, Vars[string] | ReactElement>; numClass?: string }) {
  const { lang } = useLang()
  const raw = DICTS[lang][k] ?? DICTS.ru[k] ?? k
  const parts = raw.split(/(\{\w+\})/g)
  return (
    <>
      {parts.map((p, i) => {
        const m = /^\{(\w+)\}$/.exec(p)
        if (!m) return <Fragment key={i}>{p}</Fragment>
        const v = vars?.[m[1]]
        if (isValidElement(v)) return <Fragment key={i}>{v}</Fragment>
        const s = v === null || v === undefined || v === '' ? '—' : String(v)
        return /\d/.test(s) ? <span key={i} className={`mono ${numClass}`}>{s}</span> : <Fragment key={i}>{s}</Fragment>
      })}
    </>
  )
}

export function Num({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <span className={`mono ${className}`}>{children}</span>
}
