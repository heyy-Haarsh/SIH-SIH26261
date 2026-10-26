import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { ApplicationTable } from '@/components/applications/ApplicationTable'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import type { ApplicationSummary } from '@/types'

export function ApplicantApplicationsPage() {
  const { role } = useRole()
  const [apps, setApps] = useState<ApplicationSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api
      .listApplications(role)
      .then(setApps)
      .catch((err) => {
        setError(
          err instanceof ApiError
            ? `Could not load applications (${err.status}): ${err.message}`
            : 'Backend unreachable — start the API on port 8000.',
        )
      })
      .finally(() => setLoading(false))
  }, [role])

  return (
    <AppShell title="My Applications" breadcrumbs={['Applicant', 'Applications']}>
      <DemoBanner>
        Live applications from the API for the demo applicant user. Switch role to Applicant.
      </DemoBanner>
      <Card>
        <CardHeader
          title="Institution applications"
          description={loading ? 'Loading…' : `${apps.length} application(s)`}
          action={
            <Link to="/applicant/applications/new">
              <Button size="sm">New application</Button>
            </Link>
          }
        />
        {error && (
          <div className="mb-4 rounded-[var(--radius-md)] border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
            {error}
          </div>
        )}
        {!loading && !error && apps.length === 0 && (
          <p className="mb-4 text-sm text-ink-muted">
            No applications yet.{' '}
            <Link className="underline" to="/applicant/applications/new">
              Create one
            </Link>
            , then upload documents.
          </p>
        )}
        <ApplicationTable rows={apps} detailBasePath="/applicant/applications" />
      </Card>
    </AppShell>
  )
}
