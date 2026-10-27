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

      {needsAction.length > 0 && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-md)] border border-amber-300 bg-amber-50 px-4 py-3">
          <div className="text-sm text-amber-950">
            <span className="font-semibold">Action needed:</span> the scrutiny officer asked for clarification on{' '}
            {needsAction.length} application{needsAction.length === 1 ? '' : 's'}.
          </div>
          <Link to={`/applicant/applications/${needsAction[0].id}`}>
            <Button size="sm" leftIcon={<AlertTriangle size={14} />}>
              Respond now
            </Button>
          </Link>
        </div>
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
