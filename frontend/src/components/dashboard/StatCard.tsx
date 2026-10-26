import type { LucideIcon } from 'lucide-react'
import { Card } from '@/components/ui/Card'

export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
}: {
  label: string
  value: string | number
  hint?: string
  icon: LucideIcon
}) {
  return (
    <Card className="!p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-medium text-ink-muted">{label}</div>
          <div className="mt-1 text-2xl font-semibold tracking-tight text-ink">{value}</div>
          {hint && <div className="mt-1 text-[11px] text-ink-muted">{hint}</div>}
        </div>
        <div className="flex h-9 w-9 items-center justify-center rounded-[var(--radius-md)] bg-brand-soft text-brand">
          <Icon size={18} />
        </div>
      </div>
    </Card>
  )
}
