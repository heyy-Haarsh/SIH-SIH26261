/**
 * StatusDot — replaces colored pill badges in table rows.
 * Always pairs a colored dot with a text label (WCAG 1.4.1 compliant).
 */

const DOT_COLORS: Record<string, string> = {
  // Application lifecycle
  draft: '#AAAAAA',
  submitted: '#1D4ED8',
  processing: '#B45309',
  under_scrutiny: '#6D28D9',
  clarification_required: '#E8622A',
  resubmitted: '#1D4ED8',
  recommended: '#2E7D52',
  rejected: '#B91C1C',
  approved: '#2E7D52',
  // Stages
  awaiting_scrutiny: '#1D4ED8',
  awaiting_applicant: '#E8622A',
  decided: '#2E7D52',
  // Generic tones
  pass: '#2E7D52',
  warning: '#B45309',
  failed: '#B91C1C',
  pending: '#6B7280',
  manual: '#6D28D9',
  info: '#1D4ED8',
  neutral: '#9CA3AF',
  brand: '#E8622A',
  // Clarification states
  action_required: '#E8622A',
  response_saved: '#1D4ED8',
  awaiting_review: '#6D28D9',
  resolved: '#2E7D52',
  // Health
  healthy: '#2E7D52',
  degraded: '#B91C1C',
  unavailable: '#6B7280',
}

export function StatusDot({
  status,
  label,
  color,
  className = '',
}: {
  status?: string
  label?: string
  color?: string
  className?: string
}) {
  const dot = color ?? DOT_COLORS[status ?? ''] ?? '#9CA3AF'
  const text = label ?? status ?? ''

  return (
    <span className={`inline-flex items-center gap-1.5 ${className}`}>
      <span
        aria-hidden="true"
        style={{
          display: 'inline-block',
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          background: dot,
          flexShrink: 0,
        }}
      />
      <span style={{ color: '#333333' }}>{text}</span>
    </span>
  )
}

/** Lookup the dot color for a given status key */
export function dotColor(status: string): string {
  return DOT_COLORS[status] ?? '#9CA3AF'
}
