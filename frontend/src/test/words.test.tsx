import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ru from '../i18n/ru.json'
import uz from '../i18n/uz.json'
import { PHRASE, renderAt } from './render'

const FORBIDDEN_RU = ['мандат', 'коридор', 'батч', 'клиринг', 'стакан', 'лот', 'оферт', 'аллокаци', 'p10', 'p50', 'p90', 'маргинальн', 'pay-as-bid']
const FORBIDDEN_UZ = ['mandat', 'koridor', 'kliring', 'lot', 'oferta', 'allokatsiya', 'batch']
const ALLOWED_PREFIX = ['plant.', 'radar.', 'passport.']

export function hits(text: string, words: string[]): string[] {
  const low = text.toLowerCase()
  return words.filter((w) => new RegExp(`(^|[^a-zа-яёўқғҳ0-9])${w}`, 'iu').test(low))
}

describe('словарь: запрещённые слова', () => {
  it('ни в одной строке пути покупателя (RU)', () => {
    const bad = Object.entries(ru as Record<string, string>).filter(([k]) => !ALLOWED_PREFIX.some((p) => k.startsWith(p))).map(([k, v]) => [k, hits(v, FORBIDDEN_RU)] as const).filter(([, h]) => h.length)
    expect(bad).toEqual([])
  })
  it('ни в одной строке пути покупателя (UZ)', () => {
    const bad = Object.entries(uz as Record<string, string>).filter(([k]) => !ALLOWED_PREFIX.some((p) => k.startsWith(p))).map(([k, v]) => [k, hits(v, FORBIDDEN_UZ)] as const).filter(([, h]) => h.length)
    expect(bad).toEqual([])
  })
  it('RU и UZ — одинаковый набор ключей', () => {
    expect(Object.keys(uz).sort()).toEqual(Object.keys(ru).sort())
  })
})

describe('экраны без запрещённых слов', () => {
  it('рынок на компе', async () => {
    renderAt('/market')
    await screen.findByText('Новое поручение')
    await screen.findAllByTestId('band-supply')
    expect(hits(document.body.textContent ?? '', FORBIDDEN_RU)).toEqual([])
  })
  it('панель поручения после разбора фразы (телефон)', async () => {
    renderAt('/buy', { width: 375 })
    fireEvent.change(await screen.findByLabelText(/как сказали бы по телефону/i), { target: { value: PHRASE } })
    fireEvent.click(screen.getByRole('button', { name: 'Разобрать' }))
    await screen.findByText('Сколько это будет')
    expect(hits(document.body.textContent ?? '', FORBIDDEN_RU)).toEqual([])
  })
})

describe('нет строк вне i18n', () => {
  it('в .tsx нет кириллицы вне комментариев', () => {
    const root = join(__dirname, '..')
    const files: string[] = []
    const walk = (d: string) => {
      for (const f of readdirSync(d)) {
        const p = join(d, f)
        if (statSync(p).isDirectory()) { if (!['test', 'fixtures', 'i18n'].includes(f)) walk(p) } else if (/\.tsx$/.test(f)) files.push(p)
      }
    }
    walk(root)
    const bad: string[] = []
    for (const f of files) {
      const code = readFileSync(f, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '').replace(/\{\/\*[\s\S]*?\*\/\}/g, '')
      if (/[А-Яа-яЁёЎўҚқҒғҲҳ]/.test(code)) bad.push(f)
    }
    expect(bad).toEqual([])
  })
})

describe('переключение языка', () => {
  it('RU → UZ меняет строки входа и не сбрасывает ИНН', async () => {
    renderAt('/welcome', { account: { door: null, inn: '123456789' } })
    expect(screen.getByText('Купить на бирже — за одну фразу')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'UZ' }))
    await waitFor(() => expect(screen.getByText('Birjadan bir jumla bilan xarid qiling')).toBeInTheDocument())
    expect(screen.queryByText('Купить на бирже — за одну фразу')).not.toBeInTheDocument()
    expect((screen.getByPlaceholderText('9 ta raqam') as HTMLInputElement).value).toBe('123456789')
  })
})
