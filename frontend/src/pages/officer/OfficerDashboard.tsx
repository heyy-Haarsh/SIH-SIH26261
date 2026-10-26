import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, ClipboardList, FileSearch, ShieldAlert } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { StatCard } from '@/components/dashboard/StatCard'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { ApplicationTable } from '@/components/applications/ApplicationTable'
import { ApplicationStatusBadge, PriorityBadge } from '@/components/ui/StatusBadge'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import type { ApplicationSummary } from '@/types'

const QUEUE_STATUSES = new Set([
  'submitted',
  'processing',
  'under_scrutiny',
  'clarification_required',
  'resubmitted',
  'awaiting_review',
  'under_review',
  'deficiency',
  'manual_review',
])

export function OfficerDashboard() {
  const { role } = useRole()
  const [apps, setApps] = useState<ApplicationSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
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
      .finally(() => setLoading(false))
  }, [role])

  const queue = useMemo(() => apps.filter((a) => QUEUE_STATUSES.has(a.status)), [apps])
  const highPriority = useMemo(
    () =>
      [...queue]
        .sort((a, b) => (b.priorityScore ?? 0) - (a.priorityScore ?? 0))
        .slice(0, 5),
    [queue],
  )

  const stats = {
    totalInQueue: queue.length,
    underScrutiny: queue.filter((a) =>
      ['under_scrutiny', 'under_review', 'awaiting_review', 'manual_review'].includes(a.status),
    ).length,
    clarification: queue.filter((a) =>
      ['clarification_required', 'deficiency'].includes(a.status),
    ).length,
    manualReview: queue.filter((a) => a.requiresManualReview).length,
  }

  return (
    <AppShell title="Scrutiny Dashboard" breadcrumbs={['Scrutiny Officer', 'Dashboard']}>
      <DemoBanner>
        Live queue from the API. Priority scores are explainable prioritization aids — not fraud
        proof or auto-rejection.
      </DemoBanner>

      {error && (
        <div className="mb-4 rounded-[var(--radius-md)] border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          {error}
        </div>
      )}

      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="In queue" value={loading ? '…' : stats.totalInQueue} icon={ClipboardList} />
        <StatCard label="Under scrutiny" value={stats.underScrutiny} icon={FileSearch} />
        <StatCard label="Clarification required" value={stats.clarification} icon={AlertTriangle} />
        <StatCard label="Needs manual review" value={stats.manualReview} icon={ShieldAlert} />
      </div>

      <div className="mb-5 flex flex-wrap gap-2">
        <Link to="/officer/queue">
          <Button>Open review queue</Button>
        </Link>
        <Link to="/officer/comparison">
          <Button variant="outline">Cross-doc comparison</Button>
        </Link>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="Highest priority (score)"
            description="From persisted score_breakdown contributions"
          />
          <ul className="space-y-2">
            {highPriority.length === 0 && (
              <li className="text-sm text-ink-muted">No applications in queue yet.</li>
            )}
            {highPriority.map((a) => (
              <li
                key={a.id}
                className="flex items-center justify-between gap-2 rounded-[var(--radius-md)] border border-border px-3 py-2"
              >
                <div>
                  <Link
                    className="text-sm font-medium text-brand hover:underline"
                    to={`/officer/applications/${a.id}`}
                  >
                    {a.applicationNumber}
                  </Link>
                  <div className="text-[11px] text-ink-muted">{a.institutionName}</div>
                </div>
                <div className="flex items-center gap-2">
                  <PriorityBadge priority={a.priority} />
                  <span className="text-xs font-semibold text-ink">{a.priorityScore ?? 0}</span>
                  <ApplicationStatusBadge status={a.status} />
                </div>
              </li>
            ))}
          </ul>
        </Card>

        <Card>
          <CardHeader title="Queue snapshot" description={`${queue.length} applications`} />
          <ApplicationTable rows={queue.slice(0, 8)} detailBasePath="/officer/applications" />
        </Card>
      </div>
    </AppShell>
  )
}
