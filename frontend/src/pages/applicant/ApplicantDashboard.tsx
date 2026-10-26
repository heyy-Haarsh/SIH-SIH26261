import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, FilePlus2, FolderOpen, Upload } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { StatCard } from '@/components/dashboard/StatCard'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { ApplicationTable } from '@/components/applications/ApplicationTable'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import type { ApplicationSummary } from '@/types'

export function ApplicantDashboard() {
  const { user, role } = useRole()
  const [apps, setApps] = useState<ApplicationSummary[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .listApplications(role)
      .then(setApps)
      .catch((err) => {
        setError(
          err instanceof ApiError
            ? `API (${err.status}): ${err.message}`
            : 'Backend unreachable — start the API on port 8000.',
        )
      })
  }, [role])

  return (
    <AppShell title="Institution Dashboard" breadcrumbs={['Applicant', 'Dashboard']}>
      <DemoBanner>
        {`Applicant workspace for ${user.institutionName ?? 'your institution'}. Live API data when the backend is running.`}
      </DemoBanner>

      {error && (
        <div className="mb-4 rounded-[var(--radius-md)] border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          {error}
        </div>
      )}

      {apps.reduce((n, a) => n + a.deficiencyCount, 0) > 0 && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-md)] border border-amber-300 bg-amber-50 px-4 py-3">
          <div className="text-sm text-amber-950">
            <span className="font-semibold">Action needed:</span> officers requested clarification on{' '}
            {apps.filter((a) => a.deficiencyCount > 0 || a.status === 'clarification_required').length}{' '}
            application(s). Respond, upload corrections, then resubmit.
          </div>
          <Link to="/applicant/deficiencies">
            <Button size="sm" leftIcon={<AlertTriangle size={14} />}>
              Review clarifications
            </Button>
          </Link>
        </div>
      )}

      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="My applications" value={apps.length} icon={FolderOpen} />
        <StatCard
          label="Open deficiencies"
          value={apps.reduce((n, a) => n + a.deficiencyCount, 0)}
          icon={AlertTriangle}
        />
        <StatCard
          label="Awaiting review"
          value={apps.filter((a) => a.status === 'awaiting_review').length}
          icon={CheckCircle2}
        />
        <StatCard
          label="Needs manual review"
          value={apps.filter((a) => a.requiresManualReview).length}
          icon={Upload}
        />
      </div>

      <div className="mb-5 flex flex-wrap gap-2">
        <Link to="/applicant/applications/new">
          <Button leftIcon={<FilePlus2 size={16} />}>New application</Button>
        </Link>
        <Link to="/applicant/uploads">
          <Button variant="outline" leftIcon={<Upload size={16} />}>
            Upload documents
          </Button>
        </Link>
        <Link to="/applicant/deficiencies">
          <Button variant="secondary" leftIcon={<AlertTriangle size={16} />}>
            View deficiencies
          </Button>
        </Link>
      </div>

      <Card>
        <CardHeader
          title="My applications"
          description="Applications belonging to your institution"
          action={
            <Link to="/applicant/applications">
              <Button variant="outline" size="sm">
                View all
              </Button>
            </Link>
          }
        />
        <ApplicationTable rows={apps} detailBasePath="/applicant/applications" />
      </Card>
    </AppShell>
  )
}
