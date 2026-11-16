import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { NumberConfirm } from '../components/NumberConfirm'
import { LangProvider } from '../i18n'
import { numToWordsRu, numToWordsUz } from '../lib/numwords'

describe('числа прописью', () => {
  it('RU: 200 — двести, 20 — двадцать, 1 000 000 — один миллион', () => {
    expect(numToWordsRu(200)).toBe('двести')
    expect(numToWordsRu(20)).toBe('двадцать')
    expect(numToWordsRu(1_000_000)).toBe('один миллион')
    expect(numToWordsRu(2_000)).toBe('две тысячи')
    expect(numToWordsRu(571_000)).toBe('пятьсот семьдесят одна тысяча')
    expect(numToWordsRu(15)).toBe('пятнадцать')
  })
  it('UZ: 200 — ikki yuz, 20 — yigirma, 1 000 000 — bir million', () => {
    expect(numToWordsUz(200)).toBe('ikki yuz')
    expect(numToWordsUz(20)).toBe('yigirma')
    expect(numToWordsUz(1_000_000)).toBe('bir million')
    expect(numToWordsUz(25)).toBe('yigirma besh')
  })
})

describe('NumberConfirm', () => {
  it('читает 200 т и 1 000 000 сум прописью по-русски, «Верно» вызывает подтверждение', () => {
    const yes = vi.fn()
    render(<LangProvider initial="ru"><NumberConfirm qty={200} price={1_000_000} onYes={yes} onFix={() => undefined} /></LangProvider>)
    expect(screen.getByTestId('confirm-qty')).toHaveTextContent('двести тонн')
    expect(screen.getByTestId('confirm-price')).toHaveTextContent('один миллион сум за тонну')
    fireEvent.click(screen.getByRole('button', { name: 'Верно' }))
    expect(yes).toHaveBeenCalledOnce()
  })
  it('20 т — «двадцать тонн», не «двести»', () => {
    render(<LangProvider initial="ru"><NumberConfirm qty={20} price={650_000} onYes={() => undefined} onFix={() => undefined} /></LangProvider>)
    expect(screen.getByTestId('confirm-qty')).toHaveTextContent(/^двадцать тонн$/)
  })
  it('по-узбекски: ikki yuz tonna / yigirma tonna', () => {
    const { rerender } = render(<LangProvider initial="uz"><NumberConfirm qty={200} price={1_000_000} onYes={() => undefined} onFix={() => undefined} /></LangProvider>)
    expect(screen.getByTestId('confirm-qty')).toHaveTextContent('ikki yuz tonna')
    expect(screen.getByTestId('confirm-price')).toHaveTextContent('bir million')
    rerender(<LangProvider initial="uz"><NumberConfirm qty={20} price={1_000_000} onYes={() => undefined} onFix={() => undefined} /></LangProvider>)
    expect(screen.getByTestId('confirm-qty')).toHaveTextContent('yigirma tonna')
  })
})
