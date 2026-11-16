import { useT } from '../i18n'

export function AiPanel() {
  const t = useT()
  return (
    <div data-testid="ai-panel" className="grid grid-cols-2 gap-2 mt-2">
      <div className="bg-s1 rounded-chip p-3">
        <div className="caption mb-1">{t('ai.doesnt')}</div>
        {[1, 2, 3].map((i) => <div key={i} className="text-[13px] text-ink3 leading-[1.8]">✕ {t(`ai.no.${i}`)}</div>)}
      </div>
      <div className="bg-s1 rounded-chip p-3">
        <div className="caption mb-1 text-lime">{t('ai.does')}</div>
        {[1, 2, 3].map((i) => <div key={i} className="text-[13px] text-ink leading-[1.8]"><span className="text-lime">✓</span> {t(`ai.yes.${i}`)}</div>)}
      </div>
    </div>
  )
}
