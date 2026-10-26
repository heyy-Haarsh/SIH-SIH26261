import { Info } from 'lucide-react'

export function DemoBanner({ children }: { children: string }) {
  return (
    <div className="mb-4 flex items-start gap-2 rounded-[var(--radius-md)] border border-sky-200 bg-status-info-bg px-3 py-2.5 text-xs text-status-info">
      <Info size={14} className="mt-0.5 shrink-0" />
      <p>{children}</p>
    </div>
  )
}
