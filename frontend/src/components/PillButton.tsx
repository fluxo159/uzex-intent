import type { ButtonHTMLAttributes, ReactNode } from 'react'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'lime' | 'ghost'
  arrow?: boolean
  children: ReactNode
  block?: boolean
}

export function PillButton({ variant = 'lime', arrow = false, block = true, children, className = '', ...rest }: Props) {
  const base = 'tap focus-ring rounded-full px-[18px] py-[14px] text-center text-[15px] font-semibold transition-[opacity,transform] duration-[120ms] active:scale-[0.98] disabled:active:scale-100 disabled:opacity-40 disabled:cursor-not-allowed'
  const v = variant === 'lime' ? 'bg-lime text-lime-ink hover:opacity-90' : 'bg-s3 text-ink hover:bg-[#2a3125]'
  return (
    <button type="button" className={`${base} ${v} ${block ? 'w-full' : ''} ${className}`} {...rest}>
      {children}
      {arrow ? ' ↗' : null}
    </button>
  )
}

export const PrimaryButton = (p: Omit<Props, 'variant'>) => <PillButton variant="lime" arrow {...p} />
