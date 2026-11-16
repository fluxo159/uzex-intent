import { limitDetail } from '../api/client'
import { limitText } from '../app/auth'
import { useLang, useT } from '../i18n'
import { PillButton } from './PillButton'

export function Loading() {
  const t = useT()
  return <p className="caption py-6" role="status">{t('common.loading')}</p>
}

export function ErrorBox({ onRetry, detail }: { onRetry?: () => void; detail?: unknown }) {
  const { t, lang, has } = useLang()
  const lim = limitDetail(detail)
  if (lim) {
    return (
      <div role="alert" className="bg-s2 rounded-card p-4" data-testid="limit-box">
        <p className="text-warn text-[14px]">{limitText(lim, lang, t, has)}</p>
        {onRetry ? <PillButton variant="ghost" className="mt-3" onClick={onRetry}>{t('common.retry')}</PillButton> : null}
      </div>
    )
  }
  const msg = typeof detail === 'string' ? detail : detail instanceof Error && detail.message && !/HTTP|fetch|network/i.test(detail.message) ? detail.message : null
  return (
    <div role="alert" className="bg-s2 rounded-card p-4">
      <p className="text-bad text-[14px]">{t('common.error')}</p>
      {msg ? <p className="caption mt-1">{msg}</p> : null}
      {onRetry ? <PillButton variant="ghost" className="mt-3" onClick={onRetry}>{t('common.retry')}</PillButton> : null}
    </div>
  )
}
