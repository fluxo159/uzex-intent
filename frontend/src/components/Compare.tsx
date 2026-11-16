import type { ReactNode } from 'react'
import { useT } from '../i18n'

export function Compare({ rows, big = false }: { rows: { key: string; today: ReactNode; ours: ReactNode }[]; big?: boolean }) {
  const t = useT()
  return (
    <div data-testid="compare" className="grid grid-cols-2 gap-2">
      <div className="caption px-1">{t('compare.today')}</div>
      <div className="caption px-1 text-lime">{t('compare.ours')}</div>
      {rows.map((r) => (
        <div key={r.key} className="contents">
          <div className={`bg-s1 rounded-chip px-3 py-2 text-mute ${big ? 'text-[15px]' : 'text-[13px]'}`}>{r.today}</div>
          <div className={`bg-s2 rounded-chip px-3 py-2 text-ink ${big ? 'text-[15px]' : 'text-[13px]'}`}>{r.ours}</div>
        </div>
      ))}
    </div>
  )
}
