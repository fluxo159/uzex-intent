import { useEffect, useRef, useState } from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { fmtNum } from './format'

export const E = [0.2, 0.8, 0.2, 1] as const
export const EASE_CSS = 'cubic-bezier(0.2, 0.8, 0.2, 1)'

export const NO_ANIM = import.meta.env.MODE === 'test'

const cubicOut = (x: number) => 1 - Math.pow(1 - x, 3)

export function useCountUp(target: number | null | undefined, { duration = 400, delay = 0, from0 = false }: { duration?: number; delay?: number; from0?: boolean } = {}): number | null {
  const reduce = useReducedMotion()
  const valid = target !== null && target !== undefined && !Number.isNaN(target)
  const [shown, setShown] = useState<number | null>(() => (valid ? (from0 && !NO_ANIM && !reduce ? 0 : target!) : null))
  const cur = useRef<number | null>(shown)
  useEffect(() => {
    if (!valid) { cur.current = null; setShown(null); return }
    const to = target!
    const from = cur.current
    if (from === null || from === to || NO_ANIM || reduce) { cur.current = to; setShown(to); return }
    let raf = 0
    let t0 = 0
    const step = (ts: number) => {
      if (!t0) t0 = ts
      const el = ts - t0 - delay
      const k = el <= 0 ? 0 : Math.min(1, el / duration)
      const v = from + (to - from) * cubicOut(k)
      cur.current = k >= 1 ? to : v
      setShown(k >= 1 ? to : Math.round(v))
      if (k < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, valid, reduce])
  return shown
}

export function CountUp({ value, duration, delay, from0, className, style, testId }: {
  value: number | null | undefined; duration?: number; delay?: number; from0?: boolean; className?: string; style?: React.CSSProperties; testId?: string
}) {
  const v = useCountUp(value, { duration, delay, from0 })
  return (
    <span data-testid={testId} className={className} style={{ fontVariantNumeric: 'tabular-nums', ...style }}>
      {fmtNum(v)}
    </span>
  )
}

export function Typed({ text, delay = 0, className }: { text: string; delay?: number; className?: string }) {
  const reduce = useReducedMotion()
  const [n, setN] = useState(() => (NO_ANIM || reduce ? text.length : 0))
  useEffect(() => {
    if (NO_ANIM || reduce) { setN(text.length); return }
    setN(0)
    let i = 0
    let iv: ReturnType<typeof setInterval> | undefined
    const start = setTimeout(() => {
      iv = setInterval(() => { i += 1; setN(i); if (i >= text.length && iv) clearInterval(iv) }, 20)
    }, delay)
    return () => { clearTimeout(start); if (iv) clearInterval(iv) }
  }, [text, delay, reduce])
  return (
    <span className={className} aria-label={text}>
      <span aria-hidden>{text.slice(0, n)}</span>
      <span aria-hidden className="opacity-0">{text.slice(n)}</span>
    </span>
  )
}

export function SignRing({ className }: { className?: string }) {
  const reduce = useReducedMotion()
  const still = NO_ANIM || reduce
  return (
    <svg aria-hidden viewBox="0 0 60 60" className={className} style={{ transform: 'rotate(-90deg)' }}>
      <motion.circle cx={30} cy={30} r={28} fill="none" stroke="var(--lime)" strokeWidth={2} strokeLinecap="round"
        initial={still ? false : { pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1.2, ease: 'linear' }} />
    </svg>
  )
}
