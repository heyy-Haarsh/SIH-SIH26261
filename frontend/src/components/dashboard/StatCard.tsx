import type { LucideIcon } from 'lucide-react'

/**
 * Lintel-style metric cell: no card border, just label → big number → trend text.
 * Used inside a flexbox row separated by thin vertical dividers.
 */
export function StatCard({
  label,
  value,
  hint,
  trend,
  trendUp,
  icon: _Icon,
}: {
  label: string
  value: string | number
  hint?: string
  trend?: string
  trendUp?: boolean
  icon?: LucideIcon
}) {
  return (
    <div className="flex-1 px-6 py-5 metric-divider">
      <div
        className="text-[11px] font-medium uppercase tracking-wider mb-1"
        style={{ color: '#999999' }}
      >
        {label}
      </div>
      <div
        className="text-[28px] font-bold leading-none tracking-tight"
        style={{ color: '#111111' }}
      >
        {value}
      </div>
      {(hint || trend) && (
        <div
          className="mt-1.5 text-[11px]"
          style={{ color: trendUp ? '#2E7D52' : trend ? '#888888' : '#888888' }}
        >
          {trend ?? hint}
        </div>
      )}
    </div>
  )
}
