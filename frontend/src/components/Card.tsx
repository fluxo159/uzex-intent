import type { ReactNode } from 'react'

export function Card({ title, badge, children, className = '', tight = false }: { title?: ReactNode; badge?: ReactNode; children: ReactNode; className?: string; tight?: boolean }) {
  return (
    <section className={`bg-s2 rounded-card ${tight ? 'px-5 py-2' : 'px-5 py-4'} ${className}`}>
      {title || badge ? (
        <div className="flex items-center justify-between gap-2 mb-2">
          {title ? <h3 className="text-[13px] text-ink3">{title}</h3> : <span />}
          {badge}
        </div>
      ) : null}
      {children}
    </section>
  )
}

export function KV({ k, v, vClass = '' }: { k: ReactNode; v: ReactNode; vClass?: string }) {
  return (
    <div className="kv">
      <span>{k}</span>
      <span className={vClass}>{v}</span>
    </div>
  )
}
