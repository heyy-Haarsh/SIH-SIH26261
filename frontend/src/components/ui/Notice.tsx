import type { ReactNode } from 'react'
import { clsx } from 'clsx'
import { Button } from './Button'

type Tone = 'neutral' | 'warning' | 'error' | 'success'

/** Flat Lintel-style tone mappings */
const TONES: Record<Tone, { bg: string; border: string; text: string }> = {
  neutral: { bg: '#FAFAFA', border: '#E0E0E0', text: '#555555' },
  warning: { bg: '#FFFBEB', border: '#FDE68A', text: '#92400E' },
  error:   { bg: '#FEF2F2', border: '#FECACA', text: '#991B1B' },
  success: { bg: '#F0FDF4', border: '#BBF7D0', text: '#166534' },
}

/** Inline message with an optional real retry. Errors are announced to assistive tech. */
export function Notice({
  tone = 'neutral',
  title,
  children,
  onRetry,
  retryLabel = 'Try again',
  className,
}: {
  tone?: Tone
  title?: string
  children?: ReactNode
  onRetry?: () => void
  retryLabel?: string
  className?: string
}) {
  const s = TONES[tone]
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={clsx('rounded-xl px-4 py-3 text-sm', className)}
      style={{ background: s.bg, border: `1px solid ${s.border}`, color: s.text }}
    >
      {title && <p className="font-semibold mb-0.5">{title}</p>}
      {children && <div className="leading-relaxed">{children}</div>}
      {onRetry && (
        <div className="mt-2">
          <Button size="sm" variant="outline" onClick={onRetry}>
            {retryLabel}
          </Button>
        </div>
      )}
    </div>
  )
}

/** A bounded loading placeholder: names what is loading. */
export function Loading({ label = 'Loading' }: { label?: string }) {
  return (
    <p
      className="px-1 py-6 text-sm"
      style={{ color: '#888888' }}
      role="status"
      aria-live="polite"
    >
      {label}…
    </p>
  )
}
