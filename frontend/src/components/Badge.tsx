import { useT } from '../i18n'

export type BadgeKind = 'demo' | 'demoSign' | 'future' | 'data' | 'filled' | 'partial' | 'unfilled' | 'waiting' | 'mock' | 'demoTariff' | 'demoVolume' | 'guest' | 'fictional'

const STYLE: Record<BadgeKind, string> = {
  demo: 'bg-warn-bg text-warn',
  demoSign: 'bg-warn-bg text-warn',
  demoTariff: 'bg-warn-bg text-warn',
  demoVolume: 'bg-warn-bg text-warn',
  guest: 'bg-warn-bg text-warn',
  fictional: 'bg-warn-bg text-warn',
  mock: 'bg-warn-bg text-warn',
  future: 'bg-lav-bg text-lav',
  data: 'bg-s1 text-ink3',
  filled: 'bg-lime text-lime-ink',
  partial: 'bg-s3 text-lime',
  unfilled: 'bg-s3 text-bad',
  waiting: 'bg-s1 text-mute',
}

export function Badge({ kind, text, testId }: { kind: BadgeKind; text?: string; testId?: string }) {
  const t = useT()
  return (
    <span
      data-testid={testId ?? `badge-${kind}`}
      data-badge={kind}
      className={`inline-block rounded-full px-[10px] py-1 text-[11px] leading-[14px] ${text ? 'whitespace-normal' : 'lowercase whitespace-nowrap'} ${STYLE[kind]}`}
    >
      {text ?? t(`badge.${kind}`)}
    </span>
  )
}
