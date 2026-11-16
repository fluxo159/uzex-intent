import { useId, useState, type ReactNode } from 'react'

export function Disclosure({ label, children, center = false }: { label: string; children: ReactNode; center?: boolean }) {
  const [open, setOpen] = useState(false)
  const id = useId()
  return (
    <div className={center ? 'text-center' : ''}>
      <button type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)} className="tap link focus-ring py-2">
        {label} <span aria-hidden className="text-mute">{open ? '−' : '+'}</span>
      </button>
      {open ? <div id={id} className="text-left text-[13px] text-ink3 leading-[1.5] mt-1 anim-rise">{children}</div> : null}
    </div>
  )
}
