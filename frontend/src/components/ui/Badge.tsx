import { clsx } from 'clsx'
import type { ReactNode } from 'react'

type Tone =
  | 'neutral'
  | 'pass'
  | 'warning'
  | 'failed'
  | 'pending'
  | 'manual'
  | 'info'
  | 'brand'

interface BadgeProps {
  children: ReactNode
  tone?: Tone
  className?: string
}

const tones: Record<Tone, string> = {
  neutral: 'bg-surface-muted text-ink-secondary border-border',
  pass: 'bg-status-pass-bg text-status-pass border-emerald-200',
  warning: 'bg-status-warning-bg text-status-warning border-amber-200',
  failed: 'bg-status-failed-bg text-status-failed border-red-200',
  pending: 'bg-status-pending-bg text-status-pending border-gray-200',
  manual: 'bg-status-manual-bg text-status-manual border-violet-200',
  info: 'bg-status-info-bg text-status-info border-sky-200',
  brand: 'bg-brand-soft text-brand border-[#c5d4e6]',
}

export function Badge({ children, tone = 'neutral', className }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium whitespace-nowrap',
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}
