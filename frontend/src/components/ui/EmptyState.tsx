import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

/** Minimal typographic empty state: a title, one plain sentence, an optional action. */
export function EmptyState({
  title,
  description,
  action,
}: {
  /** Kept optional so older call sites compile; the design no longer draws a decorative icon. */
  icon?: LucideIcon
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className="px-2 py-10 text-left">
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      <p className="mt-1 max-w-md text-sm text-ink-muted">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
