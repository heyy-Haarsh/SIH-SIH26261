import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { ApplicantApplicationTable } from '@/components/applicant/ApplicantApplicationTable'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import type { ApplicantApplicationSummary } from '@/types'

export function ApplicantApplicationsPage() {
  const { role } = useRole()
  const [apps, setApps] = useState<ApplicantApplicationSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (role !== 'applicant') {
      setLoading(false)
      setError('Switch to the Applicant role to see your applications.')
      return
    }
    setLoading(true)
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
      .finally(() => setLoading(false))
  }, [role])

  return (
    <AppShell title="My Applications" breadcrumbs={['Applicant', 'Applications']}>
      <Card>
        <CardHeader
          title="Applications"
          description={loading ? 'Loading…' : `${apps.length} application(s)`}
          action={
            <Link to="/applicant/applications/new">
              <Button size="sm">New application</Button>
            </Link>
          }
        />
        {error && (
          <div className="mb-4 rounded-[var(--radius-md)] border border-[#e3d8bd] bg-status-warning-bg px-3 py-2 text-xs text-status-warning">
            {error}
          </div>
        )}
        {!loading && !error && apps.length === 0 ? (
          <p className="mb-4 text-sm text-ink-muted">
            No applications yet.{' '}
            <Link className="underline" to="/applicant/applications/new">
              Create one
            </Link>
            , then upload your documents.
          </p>
        ) : (
          <ApplicantApplicationTable rows={apps} loading={loading} />
        )}
      </Card>
    </AppShell>
  )
}
