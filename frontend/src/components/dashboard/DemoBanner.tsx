import type { ReactNode } from 'react'

/** A quiet note, not a banner: plain muted text with a hairline rule. */
export function DemoBanner({ children }: { children: ReactNode }) {
  return <p className="mb-3 border-l-2 border-border-strong pl-3 text-xs text-ink-muted">{children}</p>
}
