import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, resetLocalMock, setAdminToken } from '../api/client'
import { limitText, useAuth } from '../app/auth'
import { useStore, useViewport } from '../app/store'
import { AiPanel } from '../components/AiPanel'
import { Badge } from '../components/Badge'
import { Compare } from '../components/Compare'
import { LangToggle } from '../components/LangToggle'
import { PillButton } from '../components/PillButton'
import { ErrorBox } from '../components/States'
import { useLang, useT } from '../i18n'

const ROWS = ['door', 'call', 'prepay', 'fields', 'mult', 'race', 'prices', 'refuse', 'chat']

function AccessBlock() {
  const { t, lang, has } = useLang()
  const { me, applyCode, logout, refresh } = useAuth()
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!code.trim() || busy) return
    setBusy(true)
    setErr(null)
    const bad = await applyCode(code)
    setBusy(false)
    if (bad) setErr(limitText(bad, lang, t, has))
    else setCode('')
  }
  const left = me.limits_left ?? {}
  return (
    <section className="bg-s2 rounded-card px-5 py-4" data-testid="access-block">
      <h2 className="text-[13px] text-ink3 mb-2">{t('acc.title')}</h2>
      {me.level === 'jury' ? (
        <div data-testid="access-jury">
          <p className="text-[14px] text-lime">{t('acc.jury')}</p>
          {left.llm_per_hour !== undefined ? <p className="caption mt-1">{t('acc.left', { llm: left.llm_per_hour, stt: left.stt_per_hour ?? '—' })}</p> : null}
          <button type="button" className="link text-[13px] mt-2" onClick={() => void logout()} data-testid="access-logout">{t('acc.logout')}</button>
        </div>
      ) : me.level === 'admin' ? (
        <div data-testid="access-admin">
          <p className="text-[14px] text-lime">{t('acc.admin')}</p>
          <button type="button" className="link text-[13px] mt-2" onClick={() => { setAdminToken(null); void refresh() }}>{t('acc.adminOff')}</button>
        </div>
      ) : (
        <form onSubmit={submit}>
          <div className="flex gap-2">
            <input value={code} onChange={(e) => setCode(e.target.value)} placeholder={t('acc.placeholder')} aria-label={t('acc.title')}
              autoComplete="off" autoCapitalize="characters" spellCheck={false} maxLength={32} data-testid="access-input"
              className="mono flex-1 min-w-0 bg-s3 rounded-full px-4 py-2 text-[14px] text-ink outline-none focus-ring uppercase placeholder:normal-case placeholder:text-mute" />
            <PillButton type="submit" block={false} variant="lime" className="!py-2 !text-[13px] tap" disabled={busy || !code.trim()} data-testid="access-apply">{busy ? t('common.loading') : t('acc.apply')}</PillButton>
          </div>
          {err ? <p role="alert" className="text-[12px] text-bad mt-2">{err}</p> : null}
          <p className="caption mt-2" data-testid="access-guest-note">{t('acc.guestNote')}</p>
        </form>
      )}
    </section>
  )
}

export function MoreScreen() {
  const t = useT()
  const nav = useNavigate()
  const vp = useViewport()
  const { account, resetAll } = useStore()
  const { me } = useAuth()
  const admin = me.level === 'admin'
  const [confirm, setConfirm] = useState(false)
  const [done, setDone] = useState(false)
  const [resetErr, setResetErr] = useState<unknown>(null)
  const doReset = async () => {
    setResetErr(null)
    try { await api.reset() } catch (e) { setResetErr(e); setConfirm(false); return }
    resetLocalMock()
    resetAll()
    setConfirm(false)
    setDone(true)
  }
  const accLabel = account.door === 'person' ? t('hdr.person') : account.door === 'guest' ? t('hdr.guest') : account.door ? `${t('entry.inn.label')} ${account.inn}` : '—'
  return (
    <div className={vp === 'desktop' ? 'p-6' : 'pt-4'}>
      <h1 className="h-page mb-4">{t('more.title')}</h1>
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="bg-s2 rounded-card px-5 py-4">
          <h2 className="text-[13px] text-ink3 mb-2">{t('more.account')}</h2>
          <div className="flex items-center justify-between gap-2">
            <span className={account.door === 'business' ? 'mono' : ''}>{accLabel}</span>
            {account.door === 'person' ? <Badge kind="future" /> : account.door === 'guest' ? <Badge kind="guest" /> : null}
          </div>
          <PillButton variant="ghost" block={false} className="mt-3 !py-2 !text-[13px]" onClick={() => nav('/welcome')}>{t('more.change')}</PillButton>
          <div className="flex items-center justify-between mt-4"><span className="caption">{t('more.lang')}</span><LangToggle /></div>
        </section>
        <AccessBlock />
        {vp !== 'desktop' ? (
          <section className="bg-s2 rounded-card px-5 py-2 flex flex-col">
            <Link className="link text-[15px] text-ink h-11 flex items-center" to="/plant">{t('nav.plant')} ↗</Link>
            <Link className="link text-[15px] text-ink h-11 flex items-center" to="/radar">{t('nav.radar')} ↗</Link>
          </section>
        ) : null}
        <section className="bg-s2 rounded-card px-5 py-4">
          <h2 className="text-[13px] text-ink3 mb-2">{t('more.about')}</h2>
          <p className="text-[13px] text-ink3 leading-[1.5]">{t('more.aboutText')}</p>
        </section>
        <section className="bg-s2 rounded-card px-5 py-4 lg:col-span-2">
          <h2 className="text-[13px] text-ink3 mb-2">{t('cmp.title')} · {t('cmp.sub')}</h2>
          <Compare big rows={ROWS.map((r) => ({ key: r, today: t(`cmp.row.${r}.today`), ours: t(`cmp.row.${r}.ours`) }))} />
        </section>
        <section className={`bg-s2 rounded-card px-5 py-4 ${admin ? '' : 'lg:col-span-2'}`}>
          <h2 className="text-[13px] text-ink3">{t('ai.title')}</h2>
          <AiPanel />
        </section>
        {admin ? (
          <section className="bg-s2 rounded-card px-5 py-4">
            <h2 className="text-[13px] text-ink3 mb-2">{t('more.presenter')}</h2>
            {confirm ? (
              <div className="flex flex-wrap items-center gap-2 text-[13px]">
                <span className="text-warn">{t('reset.confirm')}</span>
                <button type="button" onClick={doReset} data-testid="reset-yes" className="link text-bad">{t('reset.yes')}</button>
                <button type="button" onClick={() => setConfirm(false)} className="link">{t('reset.no')}</button>
              </div>
            ) : <button type="button" onClick={() => setConfirm(true)} data-testid="reset-demo" className="link text-ink">{t('footer.reset')}</button>}
            {done ? <p role="status" className="text-[12px] text-lime mt-2">{t('footer.resetDone')}</p> : null}
            {resetErr ? <ErrorBox detail={resetErr} /> : null}
          </section>
        ) : null}
      </div>
    </div>
  )
}
