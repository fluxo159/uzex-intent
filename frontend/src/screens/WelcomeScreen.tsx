import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStore, type Door } from '../app/store'
import { Logo } from '../app/Shell'
import { Badge } from '../components/Badge'
import { LangToggle } from '../components/LangToggle'
import { LiveTape } from '../components/LiveTape'
import { PrimaryButton } from '../components/PillButton'
import { useT } from '../i18n'

export function WelcomeScreen() {
  const t = useT()
  const nav = useNavigate()
  const { account, setAccount } = useStore()
  const [door, setDoor] = useState<Door>(account.door === 'person' ? 'person' : 'business')
  const [inn, setInn] = useState(account.inn || '900000005')
  const innOk = /^\d{9}$/.test(inn)
  const canGo = door === 'person' || (door === 'business' && innOk)
  const go = () => {
    if (!canGo) return
    setAccount({ door, inn: door === 'business' ? inn : account.inn })
    nav('/market')
  }
  const doorCls = (d: Door) => `text-left w-full bg-s2 rounded-card p-4 focus-ring ${door === d ? 'ring-2 ring-lime' : 'hover:bg-[#1d211b]'}`
  return (
    <div className="min-h-screen px-4 py-5 max-w-[520px] mx-auto flex flex-col">
      <div className="flex items-center justify-between"><Logo /><LangToggle /></div>
      <h1 className="h1 mt-8">{t('entry.title')}</h1>
      <p className="text-[14px] text-ink3 mt-2 mb-5">{t('entry.sub')}</p>
      <div role="radiogroup" className="flex flex-col gap-[10px]">
        <div className={doorCls('business')}>
          <button type="button" role="radio" aria-checked={door === 'business'} aria-label={t('entry.door.business')} onClick={() => setDoor('business')} className="w-full text-left focus-ring">
            <div className="text-[16px] font-semibold">{t('entry.door.business')}</div>
            <div className="caption mt-1">{t('entry.door.business.hint')}</div>
          </button>
          {door === 'business' ? (
            <label className="block mt-3">
              <span className="caption">{t('entry.inn.label')}</span>
              <input inputMode="numeric" maxLength={9} value={inn} placeholder={t('entry.inn.placeholder')}
                onChange={(e) => setInn(e.target.value.replace(/\D/g, '').slice(0, 9))} onKeyDown={(e) => { if (e.key === 'Enter') go() }}
                className="mono mt-1 w-full bg-s1 rounded-chip px-3 py-2 text-[16px] text-ink2 outline-none focus:ring-2 focus:ring-lime placeholder:text-mute" />
              <span className={`caption block mt-1 ${inn.length > 0 && !innOk ? 'text-bad' : ''}`}>{inn.length > 0 && !innOk ? t('entry.inn.bad') : t('entry.inn.hint')}</span>
            </label>
          ) : null}
        </div>
        <button type="button" role="radio" aria-checked={door === 'person'} aria-label={t('entry.door.person')} onClick={() => setDoor('person')} className={doorCls('person')}>
          <div className="flex items-start justify-between gap-2"><div className="text-[16px] font-semibold">{t('entry.door.person')}</div><Badge kind="future" /></div>
          <div className="caption mt-1">{t('entry.door.person.hint')}</div>
        </button>
      </div>
      <PrimaryButton className="mt-5" onClick={go} disabled={!canGo}>{t('welcome.cta')}</PrimaryButton>
      <div className="mt-5"><LiveTape rows={3} /></div>
    </div>
  )
}

export function GuestScreen() {
  const t = useT()
  const nav = useNavigate()
  const { setAccount } = useStore()
  useEffect(() => {
    setAccount({ door: 'guest', inn: '' })
    nav('/buy', { replace: true })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="min-h-screen px-4 py-5 max-w-[520px] mx-auto flex flex-col">
      <div className="flex items-center justify-between"><Logo /><LangToggle /></div>
      <h1 className="h1 mt-8">{t('guest.title')}</h1>
      <p className="text-[14px] text-ink3 mt-2">{t('guest.sub')}</p>
      <div className="mt-3"><Badge kind="guest" /></div>
      <p className="caption mt-2">{t('guest.note')}</p>
      <PrimaryButton className="mt-5" onClick={() => { setAccount({ door: 'guest' }); nav('/buy') }}>{t('guest.cta')}</PrimaryButton>
    </div>
  )
}
