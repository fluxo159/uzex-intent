import { describe, expect, it } from 'vitest'
import { niceTicks } from '../components/PriceChart'

describe('ось Y графика', () => {
  it('на компьютере — не меньше 5 круглых делений', () => {
    expect(niceTicks(420000, 780000).length).toBeGreaterThanOrEqual(5)
  })
  it('на телефоне — 5 делений там, где круглый шаг даёт 3 или 7', () => {
    expect(niceTicks(420000, 780000, 5, 5)).toEqual([450000, 525000, 600000, 675000, 750000])
  })
})
