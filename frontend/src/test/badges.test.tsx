import { fireEvent, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PHRASE, renderAt } from './render'

async function parseIn(path: string, opts: Parameters<typeof renderAt>[1] = {}) {
  renderAt(path, opts)
  fireEvent.change(await screen.findByLabelText(/как сказали бы по телефону/i), { target: { value: PHRASE } })
  fireEvent.click(screen.getByRole('button', { name: 'Разобрать' }))
  await screen.findByText('Сколько это будет')
}

describe('плашки демо и модели 2035', () => {
  it('подпись: «демо-подпись» — одна демо-плашка на панель (04c §2)', async () => {
    await parseIn('/buy', { width: 375 })
    expect(screen.getByTestId('badge-demo-sign')).toHaveTextContent('демо-подпись')
    const panel = screen.getByTestId('order-panel')
    expect(panel.querySelectorAll('[data-badge^="demo"]')).toHaveLength(1)
  })
  it('деньги: «демо»', () => {
    renderAt('/money')
    expect(screen.getByTestId('badge-demo-money')).toHaveTextContent('демо')
  })
  it('радар: «демо: участники вымышленные»', () => {
    renderAt('/radar')
    expect(screen.getByTestId('badge-demo-radar')).toHaveTextContent('участники вымышленные')
  })
  it('частное лицо: «модель 2035» в шапке и в панели', async () => {
    await parseIn('/market', { account: { door: 'person' } })
    expect(screen.getByTestId('account-chip')).toHaveTextContent('модель 2035')
    expect(screen.getAllByText('модель 2035').length).toBeGreaterThanOrEqual(1)
  })
  it('источник данных — в строке состояния', () => {
    renderAt('/market')
    expect(screen.getAllByTestId('source-note')[0]).toHaveTextContent('Данные UZEX, сделки до 06.11.2026')
  })
})

describe('подача поручения в панели', () => {
  it('числа прописью одной строкой, «Верно», подпись — и поручение в корзине', async () => {
    await parseIn('/buy', { width: 375 })
    expect(screen.getByTestId('number-confirm')).toHaveTextContent('двести тонн, один миллион сум за тонну — верно?')
    expect(screen.getByTestId('sign-btn')).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Верно' }))
    await waitFor(() => expect(screen.getByTestId('sign-btn')).not.toBeDisabled())
    fireEvent.click(screen.getByTestId('sign-btn'))
    expect(await screen.findByTestId('order-signed', {}, { timeout: 5000 })).toHaveTextContent('в корзине')
  })
  it('поля из фразы помечены «из вашей фразы»', async () => {
    await parseIn('/buy', { width: 375 })
    expect(screen.getAllByText(/из вашей фразы/).length + screen.queryAllByTitle('из вашей фразы').length).toBeGreaterThanOrEqual(4)
    expect((screen.getByTestId('f-qty') as HTMLInputElement).value).toBe('200')
  })
})
