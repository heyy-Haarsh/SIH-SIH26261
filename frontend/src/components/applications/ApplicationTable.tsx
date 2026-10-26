import { Link } from 'react-router-dom'
import type { ApplicationSummary } from '@/types'
import { ApplicationStatusBadge, PriorityBadge } from '@/components/ui/StatusBadge'
import { formatDate } from '@/lib/format'
import { Button } from '@/components/ui/Button'
import { Eye } from 'lucide-react'

export function ApplicationTable({
  rows,
  detailBasePath,
}: {
  rows: ApplicationSummary[]
  detailBasePath: string
}) {
  if (rows.length === 0) {
    return (
      <div className="px-4 py-10 text-center text-sm text-ink-muted">
        No applications match the current filters.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[860px] text-left text-sm">
        <thead>
          <tr className="border-b border-border bg-surface-muted/60 text-xs font-medium uppercase tracking-wide text-ink-muted">
            <th className="px-4 py-3">Application ID</th>
            <th className="px-4 py-3">Institution</th>
            <th className="px-4 py-3">Category</th>
            <th className="px-4 py-3">Submitted</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Priority</th>
            <th className="px-4 py-3 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-b border-border last:border-0 hover:bg-surface-muted/40">
              <td className="px-4 py-3">
                <Link
                  to={`${detailBasePath}/${row.id}`}
                  className="font-medium text-accent hover:underline"
                >
                  {row.applicationNumber}
                </Link>
                {typeof row.priorityScore === 'number' && (
                  <div className="mt-0.5 text-[10px] text-ink-muted">
                    Priority aid: {row.priorityScore} (not a compliance score)
                  </div>
                )}
              </td>
              <td className="px-4 py-3">
                <div className="font-medium text-ink">{row.institutionName}</div>
                <div className="text-[11px] text-ink-muted">{row.institutionId}</div>
              </td>
              <td className="px-4 py-3 text-ink-secondary">{row.category}</td>
              <td className="px-4 py-3 text-ink-secondary">{formatDate(row.submittedAt)}</td>
              <td className="px-4 py-3">
                <ApplicationStatusBadge status={row.status} />
              </td>
              <td className="px-4 py-3">
                <PriorityBadge priority={row.priority} />
              </td>
              <td className="px-4 py-3 text-right">
                <Button
                  variant="outline"
                  size="sm"
                  leftIcon={<Eye size={14} />}
                  onClick={() => {
                    window.location.href = `${detailBasePath}/${row.id}`
                  }}
                >
                  Open
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
