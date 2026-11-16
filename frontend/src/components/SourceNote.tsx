import { useT } from '../i18n'

export function SourceNote({ extra }: { extra?: string[] }) {
  const t = useT()
  return (
    <p data-testid="source-note" className="caption mt-3">
      {[t('source.note'), ...(extra ?? [])].join(' · ')}
    </p>
  )
}
