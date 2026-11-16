import type { ReactNode } from 'react'
import { Link, Navigate, Route, Routes } from 'react-router-dom'
import { BuyScreen, MarketScreen } from '../screens/MarketScreen'
import { MoneyScreen } from '../screens/MoneyScreen'
import { MoreScreen } from '../screens/MoreScreen'
import { OrdersScreen } from '../screens/OrdersScreen'
import { Plant } from '../screens/Plant'
import { Radar } from '../screens/Radar'
import { GuestScreen, WelcomeScreen } from '../screens/WelcomeScreen'
import { useT } from '../i18n'
import { AuthProvider } from './auth'
import type { Me } from '../api/client'
import { Shell } from './Shell'
import { useStore, useViewport } from './store'

function NotFound() {
  const t = useT()
  return (
    <div className="p-4">
      <h1 className="h1">{t('notfound.title')}</h1>
      <Link to="/market" className="link mt-4 inline-block">{t('notfound.cta')} ↗</Link>
    </div>
  )
}

function Pad({ children }: { children: ReactNode }) {
  const vp = useViewport()
  return <div className={vp === 'desktop' ? 'p-6' : 'pt-4'}>{children}</div>
}

function Home() {
  const { account } = useStore()
  return <Navigate to={account.door ? '/market' : '/welcome'} replace />
}

function Buy() {
  const vp = useViewport()
  return vp === 'desktop' ? <Navigate to="/market" replace /> : <BuyScreen />
}

export function AppRoutes({ me }: { me?: Me } = {}) {
  return (
    <AuthProvider initial={me}>
    <Routes>
      <Route path="welcome" element={<WelcomeScreen />} />
      <Route path="guest" element={<GuestScreen />} />
      <Route index element={<Home />} />
      <Route element={<Shell />}>
        <Route path="market" element={<MarketScreen />} />
        <Route path="buy" element={<Buy />} />
        <Route path="orders" element={<OrdersScreen />} />
        <Route path="orders/:id" element={<OrdersScreen />} />
        <Route path="money" element={<MoneyScreen />} />
        <Route path="plant" element={<Pad><Plant /></Pad>} />
        <Route path="radar" element={<Pad><Radar /></Pad>} />
        <Route path="more" element={<MoreScreen />} />
        {}
        <Route path="intent" element={<Navigate to="/buy" replace />} />
        <Route path="card" element={<Navigate to="/buy" replace />} />
        <Route path="sign" element={<Navigate to="/buy" replace />} />
        <Route path="wait" element={<Navigate to="/orders" replace />} />
        <Route path="result" element={<Navigate to="/orders" replace />} />
        <Route path="why" element={<Navigate to="/orders" replace />} />
        <Route path="passport/:id" element={<Navigate to="/orders" replace />} />
        <Route path="compare" element={<Navigate to="/more" replace />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
    </AuthProvider>
  )
}
