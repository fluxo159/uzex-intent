import type { ReactNode } from 'react'

export function Screen({ top, children, aside, wide = false }: { step?: number; top?: ReactNode; children: ReactNode; aside?: ReactNode; wide?: boolean }) {
  return (
    <div className="lg:grid lg:grid-cols-3 lg:gap-8">
      <div className={`w-full ${wide && !aside ? 'lg:col-span-3' : 'lg:col-span-2'} ${wide ? '' : 'max-w-[560px]'}`}>
        {top}
        <div className="flex flex-col gap-4">{children}</div>
      </div>
      {aside ? <div className="mt-6 lg:mt-0">{aside}</div> : null}
    </div>
  )
}

export function Title({ children, sub }: { children: ReactNode; sub?: ReactNode }) {
  return (
    <div>
      <h1 className="h-page">{children}</h1>
      {sub ? <p className="text-[14px] text-ink3 mt-2">{sub}</p> : null}
    </div>
  )
}
