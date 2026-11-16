import { render } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { AppRoutes } from '../app/App'
import type { Me } from '../api/client'
import { ME_OPEN } from '../app/auth'
import { StoreProvider, type Account, type LocalOrder } from '../app/store'
import { LangProvider, type Lang } from '../i18n'

export const B1 = { commodity: 'cement', grade: '32.5', qty_t: 200, region: 'Namangan', deadline: '2026-11-15', max_price_t: 1_000_000, payment_terms: 'after_delivery' }
export const PHRASE = '200 тонн цемента М400 в Наманган до 15 ноября, не дороже 1 000 000 за тонну'

export function setWidth(w: number) {
  Object.defineProperty(window, 'innerWidth', { configurable: true, writable: true, value: w })
}

function LocationProbe() {
  const l = useLocation()
  return <span hidden data-testid="location">{l.pathname + l.search}</span>
}

export function renderAt(path: string, opts: { lang?: Lang; account?: Partial<Account>; orders?: LocalOrder[]; width?: number; me?: Me | null } = {}) {
  sessionStorage.clear()
  localStorage.clear()
  setWidth(opts.width ?? 1440)
  return render(
    <LangProvider initial={opts.lang ?? 'ru'}>
      <StoreProvider initial={{ account: { door: 'business', inn: '900000005', ...(opts.account ?? {}) }, orders: opts.orders ?? [] }}>
        <MemoryRouter initialEntries={[path]}>
          <AppRoutes me={opts.me === null ? undefined : opts.me ?? ME_OPEN} />
          <LocationProbe />
        </MemoryRouter>
      </StoreProvider>
    </LangProvider>,
  )
}
