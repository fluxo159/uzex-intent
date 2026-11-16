import { useT } from '../i18n'
import { dateLong } from '../lib/labels'
import { fmtTime, parseYmd } from '../lib/format'

export function When({ start, end, window }: { start: string | null | undefined; end?: string | null; window?: string | null }) {
  const t = useT()
  const p = parseYmd(start)
  if (!p || !start) return <>—</>
  const wd = new Date(Date.UTC(p.y, p.m - 1, p.d)).getUTCDay()
  const time = window ?? `${fmtTime(start)}${end ? `–${fmtTime(end)}` : ''}`
  return <>{t(`wd.${wd}`)}, {dateLong(t, start)}, <span className="mono">{time}</span></>
}
