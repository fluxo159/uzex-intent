import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { MotionConfig } from 'motion/react'
import './app/theme.css'
import { AppRoutes } from './app/App'
import { StoreProvider } from './app/store'
import { LangProvider } from './i18n'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MotionConfig reducedMotion="user" transition={{ duration: 0.3, ease: [0.2, 0.8, 0.2, 1] }}>
    <LangProvider>
      <StoreProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </StoreProvider>
    </LangProvider>
    </MotionConfig>
  </StrictMode>,
)
