import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/Badge'
import { applicationStatusTone } from '@/lib/applicantStatus'
import { formatDate } from '@/lib/format'
import type { ApplicantApplicationSummary } from '@/types'

/** Applicant's own applications: status, document progress and open clarifications only. */
export function ApplicantApplicationTable({ rows }: { rows: ApplicantApplicationSummary[] }) {
  if (rows.length === 0) {
    return <div className="px-4 py-10 text-center text-sm text-ink-muted">No applications yet.</div>
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead>
          <tr className="border-b border-border bg-surface-muted/60 text-xs font-medium uppercase tracking-wide text-ink-muted">
            <th className="px-4 py-3">Application</th>
            <th className="px-4 py-3">Institution</th>
            <th className="px-4 py-3">Documents</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Submitted</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-b border-border last:border-0 hover:bg-surface-muted/40">
              <td className="px-4 py-3">
                <Link to={`/applicant/applications/${row.id}`} className="font-medium text-accent hover:underline">
                  {row.applicationNumber}
                </Link>
                <div className="text-[11px] text-ink-muted">
                  {row.category} · {row.programName} · {row.academicYear}
                </div>
              </td>
              <td className="px-4 py-3 font-medium text-ink">{row.institutionName}</td>
              <td className="px-4 py-3 text-ink-secondary">
                {row.requiredUploaded} of {row.requiredTotal} required uploaded
              </td>
              <td className="px-4 py-3">
                <div className="flex flex-wrap items-center gap-1.5">
                  <Badge tone={applicationStatusTone(row.status)}>{row.statusLabel}</Badge>
                  {row.openClarifications > 0 && (
                    <Badge tone="warning">{row.openClarifications} to answer</Badge>
                  )}
                </div>
              </td>
              <td className="px-4 py-3 text-ink-secondary">{formatDate(row.submittedAt)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
