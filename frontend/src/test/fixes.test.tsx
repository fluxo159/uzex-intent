import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { normLadder } from '../api/normalize'
import type { ClearingResult, Ladder as LadderT, MyOrder } from '../api/types'
import { Ladder } from '../components/Ladder'
import { LangProvider } from '../i18n'
import { renderAt } from './render'

afterEach(() => { vi.restoreAllMocks() })

const LAD: LadderT = {
  bands_demand: [{ price_from: 980000, price_to: 990000, qty_t: 200 }, { price_from: 540000, price_to: 550000, qty_t: 60 }, { price_from: 450000, price_to: 460000, qty_t: 30 }],
  bands_supply: [{ price_from: 470000, price_to: 480000, qty_t: 150 }, { price_from: 490000, price_to: 500000, qty_t: 300 }],
  totals: { bids: 7, bid_t: 360, asks: 5, ask_t: 1000 }, closed: false, clearing_price_t: null,
}

describe('лестница спроса и предложения', () => {
  it('только полосы-агрегаты, без отдельных поручений', () => {
    render(<LangProvider initial="ru"><Ladder data={LAD} /></LangProvider>)
    expect(screen.getAllByTestId('band-demand')).toHaveLength(3)
    expect(screen.getAllByTestId('band-supply')).toHaveLength(2)
    const text = screen.getByTestId('ladder').textContent ?? ''
    expect(text).not.toMatch(/M-|mandate|№|ИП |ООО/)
    expect(screen.getByTestId('ladder')).toHaveTextContent('7 покупателей · 360 т | 5 заводов · 1 000 т')
  })
  it('до закрытия цена пересечения скрыта — даже если её прислали', () => {
    const lad = normLadder({ ...LAD, closed: false, clearing_price_t: 490000 })
    expect(lad.clearing_price_t).toBeNull()
    render(<LangProvider initial="ru"><Ladder data={lad} /></LangProvider>)
    expect(screen.queryByTestId('ladder-price')).not.toBeInTheDocument()
    expect(screen.getByTestId('ladder-unknown')).toHaveTextContent('Пересечение станет известно при закрытии')
    expect(screen.getByTestId('ladder').textContent).not.toContain('одна цена для всех')
  })
  it('после закрытия — одна цена для всех', () => {
    render(<LangProvider initial="ru"><Ladder data={normLadder({ ...LAD, closed: true, clearing_price_t: 490000 })} /></LangProvider>)
    expect(screen.getByTestId('ladder-price')).toHaveTextContent('одна цена для всех: 490 000')
  })
})

describe('мои поручения', () => {
  it('список показывает статусы', async () => {
    const list: MyOrder[] = [
      { mandate_id: 'AAAA-01', status: 'in_basket', qty_t: 200, region: 'Namangan', grade: '32.5', max_price_t: 1_000_000 },
      { mandate_id: 'BBBB-02', status: 'filled', qty_t: 20, region: 'Qashqadaryo', grade: '32.5', max_price_t: 650_000, run_id: 'R-1' },
      { mandate_id: 'CCCC-03', status: 'unfilled', qty_t: 30, region: 'Tashkent_city', grade: '32.5', max_price_t: 470_000, run_id: 'R-1' },
    ]
    vi.spyOn(api, 'mine').mockResolvedValue(list)
    renderAt('/orders')
    expect(await screen.findByTestId('status-in_basket')).toHaveTextContent('в корзине')
    expect(screen.getByTestId('status-filled')).toHaveTextContent('исполнено')
    expect(screen.getByTestId('status-unfilled')).toHaveTextContent('ждёт следующую')
    expect(screen.getAllByTestId('order-row')).toHaveLength(3)
  })
})

describe('редиректы старых маршрутов', () => {
  it.each(['/intent', '/card', '/sign'])('%s → рынок с панелью поручения (комп)', async (path) => {
    renderAt(path)
    expect(await screen.findByTestId('market-desktop')).toBeInTheDocument()
    expect(screen.getByTestId('order-panel')).toBeInTheDocument()
  })
  it.each(['/wait', '/result', '/why'])('%s → поручения', async (path) => {
    renderAt(path)
    expect(await screen.findByRole('heading', { name: 'Поручения' })).toBeInTheDocument()
  })
  it('/money — деньги со сводкой', async () => {
    renderAt('/money')
    expect(await screen.findByTestId('money-summary')).toBeInTheDocument()
  })
  it('/intent на телефоне → вкладка «Купить»', async () => {
    renderAt('/intent', { width: 375 })
    expect(await screen.findByTestId('order-panel')).toBeInTheDocument()
    expect(screen.queryByTestId('market-phone')).not.toBeInTheDocument()
  })
})

describe('гостевой вход и сброс', () => {
  it('/guest ведёт во вкладку «Купить», вход — демо-участник', async () => {
    renderAt('/guest', { width: 375, account: { door: null } })
    expect(await screen.findByTestId('order-panel')).toBeInTheDocument()
    expect(JSON.parse(localStorage.getItem('intent.account') ?? '{}').door).toBe('guest')
  })
  it('без секрета ведущего кнопки «Сбросить демо» нет', async () => {
    renderAt('/more')
    await screen.findByText('Было / Стало · Тот же покупатель цемента — сегодня и у нас')
    expect(screen.queryByTestId('reset-demo')).not.toBeInTheDocument()
  })
})

describe('результат по двум заводам', () => {
  it('крупно — средняя цена, под ней строки по каждой части, которые сходятся', async () => {
    const run = {
      run_id: 'R-1', basket_id: 'B-1', engine_version: 'clearing-1.0.0', clearing_price_t: 500_000, executed_qty_t: 200,
      allocations: [
        { mandate_id: 'DDDD-04', offer_id: 'A-SBF', seller: 'Shangfeng-Bridge of Friendship', qty_t: 50, price_t: 500_000, tariff_t: 11_000, delivered_price_t: 511_000, lot_group_id: 'L1' },
        { mandate_id: 'DDDD-04', offer_id: 'A-TCC', seller: 'Toshkent Conch Cement', qty_t: 150, price_t: 500_000, tariff_t: 22_000, delivered_price_t: 522_000, lot_group_id: 'L2' },
      ],
      unfilled: [], aggregates: { demand_curve: [[500000, 200]], supply_curve: [[500000, 200]], total_demand: 610, total_supply: 1000, n_bids: 9, n_asks: 5, n_executed_bids: 7 },
      tie_break_used: 'min_surplus', inputs_hash: 'x',
    } as unknown as ClearingResult
    vi.spyOn(api, 'mine').mockResolvedValue([{ mandate_id: 'DDDD-04', status: 'filled', qty_t: 200, region: 'Namangan', grade: '32.5', max_price_t: 1_000_000, run_id: 'R-1', deal_id: 'R-1:DDDD-04' }])
    vi.spyOn(api, 'result').mockResolvedValue(run)
    vi.spyOn(api, 'explain').mockResolvedValue({ mandate_id: 'DDDD-04', outcome: 'filled', your_qty: 200, your_filled_qty: 200, your_max: 1_000_000, your_price_delivered: 519_250, clearing_price_base: 500_000, total_demand_t: 610, total_supply_t: 1000, n_buyers: 9, n_plants: 5 })
    renderAt('/orders/DDDD-04')
    const parts = await screen.findByTestId('result-parts', {}, { timeout: 4000 })
    expect(parts).toHaveTextContent('50 т · Shangfeng-Bridge of Friendship · 511 000 = 500 000 + доставка 11 000')
    expect(parts).toHaveTextContent('150 т · Toshkent Conch Cement · 522 000 = 500 000 + доставка 22 000')
    expect(screen.getByText(/в среднем/)).toBeInTheDocument()
  })
})

describe('окно корзины словами', () => {
  it('«пн, 9 ноября, 11:30–11:50» и по-узбекски', async () => {
    const { windowWords } = await import('../lib/labels')
    const { translate } = await import('../i18n')
    expect(windowWords((k, v) => translate('ru', k, v), '2026-11-09T11:30', '2026-11-09T11:50')).toBe('пн, 9 ноября, 11:30–11:50')
    expect(windowWords((k, v) => translate('uz', k, v), '2026-11-09T11:30', '2026-11-09T11:50')).toBe('dush, 9 noyabr, 11:30–11:50')
  })
})

describe('изменение цены на карточке инструмента', () => {
  const pts = [
    { date: '2026-10-12', vwap: 535585, volume_t: 1, n_deals: 117 },
    { date: '2026-10-19', vwap: 569210, volume_t: 1, n_deals: 121 },
    { date: '2026-10-26', vwap: 766000, volume_t: 500, n_deals: 5 },
    { date: '2026-11-02', vwap: 507317, volume_t: 1, n_deals: 163 },
  ]
  it('неделя-выброс (меньше 10 сделок) не становится опорной', async () => {
    const { weekStats } = await import('../features/MarketParts')
    const s = weekStats({ points: pts })
    expect(s.price).toBe(507317)
    expect(s.basis).toBe('2026-10-19')
    expect(s.pct).toBeCloseTo(-10.87, 1)
  })
  it('headline с бэкенда важнее; change_pct null — процента нет', async () => {
    const { weekStats } = await import('../features/MarketParts')
    expect(weekStats({ points: pts, headline: { last_vwap: 507317, prev_vwap: 569210, change_pct: -10.9, basis: '2026-10-19' } })).toEqual({ price: 507317, pct: -10.9, basis: '2026-10-19' })
    expect(weekStats({ points: pts, headline: { last_vwap: 507317, prev_vwap: null, change_pct: null, basis: null } }).pct).toBeNull()
  })
})

describe('headline: дата опорной недели из prev_from', () => {
  it('берёт prev_from, а не русскую строку basis', async () => {
    const { weekStats } = await import('../features/MarketParts')
    expect(weekStats({ points: [], headline: { last_vwap: 507317, last_from: '2026-11-02', prev_vwap: 569210, prev_from: '2026-10-19', change_pct: -10.9, basis: 'к неделе 19.10 (121 сделок)' } }).basis).toBe('2026-10-19')
  })
})
