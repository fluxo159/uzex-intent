import { useStore, useViewport } from '../app/store'
import { InstrumentSwitch } from '../app/Shell'
import { LiveTape } from '../components/LiveTape'
import { ChartPanel, InstrumentList, LadderPanel, NoBasket, RecentOrders } from '../features/MarketParts'
import { OrderPanel } from '../features/OrderPanel'
import { useT } from '../i18n'

export function MarketScreen() {
  const t = useT()
  const vp = useViewport()
  const { tick, instrument } = useStore()
  const hasLadder = instrument === '32.5'
  if (vp === 'desktop') {
    return (
      <div data-testid="market-desktop" className="h-full grid grid-cols-12 gap-4 p-6 overflow-hidden">
        <section className="col-span-3 min-h-0 flex flex-col gap-4">
          <InstrumentList />
          <div className="bg-s2 rounded-card px-5 py-4 flex-1 min-h-0 flex flex-col">
            <h2 className="text-[13px] text-ink3 mb-2">{t('mkt.tape')}</h2>
            <div className="flex-1 min-h-0 overflow-y-auto"><LiveTape scroll rows={50} refreshKey={tick} /></div>
          </div>
        </section>
        <section className="col-span-6 min-h-0 flex flex-col gap-4">
          <div className={`bg-s2 rounded-card px-5 py-4 min-h-0 flex flex-col ${hasLadder ? 'basis-[55%] shrink-0' : 'flex-1'}`}><ChartPanel height={0} /></div>
          {hasLadder
            ? <div className="bg-s2 rounded-card px-5 py-4 flex-1 min-h-0 flex flex-col"><LadderPanel /></div>
            : <NoBasket />}
        </section>
        <section className="col-span-3 min-h-0 overflow-y-auto flex flex-col gap-6">
          <OrderPanel />
          <RecentOrders />
        </section>
      </div>
    )
  }
  return (
    <div data-testid="market-phone" className="flex flex-col gap-4 pt-4">
      <InstrumentSwitch chips />
      <InstrumentList compact />
      <div className="bg-s2 rounded-card p-4"><ChartPanel height={220} /></div>
      {hasLadder ? <div className="bg-s2 rounded-card p-4"><LadderPanel maxRows={6} /></div> : <NoBasket />}
      <div className="bg-s2 rounded-card p-4">
        <h2 className="text-[13px] text-ink3 mb-2">{t('mkt.tape')}</h2>
        <LiveTape rows={6} refreshKey={tick} />
      </div>
    </div>
  )
}

export function BuyScreen() {
  return (
    <div className="pt-4 max-w-[560px]">
      <OrderPanel anchors />
    </div>
  )
}
