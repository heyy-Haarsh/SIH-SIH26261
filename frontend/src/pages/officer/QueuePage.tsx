import { useEffect, useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { Card, CardHeader } from '@/components/ui/Card'
import { Input, Select } from '@/components/ui/Input'
import { ApplicationTable } from '@/components/applications/ApplicationTable'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import type { ApplicationSummary } from '@/types'

export function QueuePage() {
  const { role } = useRole()
  const [apps, setApps] = useState<ApplicationSummary[]>([])
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .listApplications(role)
      .then(setApps)
      .catch((err) =>
        setError(
          err instanceof ApiError
            ? err.message
            : 'Backend unreachable — start the API on port 8000.',
        ),
      )
  }, [role])

  const rows = useMemo(
    () =>
      apps.filter((a) => {
        const q = query.toLowerCase()
        const matchQ =
          !q ||
          a.applicationNumber.toLowerCase().includes(q) ||
          a.institutionName.toLowerCase().includes(q)
        const matchS = statusFilter === 'all' || a.status === statusFilter
        return matchQ && matchS
      }),
    [apps, query, statusFilter],
  )

  return (
    <AppShell title="Application Queue" breadcrumbs={['Scrutiny Officer', 'Queue']}>
      <DemoBanner>
        Persisted applications from the API. Filter by Phase 5 scrutiny statuses.
      </DemoBanner>
      <Card>
        <CardHeader title="Review queue" description={`${rows.length} applications shown`} />
        {error && (
          <div className="mb-4 rounded-[var(--radius-md)] border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
            {error}
          </div>
        )}
        <div className="mb-4 flex flex-col gap-2 sm:flex-row">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
            <Input
              className="pl-8"
              placeholder="Search applications…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <Select
            className="sm:w-56"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">All statuses</option>
            <option value="submitted">Submitted</option>
            <option value="processing">Processing</option>
            <option value="under_scrutiny">Under scrutiny</option>
            <option value="clarification_required">Clarification required</option>
            <option value="resubmitted">Resubmitted</option>
            <option value="recommended">Recommended</option>
            <option value="rejected">Rejected</option>
          </Select>
        </div>
        <ApplicationTable rows={rows} detailBasePath="/officer/applications" />
      </Card>
    </AppShell>
  )
}
