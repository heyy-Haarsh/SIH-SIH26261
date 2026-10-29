import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/Badge'
import { stagePresentation } from '@/lib/applicantLifecycle'
import { formatDateTime } from '@/lib/format'
import { SkeletonTable } from '@/components/ui/Skeleton'
import type { ApplicantApplicationSummary } from '@/types'

/** 44px rows. Status comes from the application's stage, never from a locally invented label. */
export function ApplicantApplicationTable({
  rows,
  loading = false,
}: {
  rows: ApplicantApplicationSummary[]
  loading?: boolean
}) {
  if (loading) {
    return (
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead>
            <tr className="border-b border-border text-xs font-medium text-ink-muted">
              <th className="px-4 py-2.5">Application ID</th>
              <th className="px-4 py-2.5">Institution</th>
              <th className="px-4 py-2.5">Category</th>
              <th className="px-4 py-2.5">Status</th>
              <th className="px-4 py-2.5">Last Updated</th>
              <th className="px-4 py-2.5">Next Action</th>
            </tr>
          </thead>
        </table>
        <SkeletonTable rows={5} cols={6} />
      </div>
    )
  }

  if (rows.length === 0) {
    return <p className="px-4 py-8 text-sm text-ink-muted">No applications match this view.</p>
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-left text-sm">
        <thead>
          <tr className="border-b border-border text-xs font-medium text-ink-muted">
            <th className="px-4 py-2.5">Application ID</th>
            <th className="px-4 py-2.5">Institution</th>
            <th className="px-4 py-2.5">Category</th>
            <th className="px-4 py-2.5">Status</th>
            <th className="px-4 py-2.5">Last Updated</th>
            <th className="px-4 py-2.5">Next Action</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const st = stagePresentation(row.stage)
            const Icon = st.icon
            return (
              <tr key={row.id} className="h-11 border-b border-border last:border-0 hover:bg-surface">
                <td className="px-4">
                  <Link to={`/applicant/applications/${row.id}`} className="mono text-ink hover:underline">
                    {row.applicationNumber}
                  </Link>
                </td>
                <td className="px-4 text-ink">{row.institutionName}</td>
                <td className="px-4 text-ink-secondary">{row.category}</td>
                <td className="px-4">
                  <span className="inline-flex items-center gap-1.5">
                    <Icon size={16} strokeWidth={1.5} aria-hidden />
                    <span>{st.label}</span>
                  </span>
                </td>
                <td className="px-4 text-xs text-ink-muted">{formatDateTime(row.updatedAt ?? row.submittedAt)}</td>
                <td className="px-4">
                  {row.openClarifications > 0 ? (
                    <Badge tone="warning">{row.openClarifications} to answer</Badge>
                  ) : (
                    <span className="text-xs text-ink-secondary">{row.nextAction?.title ?? st.meaning}</span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
