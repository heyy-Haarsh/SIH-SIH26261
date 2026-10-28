import type { ReactNode } from 'react'
import { Info } from 'lucide-react'

export function DemoBanner({ children }: { children: ReactNode }) {
  return (
    <div className="mb-3 flex items-center gap-2 rounded-[var(--radius-md)] border border-sky-200 bg-status-info-bg px-3 py-1.5 text-xs text-status-info">
      <Info size={13} className="shrink-0" />
      <p>{children}</p>
    </div>
  )
}
