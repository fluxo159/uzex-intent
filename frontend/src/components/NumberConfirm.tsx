import { useLang } from '../i18n'
import { numToWords, pluralForm } from '../lib/numwords'
import { PillButton } from './PillButton'

export function NumberConfirm({ qty, price, onYes, onFix }: { qty: number | null | undefined; price: number | null | undefined; onYes: () => void; onFix: () => void }) {
  const { lang, t } = useLang()
  return (
    <section data-testid="number-confirm" className="bg-s2 rounded-card p-4 anim-rise" aria-live="polite">
      <div className="caption">{t('confirm.title')}</div>
      <p className="mt-2 text-[17px] leading-[1.45] text-ink2">
        {t('confirm.said')}{' '}
        {qty != null ? <b data-testid="confirm-qty" className="text-ink font-semibold">{t('confirm.qty', { words: numToWords(qty, lang), unit: t(`unit.t.${pluralForm(qty)}`) })}</b> : null}
        {qty != null && price != null ? ', ' : null}
        {price != null ? <b data-testid="confirm-price" className="text-ink font-semibold">{t('confirm.price', { words: numToWords(price, lang) })}</b> : null}
        . {t('confirm.question')}
      </p>
      <div className="flex gap-2 mt-4">
        <PillButton onClick={onYes} className="flex-1">{t('confirm.yes')}</PillButton>
        <PillButton variant="ghost" onClick={onFix} className="flex-1">{t('confirm.fix')}</PillButton>
      </div>
    </section>
  )
}
