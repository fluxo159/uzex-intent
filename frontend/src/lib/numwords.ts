export type Lang = 'ru' | 'uz'

const RU_ONES_M = ['', 'один', 'два', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять']
const RU_ONES_F = ['', 'одна', 'две', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять']
const RU_TEENS = ['десять', 'одиннадцать', 'двенадцать', 'тринадцать', 'четырнадцать', 'пятнадцать', 'шестнадцать', 'семнадцать', 'восемнадцать', 'девятнадцать']
const RU_TENS = ['', '', 'двадцать', 'тридцать', 'сорок', 'пятьдесят', 'шестьдесят', 'семьдесят', 'восемьдесят', 'девяносто']
const RU_HUNDREDS = ['', 'сто', 'двести', 'триста', 'четыреста', 'пятьсот', 'шестьсот', 'семьсот', 'восемьсот', 'девятьсот']

function ruPlural(n: number, forms: [string, string, string]): string {
  const n10 = n % 10
  const n100 = n % 100
  if (n10 === 1 && n100 !== 11) return forms[0]
  if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) return forms[1]
  return forms[2]
}

function ruTriad(n: number, feminine: boolean): string[] {
  const out: string[] = []
  const h = Math.floor(n / 100)
  const rest = n % 100
  if (h) out.push(RU_HUNDREDS[h])
  if (rest >= 10 && rest < 20) out.push(RU_TEENS[rest - 10])
  else {
    const t = Math.floor(rest / 10)
    const o = rest % 10
    if (t) out.push(RU_TENS[t])
    if (o) out.push((feminine ? RU_ONES_F : RU_ONES_M)[o])
  }
  return out
}

const RU_SCALES: { v: number; forms: [string, string, string]; fem: boolean }[] = [
  { v: 1e9, forms: ['миллиард', 'миллиарда', 'миллиардов'], fem: false },
  { v: 1e6, forms: ['миллион', 'миллиона', 'миллионов'], fem: false },
  { v: 1e3, forms: ['тысяча', 'тысячи', 'тысяч'], fem: true },
]

export function numToWordsRu(n: number): string {
  n = Math.floor(Math.abs(n))
  if (n === 0) return 'ноль'
  const parts: string[] = []
  let rest = n
  for (const s of RU_SCALES) {
    const k = Math.floor(rest / s.v)
    if (k) {
      parts.push(...ruTriad(k, s.fem), ruPlural(k, s.forms))
      rest %= s.v
    }
  }
  if (rest) parts.push(...ruTriad(rest, false))
  return parts.join(' ')
}

export function pluralForm(n: number): 'one' | 'few' | 'many' {
  return ruPlural(Math.floor(Math.abs(n)), ['one', 'few', 'many']) as 'one' | 'few' | 'many'
}

const UZ_ONES = ['', 'bir', 'ikki', 'uch', 'toʻrt', 'besh', 'olti', 'yetti', 'sakkiz', 'toʻqqiz']
const UZ_TENS = ['', 'oʻn', 'yigirma', 'oʻttiz', 'qirq', 'ellik', 'oltmish', 'yetmish', 'sakson', 'toʻqson']

function uzTriad(n: number): string[] {
  const out: string[] = []
  const h = Math.floor(n / 100)
  const t = Math.floor((n % 100) / 10)
  const o = n % 10
  if (h) out.push(UZ_ONES[h], 'yuz')
  if (t) out.push(UZ_TENS[t])
  if (o) out.push(UZ_ONES[o])
  return out
}

const UZ_SCALES: [number, string][] = [[1e9, 'milliard'], [1e6, 'million'], [1e3, 'ming']]

export function numToWordsUz(n: number): string {
  n = Math.floor(Math.abs(n))
  if (n === 0) return 'nol'
  const parts: string[] = []
  let rest = n
  for (const [v, w] of UZ_SCALES) {
    const k = Math.floor(rest / v)
    if (k) {
      parts.push(...uzTriad(k), w)
      rest %= v
    }
  }
  if (rest) parts.push(...uzTriad(rest))
  return parts.join(' ')
}

export function numToWords(n: number, lang: Lang): string {
  return lang === 'uz' ? numToWordsUz(n) : numToWordsRu(n)
}
