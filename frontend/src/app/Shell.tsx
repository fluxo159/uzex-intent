import { useEffect, useState } from 'react'
import { motion } from 'motion/react'
import { E } from '../lib/motion'
import { NavLink, Outlet, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { Factory, LineChart, ListOrdered, MoreHorizontal, Network, PlusCircle, Wallet, X } from 'lucide-react'
import { onLimit, onMockUsed, type LimitDetail } from '../api/client'
import { limitText } from './auth'
import { AiPanel } from '../components/AiPanel'
import { Badge } from '../components/Badge'
import { LangToggle } from '../components/LangToggle'
import { useLang, useT } from '../i18n'
import { wdTime, windowWords } from '../lib/labels'
import { OrderDetails } from '../features/OrderDetails'
import { Loading } from '../components/States'
import { minutesUntil, useMyOrders, useNow } from './hooks'
import { useStore, useViewport, type Instrument } from './store'

const I = { size: 20, strokeWidth: 1.75 }

function PageFade({ children, full = false }: { children: React.ReactNode; full?: boolean }) {
  const loc = useLocation()
  return (
    <motion.div key={loc.pathname} className={full ? 'h-full' : ''} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.15, ease: E }}>
      {children}
    </motion.div>
  )
}

export function Logo() {
  const t = useT()
  return (
    <NavLink to="/market" className="tap flex items-center gap-2 font-semibold text-[14px] text-ink focus-ring">
      <i aria-hidden className="inline-block w-4 h-4 rounded-[4px] border-2 border-lime" />
      {t('app.name')}
    </NavLink>
  )
}

export function leftText(t: (k: string, v?: Record<string, string | number>) => string, mins: number, short = false): string {
  const h = Math.floor(mins / 60)
  const m = mins % 60
  if (short && h) return t('time.h', { h })
  return h ? t('time.hm', { h, m }) : t('time.m', { m })
}

export function BasketStatus({ compact = false }: { compact?: boolean }) {
  const t = useT()
  const { basket } = useStore()
  const now = useNow(15000)
  if (!basket) return null
  const left = minutesUntil(basket.close_time, now)
  const when = compact ? wdTime(t, basket.open_time ?? basket.close_time) : windowWords(t, basket.open_time ?? basket.close_time, basket.open_time ? basket.close_time : null)
  return (
    <span data-testid="basket-status" className={`${compact ? 'text-[12px]' : 'text-[13px]'} text-ink3 whitespace-nowrap truncate min-w-0`}>
      {basket.status === 'closed' ? t('hdr.closed') : <>{t('hdr.basket', { when })}{left !== null ? <> · <span className="text-ink">{t(compact ? 'hdr.in' : 'hdr.closesIn', { left: leftText(t, left, compact) })}</span></> : null}</>}
    </span>
  )
}

function Clock() {
  const t = useT()
  const now = useNow(1000)
  const p = (n: number) => String(n).padStart(2, '0')
  return (
    <span className="mono text-[13px] text-ink whitespace-nowrap" title={t('hdr.exchange')}>{p(now.getHours())}:{p(now.getMinutes())}:{p(now.getSeconds())}</span>
  )
}

export function InstrumentSwitch({ chips = false }: { chips?: boolean }) {
  const t = useT()
  const { instrument, setInstrument } = useStore()
  const items: [Instrument, string][] = [['32.5', 'instr.cement32'], ['42.5', 'instr.cement42'], ['ai92', 'instr.ai92']]
  return (
    <div role="radiogroup" aria-label={t('instr.label')} className={`flex gap-1 ${chips ? 'overflow-x-auto overflow-y-hidden py-2 -my-2' : ''}`}>
      {items.map(([k, label]) => (
        <button key={k} type="button" role="radio" aria-checked={instrument === k} onClick={() => setInstrument(k)}
          className={`tap focus-ring rounded-full px-3 py-1 text-[12px] whitespace-nowrap ${instrument === k ? 'bg-ink text-bg' : 'bg-s2 text-ink3 hover:text-ink'}`}>
          {t(label)}
        </button>
      ))}
    </div>
  )
}

function AccountChip() {
  const t = useT()
  const { account } = useStore()
  const label = account.door === 'person' ? t('hdr.person') : account.door === 'guest' ? t('hdr.guest') : account.door ? `${t('entry.inn.label')} ${account.inn}` : t('hdr.login')
  const cls = account.door === 'person' ? 'text-lav' : account.door === 'guest' ? 'text-warn' : 'text-ink3'
  return (
    <NavLink to={account.door ? '/more' : '/welcome'} data-testid="account-chip" className={`focus-ring bg-s2 rounded-full px-3 h-8 inline-flex items-center text-[13px] whitespace-nowrap hover:text-ink ${cls}`}>
      {account.door === 'business' ? <span className="mono">{label}</span> : label}
    </NavLink>
  )
}

function LimitNote() {
  const { t, lang, has } = useLang()
  const [d, setD] = useState<LimitDetail | null>(null)
  useEffect(() => onLimit(setD), [])
  useEffect(() => {
    if (!d) return
    const id = setTimeout(() => setD(null), Math.min(60, Math.max(4, d.retry_after ?? 5)) * 1000)
    return () => clearTimeout(id)
  }, [d])
  if (!d) return null
  return (
    <div role="status" data-testid="limit-note" className="fixed left-1/2 -translate-x-1/2 top-3 z-50 max-w-[92vw] bg-s1 border border-line rounded-full px-4 py-2 text-[13px] text-warn shadow-lg flex items-center gap-3">
      <span>{limitText(d, lang, t, has)}</span>
      <button type="button" className="link !text-[12px] text-mute" onClick={() => setD(null)} aria-label="×">×</button>
    </div>
  )
}

function MockFlag() {
  const [mock, setMock] = useState(false)
  useEffect(() => onMockUsed(setMock), [])
  return mock ? <Badge kind="mock" /> : null
}

const NAV: [string, string, JSX.Element][] = [
  ['/market', 'nav.market', <LineChart key="m" {...I} />],
  ['/orders', 'nav.orders', <ListOrdered key="o" {...I} />],
  ['/money', 'nav.money', <Wallet key="w" {...I} />],
  ['/plant', 'nav.plant', <Factory key="f" {...I} />],
  ['/radar', 'nav.radar', <Network key="r" {...I} />],
  ['/more', 'nav.more', <MoreHorizontal key="x" {...I} />],
]
const TABS: [string, string, JSX.Element][] = [
  ['/market', 'tab.market', <LineChart key="m" {...I} />],
  ['/buy', 'tab.buy', <PlusCircle key="b" {...I} />],
  ['/orders', 'tab.mine', <ListOrdered key="o" {...I} />],
  ['/money', 'tab.money', <Wallet key="w" {...I} />],
  ['/more', 'tab.more', <MoreHorizontal key="x" {...I} />],
]

function StatusBar() {
  const t = useT()
  const [open, setOpen] = useState(false)
  return (
    <footer className="relative h-8 shrink-0 border-t border-line px-6 flex items-center justify-between gap-4 text-[12px] text-mute">
      <span data-testid="source-note" className="truncate">{t('status.bar')}</span>
      <span className="flex items-center gap-3 shrink-0">
        <MockFlag />
        <button type="button" className="link !text-[12px] focus-ring" aria-expanded={open} onClick={() => setOpen(!open)}>{t('footer.ai')} ↗</button>
      </span>
      {open ? <div className="absolute right-6 bottom-9 w-[360px] bg-s1 rounded-card p-4 z-30 anim-rise"><AiPanel /></div> : null}
    </footer>
  )
}

function OrderDrawer() {
  const t = useT()
  const nav = useNavigate()
  const loc = useLocation()
  const [sp] = useSearchParams()
  const params = useParams()
  const id = sp.get('order') ?? (loc.pathname.startsWith('/orders/') ? params.id ?? decodeURIComponent(loc.pathname.slice(8)) : null)
  const { orders, loading } = useMyOrders()
  if (!id) return null
  const sel = orders.find((o) => o.mandate_id === id) ?? null
  const close = () => (sp.get('order') ? nav(loc.pathname, { replace: true }) : nav('/orders'))
  return (
    <aside data-testid="order-drawer" className="fixed top-14 right-0 bottom-8 w-[480px] max-w-full bg-bg border-l border-line z-30 overflow-y-auto px-5 py-4 anim-rise">
      {sel ? <OrderDetails order={sel} onClose={close} /> : (
        <div className="flex items-center justify-between gap-2">
          {loading ? <Loading /> : <p className="text-[14px] text-ink3">{t('notfound.title')}</p>}
          <button type="button" onClick={close} aria-label={t('detail.close')} className="focus-ring w-8 h-8 rounded-full bg-s2 inline-flex items-center justify-center text-ink3"><X size={16} strokeWidth={1.75} /></button>
        </div>
      )}
    </aside>
  )
}

export function Shell() {
  const t = useT()
  const vp = useViewport()
  const loc = useLocation()
  useEffect(() => { window.scrollTo?.(0, 0) }, [loc.pathname])

  if (vp === 'desktop') {
    const withInstr = loc.pathname.startsWith('/market') || loc.pathname.startsWith('/plant')
    return (
      <div className="h-screen flex flex-col overflow-hidden" data-layout="desktop">
        <header className="h-14 shrink-0 border-b border-line px-6 flex items-center gap-4">
          <Logo />
          {withInstr ? <div className="ml-6"><InstrumentSwitch /></div> : null}
          <div className="flex-1" />
          <span className="flex items-center gap-2 min-w-0">
            <Clock />
            <span className="text-mute text-[13px]">·</span>
            <BasketStatus />
          </span>
          <LangToggle />
          <AccountChip />
        </header>
        <div className="flex-1 min-h-0 flex">
          <nav aria-label="nav" className="w-16 shrink-0 border-r border-line flex flex-col items-center pt-3 gap-1">
            {NAV.map(([to, label, icon]) => (
              <NavLink key={to} to={to} className={({ isActive }) => `focus-ring w-14 py-2 rounded-chip flex flex-col items-center gap-1 ${isActive ? 'bg-s2 text-lime' : 'text-mute hover:text-ink'}`}>
                {icon}
                <span className="text-[11px] leading-none text-center">{t(label)}</span>
              </NavLink>
            ))}
          </nav>
          <div className="flex-1 min-w-0 flex flex-col">
            <main className="flex-1 min-h-0 overflow-y-auto [scrollbar-gutter:stable]">
              <PageFade full><Outlet /></PageFade>
            </main>
            <StatusBar />
          </div>
        </div>
        <OrderDrawer />
        <LimitNote />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col" data-layout="phone">
      <header className="sticky top-0 z-20 bg-bg border-b border-line px-4 py-2 flex items-center gap-3">
        <Logo />
        <div className="flex-1 min-w-0 truncate"><BasketStatus compact /></div>
        <LangToggle />
      </header>
      <main className="flex-1 px-4 pb-24">
        <PageFade><Outlet /></PageFade>
        <p data-testid="source-note" className="caption mt-6">{t('status.bar')}</p>
        <div className="mt-2"><MockFlag /></div>
      </main>
      <nav aria-label="tabs" className="fixed bottom-0 inset-x-0 z-20 bg-bg border-t border-line grid grid-cols-5 h-16">
        {TABS.map(([to, label, icon]) => (
          <NavLink key={to} to={to} className={({ isActive }) => `focus-ring flex flex-col items-center justify-center gap-1 ${isActive ? 'text-lime' : 'text-mute'}`}>
            {icon}
            <span className="text-[11px] leading-none">{t(label)}</span>
          </NavLink>
        ))}
      </nav>
      <LimitNote />
    </div>
  )
}
