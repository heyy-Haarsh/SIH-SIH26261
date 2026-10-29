import type { CheckLine } from '@/lib/intakeChecks'

/** One row per check. A failure is a single action sentence. */
export function IntakeChecklist({ lines }: { lines: CheckLine[] }) {
  if (lines.length === 0) return null
  return (
    <ul className="mt-3 divide-y divide-border rounded-[var(--radius-md)] border border-border-strong bg-white">
      {lines.map((row) => (
        <li key={row.key} className="flex items-start justify-between gap-4 px-3 py-2">
          <span className="text-xs font-medium text-ink">{row.label}</span>
          <span
            className={`max-w-[28rem] text-right text-xs ${
              row.status === 'fail'
                ? 'font-medium text-status-failed'
                : row.action
                  ? 'text-status-warning'
                  : row.status === 'pending'
                    ? 'text-ink-muted'
                    : 'text-status-pass'
            }`}
          >
            {row.action ??
              (row.status === 'pending'
                ? lines.some((l) => l.status === 'fail')
                  ? 'Not checked yet'
                  : 'Checking…'
                : 'OK')}
          </span>
        </li>
      ))}
    </ul>
  )
}
