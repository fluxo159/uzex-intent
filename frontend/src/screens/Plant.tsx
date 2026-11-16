import { useState } from 'react'
import { api } from '../api/client'
import { Screen, Title } from '../app/Screen'
import { Badge } from '../components/Badge'
import { Card } from '../components/Card'
import { DemandMap } from '../components/DemandMap'
import { ErrorBox, Loading } from '../components/States'
import { Tx } from '../components/Tx'
import { useLang } from '../i18n'
import { fmtNum } from '../lib/format'
import { regionName } from '../lib/labels'
import { useAsync } from '../lib/useAsync'

const PLANTS = ['Toshkent Conch Cement', 'Qarshi Conch Cement', 'Shangfeng-Bridge of Friendship', 'Jizzakh Cement Plant', 'Huaxin Cement Jizzakh']

export function Plant() {
  const { t } = useLang()
  const [seller, setSeller] = useState(PLANTS[0])
  const d = useAsync(() => api.plant(seller), [seller])
  const list = useAsync(() => api.plants(), [])
  const sellers = Array.from(new Set([...PLANTS, ...(list.data ?? []), ...(d.data?.sellers ?? [])]))
  const last = d.data?.last_run
  const shown = d.data && d.data.regions.length === 0 && last?.lot_groups.length
    ? {
      ...d.data,
      regions: last.lot_groups.flatMap((g) => Object.entries(g.regions).map(([region, qty]) => ({ region, qty_t: qty, n_mandates: -1, deadline: null, lots: Math.floor(qty / g.min_lot_t), rest_t: qty % g.min_lot_t }))),
    }
    : d.data
  return (
    <Screen wide>
      <div>
        <Title sub={d.data?.warehouse_region ? t('plant.warehouse', { region: regionName(t, d.data.warehouse_region) }) : undefined}>
          {seller} · {t('plant.title')}
        </Title>
      </div>
      <label className="block lg:w-[320px]">
        <span className="caption">{t('plant.choose')}</span>
        <select value={seller} onChange={(e) => setSeller(e.target.value)} className="mt-1 w-full lg:w-[320px] h-11 bg-s2 rounded-chip px-3 text-[15px] text-ink outline-none focus:ring-2 focus:ring-lime">
          {sellers.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
      </label>
      {d.loading && !d.data ? <Loading /> : null}
      {d.error ? <ErrorBox detail={d.error} onRetry={d.reload} /> : null}
      {d.data ? (
        <>
          <p className="caption">{t('plant.compress')}</p>
          {shown ? <DemandMap data={shown} /> : null}
          {last && d.data.regions.length === 0 ? <p className="caption"><Tx k="plant.sold" vars={{ qty: fmtNum(last.sold_t), price: fmtNum(last.clearing_price_t) }} /></p> : null}
          <Card>
            <p className="text-[15px] leading-[1.5]">
              {d.data.buy_at_price_t > 0
                ? <Tx k="plant.yourPrice" vars={{ price: fmtNum(d.data.price_t), qty: fmtNum(d.data.buy_at_price_t), total: fmtNum(d.data.basket_total_t) }} />
                : <Tx k="plant.noneAtPrice" vars={{ total: fmtNum(d.data.basket_total_t) }} />}
            </p>
            <p className="caption mt-2">{t('plant.private')}</p>
          </Card>
          <div><Badge kind="demoVolume" /></div>
        </>
      ) : null}
    </Screen>
  )
}
