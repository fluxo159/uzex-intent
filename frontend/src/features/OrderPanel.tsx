import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Check, Fingerprint, Loader2, Mic, Square, TriangleAlert, X } from 'lucide-react'
import { api, limitDetail, MOCK_ONLY } from '../api/client'
import type { GateCheck, IntakeFields, Preview, SignResponse } from '../api/types'
import { REGIONS } from '../api/types'
import { useMyOrders } from '../app/hooks'
import { useAuth } from '../app/auth'
import { useStore, useViewport } from '../app/store'
import { Badge } from '../components/Badge'
import { KV } from '../components/Card'
import { Disclosure } from '../components/Disclosure'
import { PillButton } from '../components/PillButton'
import { RangeBar } from '../components/RangeBar'
import { ErrorBox } from '../components/States'
import { Num, Tx } from '../components/Tx'
import { When } from '../components/When'
import { useLang } from '../i18n'
import { fmtNum, fmtPct, shortId } from '../lib/format'
import { CountUp, E, SignRing, Typed } from '../lib/motion'
import { motion, stagger } from 'motion/react'
import { FIELD_STAGGER, PhraseMarks } from '../components/PhraseMarks'

const FIELD_IN = { hidden: { opacity: 0, y: 6 }, shown: { opacity: 1, y: 0, transition: { duration: 0.25, ease: E } } }
import { regionName, windowWords } from '../lib/labels'
import { numToWords, pluralForm } from '../lib/numwords'

type Key = 'grade' | 'qty_t' | 'region' | 'deadline' | 'max_price_t'
const KEYS: Key[] = ['grade', 'qty_t', 'region', 'deadline', 'max_price_t']
const EMPTY: IntakeFields = { commodity: 'cement', grade: '32.5', qty_t: null, region: null, deadline: null, max_price_t: null, payment_terms: 'after_delivery' }

function CheckRow({ c }: { c: GateCheck }) {
  const { t } = useLang()
  const st = c.status ?? (c.passed ? 'ok' : 'blocked')
  const label = t(`card.check.${c.name}`)
  return (
    <div className="py-[3px]" data-testid={`check-${c.name}`}>
      <div className="flex items-center justify-between gap-3 text-[13px]">
        <span className={st === 'blocked' ? 'text-bad' : 'text-ink3'}>{label === `card.check.${c.name}` ? c.name : label}</span>
        {st === 'ok' ? <Check size={16} strokeWidth={1.75} className="text-lime" /> : st === 'warning' ? <TriangleAlert size={16} strokeWidth={1.75} className="text-warn" /> : <X size={16} strokeWidth={1.75} className="text-bad" />}
      </div>
      {st === 'blocked' && (c.how_to_fix || c.reason) ? <div className="caption text-bad">{t('card.check.fix', { text: c.how_to_fix ?? c.reason })}</div> : null}
    </div>
  )
}

function Section({ id, title, children }: { id: string; title?: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-20">
      {title ? <h3 className="text-[13px] text-ink3 mb-2">{title}</h3> : null}
      {children}
    </section>
  )
}

export function OrderPanel({ anchors = false }: { anchors?: boolean }) {
  const { t, lang, has } = useLang()
  const { principal, account, setAccount, prefill, addOrder, bump, refreshBasket } = useStore()
  const { me } = useAuth()
  const [text, setText] = useState('')
  const [fields, setFields] = useState<IntakeFields | null>(null)
  const [fromPhrase, setFromPhrase] = useState<Set<Key>>(new Set())
  const [transcript, setTranscript] = useState('')
  const [parsed, setParsed] = useState<{ text: string; n: number } | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<unknown>(null)
  const [pv, setPv] = useState<Preview | null>(null)
  const [pvBusy, setPvBusy] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const [signing, setSigning] = useState(false)
  const [signed, setSigned] = useState<SignResponse | null>(null)
  const [showHash, setShowHash] = useState(false)
  const [costOpen, setCostOpen] = useState(false)
  const [checkOpen, setCheckOpen] = useState(false)
  const [rec, setRec] = useState<'idle' | 'listening' | 'busy'>('idle')
  const recorder = useRef<MediaRecorder | null>(null)
  const { orders } = useMyOrders()
  const loc = useLocation()
  const vp = useViewport()
  const chunks = useRef<Blob[]>([])

  useEffect(() => {
    if (!prefill) return
    setSigned(null)
    setText(prefill.text ?? '')
    setTranscript(prefill.text ?? '')
    setFields(prefill.fields ? { ...EMPTY, ...prefill.fields } : null)
    setFromPhrase(new Set())
    setConfirmed(false)
  }, [prefill?.key]) // eslint-disable-line react-hooks/exhaustive-deps

  const parse = async () => {
    if (busy) return
    if (!text.trim()) { setErr(t('intent.empty')); return }
    setBusy(true)
    setErr(null)
    try {
      const r = await api.parse(text, lang)
      const f = { ...EMPTY, ...Object.fromEntries(Object.entries(r.fields).filter(([, v]) => v !== null && v !== undefined)) } as IntakeFields
      setFields(f)
      setTranscript(r.transcript_norm || text)
      setFromPhrase(new Set(KEYS.filter((k) => r.fields[k] !== null && r.fields[k] !== undefined && !(r.missing_fields ?? []).includes(k))))
      setParsed((x) => ({ text, n: (x?.n ?? 0) + 1 }))
      setConfirmed(false)
    } catch (e) {
      setErr(e)
    } finally {
      setBusy(false)
    }
  }

  const setField = (k: Key, v: string | number | null) => {
    setFields((f) => ({ ...(f ?? EMPTY), [k]: v === '' ? null : v }))
    setFromPhrase((s) => { const n = new Set(s); n.delete(k); return n })
    if (k === 'qty_t' || k === 'max_price_t') setConfirmed(false)
  }

  const fkey = JSON.stringify(fields)
  useEffect(() => {
    if (!fields || !fields.qty_t || !fields.max_price_t || !fields.region) { setPv(null); return }
    let alive = true
    setPvBusy(true)
    const id = setTimeout(() => {
      api.preview(fields, principal, lang, transcript || text).then(
        (r) => {
          if (!alive) return
          setPv(r)
          setPvBusy(false)
          const funds = r.gate.checks.find((c) => c.name === 'funds')?.funds_available
          if (funds != null && funds !== account.funds) setAccount({ funds })
        },
        (e) => { if (alive) { setErr(e); setPvBusy(false) } },
      )
    }, 350)
    return () => { alive = false; clearTimeout(id) }
  }, [fkey, principal.kind, principal.inn, lang]) // eslint-disable-line react-hooks/exhaustive-deps

  const blocked = pv?.gate.status === 'blocked'
  const canSign = !!pv?.mandate_draft && !blocked && confirmed && !pvBusy

  const signLock = useRef(false)
  const sign = async () => {
    if (!pv?.mandate_draft || !fields || signLock.current) return
    signLock.current = true
    setSigning(true)
    setErr(null)
    try {
      const [r] = await Promise.all([api.sign(pv.mandate_draft), new Promise((res) => setTimeout(res, 1200))])
      setSigned(r)
      addOrder({
        mandate_id: r.mandate_id, fields, phrase: text, signed_at: r.signed_at, basket_id: r.basket_id || pv.next_basket.basket_id,
        window: pv.next_basket.window ?? null, window_start: pv.next_basket.open_time ?? null, hash: r.hash, receipt: r.receipt,
      })
      bump()
      refreshBasket()
    } catch (e) {
      setErr(e)
    } finally {
      signLock.current = false
      setSigning(false)
    }
  }

  const reset = () => {
    setSigned(null); setText(''); setFields(null); setPv(null); setConfirmed(false); setFromPhrase(new Set()); setErr(null); setShowHash(false)
  }

  const startVoice = async () => {
    const simulate = async () => {
      setRec('listening')
      await new Promise((r) => setTimeout(r, 1500))
      setRec('busy')
      const r = await api.stt(new Blob(), lang)
      setText(r.transcript)
      setRec('idle')
    }
    if (MOCK_ONLY || !navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') { await simulate(); return }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream)
      chunks.current = []
      mr.ondataavailable = (e) => { if (e.data.size) chunks.current.push(e.data) }
      mr.onstop = async () => {
        stream.getTracks().forEach((tr) => tr.stop())
        setRec('busy')
        try { setText((await api.stt(new Blob(chunks.current, { type: mr.mimeType || 'audio/webm' }), lang)).transcript) } catch (e) { setErr(limitDetail(e) ? e : t('intent.voiceFail')) } finally { setRec('idle') }
      }
      recorder.current = mr
      mr.start()
      setRec('listening')
    } catch { await simulate() }
  }

  const dot = (k: Key, short = false) => {
    const v = fields?.[k]
    if (v === null || v === undefined || v === '') return <span className="text-[11px] text-ink3 whitespace-nowrap" title={t('f.clarify')}>○{short ? null : <> {t('f.clarify')}</>}</span>
    if (fromPhrase.has(k)) return <span className="text-[11px] text-lime whitespace-nowrap" title={t('f.fromPhrase')}>●{short ? null : <> {t('f.fromPhrase')}</>}</span>
    return null
  }
  const input = 'w-full h-11 md:h-9 bg-s1 rounded-chip px-3 text-[14px] text-ink2 outline-none focus:ring-2 focus:ring-lime placeholder:text-mute'
  const regions = useMemo(() => REGIONS.map((r) => [r, regionName(t, r)] as const), [t])

  if (signed) {
    const now = orders.find((o) => o.mandate_id === signed.mandate_id)
    const done = !!now && (now.status === 'filled' || now.status === 'partial') && (now.delivered_price_t ?? now.clearing_price_t) != null
    const toDetails = vp === 'desktop' ? `${loc.pathname}?order=${encodeURIComponent(signed.mandate_id)}` : `/orders/${encodeURIComponent(signed.mandate_id)}`
    const delivery = now?.delivered_price_t != null && now?.clearing_price_t != null ? now.delivered_price_t - now.clearing_price_t : null
    return (
      <div data-testid="order-signed" className="bg-s2 rounded-card px-5 py-4 anim-rise">
        <div className="flex items-center gap-3">
          <span className="relative shrink-0 w-10 h-10 rounded-full bg-s3 inline-flex items-center justify-center text-lime"><Fingerprint size={22} strokeWidth={1.5} /><SignRing className="absolute -inset-[10px] w-[60px] h-[60px] pointer-events-none" /></span>
          <div className="text-[15px]">
            {done
              ? <>{t('order.filledHead')} <span className="mono whitespace-nowrap">№ {shortId(signed.mandate_id)}</span></>
              : now?.status === 'unfilled'
                ? <>{t('order.unfilledHead')} <span className="mono whitespace-nowrap">№ {shortId(signed.mandate_id)}</span></>
                : <Tx k="order.signed" vars={{ id: <Typed className="mono" text={shortId(signed.mandate_id)} delay={1200} />, when: <When start={pv?.next_basket.open_time ?? pv?.next_basket.close_time} end={pv?.next_basket.open_time ? pv?.next_basket.close_time : null} /> }} />}
          </div>
        </div>
        {done ? (
          <div data-testid="order-result" className="mt-3">
            <div className="num-xl text-[38px] text-lime"><CountUp value={now?.delivered_price_t ?? now?.clearing_price_t} from0 duration={600} delay={300} /></div>
            <div className="text-[13px] text-ink3">{(now?.sellers?.length ?? 0) > 1 ? t('result.avg') : t('result.price')}</div>
            {delivery !== null ? <p className="text-[13px] text-ink3 mt-2"><Tx k="result.split" vars={{ base: fmtNum(now?.clearing_price_t), delivery: fmtNum(delivery) }} /></p> : null}
          </div>
        ) : null}
        {done || now?.status === 'unfilled' ? <Link to={toDetails} className="link focus-ring tap inline-block mt-2">{t('detail.why')} ↗</Link> : (
          <>
            <button type="button" className="link tap mt-3" onClick={() => setShowHash(!showHash)}>{showHash ? t('sign.hash.hide') : t('sign.hash.show')}</button>
            {showHash ? <div className="mt-2 bg-s1 rounded-chip p-3 mono text-[11px] break-all text-ink2">{signed.hash}<div className="caption mt-1 font-sans">{t('sign.receipt')}: <span className="mono">{signed.receipt}</span></div></div> : null}
          </>
        )}
        <div className="flex flex-wrap items-center gap-3 mt-4">
          <PillButton block={false} arrow onClick={reset}>{t('order.new')}</PillButton>
          <Link to="/orders" className="link tap">{t('order.toMine')} ↗</Link>
        </div>
        {done ? null : <div className="mt-3"><Badge kind="demoSign" /></div>}
      </div>
    )
  }

  return (
    <div data-testid="order-panel" className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-[17px] leading-[24px] font-semibold">{t('order.title')}</h2>
        {account.door === 'guest' ? <Badge kind="guest" /> : null}
      </div>
      {anchors && fields ? (
        <nav className="flex gap-2 overflow-x-auto text-[12px] -mx-4 px-4 py-2">
          {(pv ? ['phrase', 'fields', 'cost', 'check', 'sign'] : ['phrase', 'fields', 'sign']).map((a) => <a key={a} href={`#order-${a}`} className="tap rounded-full bg-s2 text-ink3 px-3 py-1 whitespace-nowrap">{t(`order.anchor.${a}`)}</a>)}
          <span aria-hidden className="shrink-0 w-2" />
        </nav>
      ) : null}

      <Section id="order-phrase">
        <div className="bg-s2 rounded-card px-5 py-4">
          <div className="relative">
            {parsed && fields && parsed.text === text ? <PhraseMarks key={parsed.n} text={text} fields={fields} keys={fromPhrase} regionLabel={regionName(t, fields.region)} className="text-[15px] leading-[1.45]" /> : null}
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void parse() } }}
              placeholder={t('intent.sub')}
              rows={3}
              aria-label={t('intent.sub')}
              className="relative block w-full resize-none bg-transparent text-[15px] leading-[1.45] text-ink2 outline-none placeholder:text-mute caret-lime"
            />
          </div>
          <div className="flex items-center gap-2 mt-2">
            <PillButton block={false} variant={fields ? 'ghost' : 'lime'} className="!py-2 !text-[13px] tap" onClick={parse} disabled={busy}>{busy ? t('common.loading') : t('order.parse')}</PillButton>
            {me.voice ? (
            <button type="button" data-testid="mic" onClick={rec === 'listening' ? () => recorder.current?.stop() : startVoice} disabled={rec === 'busy'} aria-label={rec === 'listening' ? t('intent.voiceStop') : t('intent.voiceStart')} title={t('intent.voiceStart')}
              className={`tap focus-ring w-9 h-9 rounded-full bg-s3 inline-flex items-center justify-center text-lime ${rec === 'listening' ? 'pulse' : ''}`}>
              {rec === 'listening' ? <Square size={14} strokeWidth={1.75} /> : <Mic size={18} strokeWidth={1.75} />}
            </button>
            ) : null}
            {rec === 'listening' ? <span className="wave inline-flex items-center gap-2 text-[12px] text-lime"><span><i /><i /><i /><i /><i /></span>{t('intent.listening')}</span> : null}
          </div>
        </div>
        {fields ? null : <div className="flex gap-2 flex-wrap mt-2">
          {[1, 2, 3].map((i) => (
            <button key={i} type="button" onClick={() => setText(t(`intent.example.${i}`))} className="tap focus-ring text-[12px] px-3 py-1 rounded-chip bg-s2 text-ink3 hover:text-ink text-left">{t(`intent.example.${i}`)}</button>
          ))}
        </div>}
      </Section>

      {fields ? (
        <Section id="order-fields">
          <motion.div key={parsed?.n ?? 0} className="bg-s2 rounded-card px-5 py-4 grid grid-cols-2 gap-3 items-end" data-testid="order-fields" initial="hidden" animate="shown" variants={{ hidden: {}, shown: { transition: { delayChildren: stagger(FIELD_STAGGER) } } }}>
            <motion.label variants={FIELD_IN} className="col-span-2">
              <span className="flex justify-between caption"><span>{t('f.commodity')}</span>{dot('grade')}</span>
              <select className={input} value={fields.grade ?? '32.5'} onChange={(e) => setField('grade', e.target.value)}>
                <option value="32.5">{t('instr.cement32')} ({t('instr.sub32')})</option>
                <option value="42.5">{t('instr.cement42')} ({t('instr.sub42')})</option>
              </select>
            </motion.label>
            <motion.label variants={FIELD_IN}>
              <span className="flex justify-between caption gap-1"><span>{t('f.qty')}</span>{dot('qty_t', true)}</span>
              <input data-testid="f-qty" inputMode="numeric" className={`${input} mono`} value={fields.qty_t ?? ''} onChange={(e) => setField('qty_t', e.target.value.replace(/\D/g, '') ? +e.target.value.replace(/\D/g, '') : null)} />
            </motion.label>
            <motion.label variants={FIELD_IN}>
              <span className="flex justify-between caption gap-1"><span className="truncate">{t('f.deadline')}</span>{dot('deadline', true)}</span>
              <input type="date" className={`${input} mono`} value={fields.deadline ?? ''} onChange={(e) => setField('deadline', e.target.value)} />
            </motion.label>
            <motion.label variants={FIELD_IN} className="col-span-2">
              <span className="flex justify-between caption"><span>{t('f.region')}</span>{dot('region')}</span>
              <select className={input} value={fields.region ?? ''} onChange={(e) => setField('region', e.target.value)}>
                <option value="">{t('f.choose')}</option>
                {regions.map(([code, name]) => <option key={code} value={code}>{name}</option>)}
              </select>
            </motion.label>
            <motion.label variants={FIELD_IN} className="col-span-2">
              <span className="flex justify-between caption"><span>{t('f.max')}</span>{dot('max_price_t')}</span>
              <input data-testid="f-max" inputMode="numeric" className={`${input} mono !text-[17px]`} value={fields.max_price_t ? fmtNum(fields.max_price_t) : ''} onChange={(e) => setField('max_price_t', e.target.value.replace(/\D/g, '') ? +e.target.value.replace(/\D/g, '') : null)} />
            </motion.label>
            <motion.div variants={FIELD_IN} className="col-span-2"><RangeBar from={pv?.usual?.p10} to={pv?.usual?.p90} cap={fields.max_price_t} /></motion.div>
          </motion.div>
        </Section>
      ) : null}

      {pv ? (
        <>
          <Section id="order-cost" title={t('card.cost.title')}>
            <div className="bg-s2 rounded-card px-5 py-2">
              {costOpen ? <>
              <KV k={t('card.cost.max')} v={<Num>{fmtNum(pv.gross_max)}</Num>} />
              <KV k={t('card.cost.fee', { rate: fmtPct(pv.fee_rate) })} v={<Num>{fmtNum(pv.exchange_fee)}</Num>} />
              <KV k={t('card.cost.deposit')} v={<Num className="whitespace-nowrap">≤&nbsp;{fmtNum(pv.deposit_worst)}</Num>} />
              <p className="caption -mt-1">{t('card.cost.depositHint')}</p>
              <KV k={t('card.cost.delivery')} v={pv.delivery_min_t !== null && pv.delivery_max_t !== null ? <Tx k="card.cost.deliveryRange" vars={{ from: fmtNum(pv.delivery_min_t), to: fmtNum(pv.delivery_max_t) }} /> : '—'} />
              </> : null}
              <KV k={t('card.cost.total')} v={<Num className="text-ink"><CountUp value={pv.total_worst} /></Num>} />
              <button type="button" aria-expanded={costOpen} onClick={() => setCostOpen(!costOpen)} className="tap link focus-ring pb-1">{t('card.cost.more')} <span aria-hidden className="text-mute">{costOpen ? '−' : '+'}</span></button>
            </div>
          </Section>
          <Section id="order-check" title={t('card.check.title')}>
            {(() => {
              const allOk = pv.gate.checks.every((c) => (c.status ?? (c.passed ? 'ok' : 'blocked')) === 'ok')
              const open = !allOk || checkOpen
              return (
                <div className="bg-s2 rounded-card px-5 py-3">
                  {allOk ? (
                    <div className="flex items-center justify-between gap-3 text-[13px]" data-testid="check-summary">
                      <span className="text-ink2 inline-flex items-center gap-2"><Check size={16} strokeWidth={1.75} className="text-lime" />{t('card.check.passed')}</span>
                      <button type="button" aria-expanded={checkOpen} onClick={() => setCheckOpen(!checkOpen)} className="tap link focus-ring">{t('card.cost.more')} <span aria-hidden className="text-mute">{checkOpen ? '−' : '+'}</span></button>
                    </div>
                  ) : null}
                  {open ? <div className={allOk ? 'mt-1' : ''}>{pv.gate.checks.map((c) => <CheckRow key={c.name} c={c} />)}</div> : null}
                </div>
              )
            })()}
            {account.door === 'person' ? <p className="text-[12px] text-lav bg-lav-bg rounded-chip px-3 py-2 mt-2">{t('card.warning.person')}</p> : null}
            {pv.warnings.filter((w) => has(`warn.${w.code}`)).map((w) => <p key={w.code} className="text-[12px] text-warn bg-warn-bg rounded-chip px-3 py-2 mt-2">{t(`warn.${w.code}`)}</p>)}
            {pv.errors.filter((e) => e.code !== 'gate_blocked').map((e, i) => <p key={i} role="alert" className="text-[12px] text-bad mt-2">{has(`err.${e.code}`) ? t(`err.${e.code}`) : e.code}</p>)}
            <p className="text-[13px] text-ink3 mt-2">{t('order.nextBasket', { when: windowWords(t, pv.next_basket.open_time ?? pv.next_basket.close_time, pv.next_basket.open_time ? pv.next_basket.close_time : null) })}</p>
          </Section>
        </>
      ) : null}

      {fields ? (
        <Section id="order-sign">
          {fields.qty_t && fields.max_price_t ? (
            <div data-testid="number-confirm" className={`rounded-chip px-3 py-2 flex items-center justify-between gap-2 ${confirmed ? 'bg-s1' : 'bg-s2'}`}>
              <span className="text-[13px] text-ink2">
                {confirmed ? <span className="text-lime">✓ {t('order.confirmed')}</span> : t('order.confirmLine', { qty: numToWords(fields.qty_t, lang), unit: t(`unit.t.${pluralForm(fields.qty_t)}`), price: numToWords(fields.max_price_t, lang) })}
              </span>
              {confirmed ? null : <PillButton block={false} className="!py-1 !px-4 !text-[13px] tap" onClick={() => setConfirmed(true)}>{t('confirm.yes')}</PillButton>}
            </div>
          ) : null}
          {blocked ? <p className="text-bad text-[12px] mt-2" role="alert">{t('card.check.blocked')}</p> : null}
          <PillButton className={`mt-3 inline-flex items-center justify-center gap-2 ${signing ? 'disabled:!opacity-100 !cursor-progress' : ''}`} disabled={!canSign || signing} aria-busy={signing} onClick={sign} data-testid="sign-btn">{signing ? <Loader2 aria-hidden size={16} strokeWidth={2} className="animate-spin motion-reduce:animate-none shrink-0" /> : null}<span>{t('card.sign')} ↗</span></PillButton>
          <div className="flex items-center justify-center flex-wrap gap-2 mt-2">
            <Badge kind="demoSign" testId="badge-demo-sign" />
            {account.door === 'person' ? <Badge kind="future" /> : null}
            <span className="caption">{t('card.signNote')}</span>
          </div>
          <Disclosure center label={t('card.what.title')}>{[1, 2, 3, 4].map((i) => <p key={i} className="mb-1">{t(`card.what.${i}`)}</p>)}</Disclosure>
        </Section>
      ) : null}

      {err ? (typeof err === 'string' ? <p className="text-bad text-[12px]" role="alert">{err}</p> : <ErrorBox detail={err} />) : null}
    </div>
  )
}
