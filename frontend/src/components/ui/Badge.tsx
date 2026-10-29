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
  /** Plain-language meaning (e.g. status vocabulary tooltips). */
  title?: string
}

const tones: Record<Tone, string> = {
  neutral: 'bg-surface-muted text-ink-secondary border-border',
  pass: 'bg-status-pass-bg text-status-pass border-[#cfdad2]',
  warning: 'bg-status-warning-bg text-status-warning border-[#e3d8bd]',
  failed: 'bg-status-failed-bg text-status-failed border-[#e2cbc8]',
  pending: 'bg-status-pending-bg text-status-pending border-border',
  manual: 'bg-status-manual-bg text-status-manual border-[#d9d3e6]',
  info: 'bg-status-info-bg text-status-info border-[#cbd8e6]',
  brand: 'bg-brand-soft text-brand border-border-strong',
}

export function Badge({ children, tone = 'neutral', className, title }: BadgeProps) {
  return (
    <span
      title={title}
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
