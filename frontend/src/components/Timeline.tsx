import { useEffect, useRef, type ReactNode } from 'react'
import { motion } from 'motion/react'
import { E, NO_ANIM } from '../lib/motion'

export interface TimelineItem {
  key: string
  title: ReactNode
  time?: string | null
  hint?: ReactNode
  state: 'done' | 'current' | 'pending' | 'bad'
  action?: ReactNode
}

const DOT: Record<TimelineItem['state'], string> = {
  done: 'bg-lime',
  current: 'bg-bg border-2 border-lime',
  pending: 'bg-s3',
  bad: 'bg-bad',
}

export function Timeline({ items }: { items: TimelineItem[] }) {
  const first = useRef(true)
  useEffect(() => { const id = setTimeout(() => { first.current = false }, 50); return () => clearTimeout(id) }, [])
  const STEP = 0.4
  return (
    <ol data-testid="timeline" className="relative">
      {items.map((it, i) => (
        <li key={it.key} className="relative pl-7 pb-5 last:pb-0">
          {i < items.length - 1 ? <motion.span aria-hidden className="absolute left-[5px] top-4 bottom-0 w-[2px] bg-s3" style={{ transformOrigin: 'top' }}
            initial={NO_ANIM || !first.current ? false : { scaleY: 0 }} animate={{ scaleY: 1 }} transition={{ duration: 0.3, delay: i * STEP + 0.25, ease: E }} /> : null}
          <motion.span key={it.state} aria-hidden className={`absolute left-0 top-[5px] h-3 w-3 rounded-full ${DOT[it.state]}`}
            initial={NO_ANIM ? false : { scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ duration: 0.25, delay: first.current ? i * STEP : 0, ease: E }} />
          <div className="flex items-baseline justify-between gap-3">
            <span className={`text-[15px] ${it.state === 'pending' ? 'text-mute' : it.state === 'bad' ? 'text-bad' : 'text-ink'}`}>{it.title}</span>
            {it.time ? <span className="mono text-[13px] text-ink3 whitespace-nowrap">{it.time}</span> : it.state === 'done' ? <span className="text-lime">✓</span> : null}
          </div>
          {it.hint ? <div className="caption mt-[2px]">{it.hint}</div> : null}
          {it.action ? <div className="mt-3">{it.action}</div> : null}
        </li>
      ))}
    </ol>
  )
}
