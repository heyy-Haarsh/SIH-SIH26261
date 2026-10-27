import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, FilePlus2, FileWarning, FolderOpen, Hourglass } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { StatCard } from '@/components/dashboard/StatCard'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { ApplicantApplicationTable } from '@/components/applicant/ApplicantApplicationTable'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import type { ApplicantApplicationSummary } from '@/types'

export function ApplicantDashboard() {
  const { user, role } = useRole()
  const [apps, setApps] = useState<ApplicantApplicationSummary[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (role !== 'applicant') return
    api
      .listMyApplications(role)
      .then((list) => {
        setApps(list)
        setError(null)
      })
      .catch((err) => {
        setError(
          err instanceof ApiError
            ? `Could not load applications (${err.status}): ${err.message}`
            : 'Cannot reach the server. Please try again shortly.',
        )
      })
  }, [role])

  const needsAction = apps.filter((a) => a.openClarifications > 0 || a.status === 'clarification_required')
  const officerInbox = apps.filter(
    (a) =>
      a.openClarifications > 0 ||
      a.status === 'clarification_required' ||
      a.officerDecision === 'recommended' ||
      a.officerDecision === 'rejected',
  )
  const missingDocs = apps.reduce((n, a) => n + Math.max(0, a.requiredTotal - a.requiredUploaded), 0)
  const inReview = apps.filter((a) =>
    ['submitted', 'processing', 'under_scrutiny', 'resubmitted', 'awaiting_review', 'under_review'].includes(
      a.status,
    ),
  ).length

  return (
    <AppShell title="My Dashboard" breadcrumbs={['Applicant', 'Dashboard']}>
      <p className="mb-4 text-sm text-ink-secondary">
        {user.institutionName ? `Applications for ${user.institutionName}.` : 'Your applications.'}
      </p>

      {error && (
        <div className="mb-4 rounded-[var(--radius-md)] border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          {error}
        </div>
      )}

      {officerInbox.length > 0 && (
        <Card className="mb-5" padding={false}>
          <div className="border-b border-border px-5 py-3">
            <h2 className="text-sm font-semibold text-ink">From the scrutiny officer</h2>
            <p className="text-xs text-ink-muted">Clarifications and decisions on your applications</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr className="border-b border-border bg-surface text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                  <th className="px-4 py-2">Application</th>
                  <th className="px-4 py-2">Officer status</th>
                  <th className="px-4 py-2">What they asked</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody>
                {officerInbox.map((a) => (
                  <tr key={a.id} className="border-b border-border last:border-0">
                    <td className="px-4 py-2.5 font-medium text-ink">{a.applicationNumber}</td>
                    <td className="px-4 py-2.5">
                      {a.openClarifications > 0
                        ? `${a.openClarifications} clarification(s)`
                        : a.officerDecision
                          ? a.officerDecision
                          : a.statusLabel}
                    </td>
                    <td className="px-4 py-2.5 text-ink-secondary">
                      {a.latestRequestTitle || 'Open the application for details'}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <Link to={`/applicant/applications/${a.id}`}>
                        <Button size="sm" variant="outline">
                          Open
                        </Button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="My applications" value={apps.length} icon={FolderOpen} />
        <StatCard label="Need your action" value={needsAction.length} icon={AlertTriangle} />
        <StatCard label="Waiting for review" value={inReview} icon={Hourglass} />
        <StatCard label="Required documents missing" value={missingDocs} icon={FileWarning} />
      </div>

      <Card>
        <CardHeader
          title="My applications"
          action={
            <Link to="/applicant/applications/new">
              <Button size="sm" leftIcon={<FilePlus2 size={14} />}>
                New application
              </Button>
            </Link>
          }
        />
        <ApplicantApplicationTable rows={apps} />
      </Card>
    </AppShell>
  )
}
