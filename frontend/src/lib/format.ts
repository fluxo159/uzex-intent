export const THIN = ' '

export function fmtNum(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  const neg = n < 0
  const abs = Math.abs(n)
  const [int, frac] = String(Math.round(abs * 100) / 100).split('.')
  const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, THIN)
  return (neg ? '−' : '') + grouped + (frac ? ',' + frac : '')
}

export function fmtPct(rate: number, digits = 4): string {
  const v = (rate * 100).toFixed(digits).replace(/0+$/, '').replace(/\.$/, '')
  return v.replace('.', ',') + '%'
}

export function fmtSignedPct(pct: number): string {
  const s = Math.abs(pct).toFixed(1).replace('.', ',')
  return (pct > 0 ? '+' : pct < 0 ? '−' : '') + s + '%'
}

export function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const m = /T(\d{2}):(\d{2})/.exec(iso)
  if (m) return `${m[1]}:${m[2]}`
  if (/^\d{2}:\d{2}/.test(iso)) return iso.slice(0, 5)
  return '—'
}

export function parseYmd(iso: string | null | undefined): { y: number; m: number; d: number } | null {
  if (!iso) return null
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  if (!m) return null
  return { y: +m[1], m: +m[2], d: +m[3] }
}

export function addDays(ymd: string, days: number): string {
  const p = parseYmd(ymd)
  if (!p) return ymd
  const dt = new Date(Date.UTC(p.y, p.m - 1, p.d + days))
  return dt.toISOString().slice(0, 10)
}

export function shortId(id: string | null | undefined): string {
  if (!id) return '—'
  if (/^[0-9A-Za-z]{2,6}(-[0-9A-Za-z]{1,6}){0,3}$/.test(id)) return id.toUpperCase().replace(/-/g, '·')
  const s = id.replace(/[^0-9A-Za-z]/g, '').toUpperCase()
  const tail = s.slice(-6)
  return tail.length === 6 ? `${tail.slice(0, 4)}·${tail.slice(4)}` : tail
}

export function shortHash(h: string | null | undefined, n = 8): string {
  if (!h) return '—'
  return h.length > n * 2 + 1 ? `${h.slice(0, n)}…${h.slice(-n)}` : h
}
