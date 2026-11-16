import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, type Me } from '../api/client'
import { ErrorBox } from '../components/States'
import { LangProvider } from '../i18n'
import { renderAt } from './render'

const GUEST: Me = { level: 'guest', principal_id: 'g-1', limits_left: { parse_per_min: 10 }, llm: false, voice: false, can_close_basket: false, protected: true }
const JURY: Me = { ...GUEST, level: 'jury', limits_left: { llm_per_hour: 30, stt_per_hour: 20 }, llm: true, voice: true }
const ADMIN: Me = { ...GUEST, level: 'admin', llm: true, voice: true, can_close_basket: true }
const SECRET = 'host-secret-0123456789'

type Call = { url: string; init?: RequestInit }
function protectedBackend(): Call[] {
  const calls: Call[] = []
  const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    calls.push({ url, init })
    const h = (init?.headers ?? {}) as Record<string, string>
    if (url.endsWith('/auth/code')) {
      const { code } = JSON.parse(String(init?.body ?? '{}')) as { code: string }
      return code === 'JURY2035' ? json(JURY) : json({ detail: { code: 'bad_code', message_ru: 'Код не подошёл.', message_uz: 'Kod mos kelmadi.' } }, 401)
    }
    if (url.endsWith('/auth/me')) return json(h['X-Admin-Token'] === SECRET ? ADMIN : GUEST)
    return json({ detail: 'Not Found' }, 404)
  }))
  return calls
}

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('код доступа', () => {
  it('ссылка /?k=КОД применяет код и убирает его из адреса', async () => {
    const calls = protectedBackend()
    renderAt('/more?k=JURY2035', { me: null })
    expect(await screen.findByTestId('access-jury')).toHaveTextContent('жюри: нейросеть и голос включены')
    const post = calls.find((c) => c.url.endsWith('/auth/code'))
    expect(post?.init?.method).toBe('POST')
    expect(JSON.parse(String(post?.init?.body))).toEqual({ code: 'JURY2035' })
    expect(calls.length).toBeGreaterThan(0)
    expect(calls.every((c) => c.init?.credentials === 'include')).toBe(true)
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/more'))
  })
  it('гость видит поле кода и строку про офлайн-разбор; неверный код — понятная строка', async () => {
    protectedBackend()
    renderAt('/more', { me: null })
    expect(await screen.findByTestId('access-guest-note')).toHaveTextContent('нейросеть: 3 разбора в час на человека; у жюри — 30 и голос')
    fireEvent.change(screen.getByTestId('access-input'), { target: { value: 'nope00' } })
    fireEvent.click(screen.getByTestId('access-apply'))
    expect(await screen.findByText('Код не подошёл.')).toBeInTheDocument()
  })
})

describe('микрофон по уровню', () => {
  it('у гостя защищённого стенда микрофона нет', async () => {
    renderAt('/buy', { width: 375, account: { door: 'guest' }, me: GUEST })
    expect(await screen.findByTestId('order-panel')).toBeInTheDocument()
    expect(screen.queryByTestId('mic')).not.toBeInTheDocument()
  })
  it('у жюри микрофон есть', async () => {
    renderAt('/buy', { width: 375, me: JURY })
    expect(await screen.findByTestId('mic')).toBeInTheDocument()
  })
})

describe('кнопки ведущего', () => {
  it('без секрета кнопки сброса нет', async () => {
    protectedBackend()
    renderAt('/more', { me: null })
    await screen.findByTestId('access-guest-note')
    expect(screen.queryByTestId('reset-demo')).not.toBeInTheDocument()
  })
  it('старый ?admin=1 ничего не даёт и убирается из адреса', async () => {
    protectedBackend()
    renderAt('/more?admin=1', { me: null })
    await screen.findByTestId('access-guest-note')
    expect(screen.queryByTestId('reset-demo')).not.toBeInTheDocument()
    expect(sessionStorage.getItem('intent.adminToken')).toBeNull()
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/more'))
  })
  it('/more?admin=СЕКРЕТ: секрет в sessionStorage, уходит заголовком, кнопка сброса есть, адрес чистый', async () => {
    const calls = protectedBackend()
    renderAt(`/more?admin=${SECRET}`, { me: null })
    expect(await screen.findByTestId('reset-demo')).toBeInTheDocument()
    expect(sessionStorage.getItem('intent.adminToken')).toBe(SECRET)
    const me = calls.find((c) => c.url.endsWith('/auth/me'))
    expect((me?.init?.headers as Record<string, string>)['X-Admin-Token']).toBe(SECRET)
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/more'))
  })
  it('«Закрыть корзину сейчас» — у ведущего есть, у гостя защищённого стенда нет', async () => {
    const a = renderAt('/market', { me: ADMIN })
    expect(await screen.findByTestId('close-basket')).toBeInTheDocument()
    a.unmount()
    renderAt('/market', { me: GUEST })
    await screen.findByTestId('ladder')
    expect(screen.queryByTestId('close-basket')).not.toBeInTheDocument()
  })
})

describe('тексты лимитов', () => {
  it('429 по коду ответа — RU и UZ (латиница)', () => {
    const e = new ApiError(429, { code: 'parse_limit', retry_after: 42, n: 10, message_ru: 'x', message_uz: 'y' })
    const r = render(<LangProvider initial="ru"><ErrorBox detail={e} /></LangProvider>)
    expect(screen.getByTestId('limit-box')).toHaveTextContent('Гостям — не больше 10 разборов фразы в минуту. Подождите 42 с.')
    r.unmount()
    render(<LangProvider initial="uz"><ErrorBox detail={e} /></LangProvider>)
    expect(screen.getByTestId('limit-box')).toHaveTextContent('Mehmonlar uchun — daqiqasiga 10 tadan koʻp tahlil emas. 42 soniya kuting.')
  })
})
