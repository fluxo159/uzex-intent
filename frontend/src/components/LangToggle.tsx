import { useLang } from '../i18n'

export function LangToggle() {
  const { lang, setLang, t } = useLang()
  return (
    <div role="group" aria-label={t('lang.label')} className="flex items-center gap-1 text-[12px]">
      {(['ru', 'uz'] as const).map((l, i) => (
        <span key={l} className="flex items-center gap-1">
          {i > 0 ? <span className="text-mute">·</span> : null}
          <button
            type="button"
            aria-pressed={lang === l}
            onClick={() => setLang(l)}
            className={`tap focus-ring px-1 py-1 ${lang === l ? 'text-ink' : 'text-mute hover:text-ink3'}`}
          >
            {t(`lang.${l}`)}
          </button>
        </span>
      ))}
    </div>
  )
}
