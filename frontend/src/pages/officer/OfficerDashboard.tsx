import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, ClipboardList, FileSearch, ShieldAlert } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { StatCard } from '@/components/dashboard/StatCard'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { ApplicationTable } from '@/components/applications/ApplicationTable'
import { ApplicationStatusBadge, PriorityBadge } from '@/components/ui/StatusBadge'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import type { ApplicationMetrics, ApplicationSummary } from '@/types'

export function OfficerDashboard() {
  const { role } = useRole()
  const [apps, setApps] = useState<ApplicationSummary[]>([])
  const [metrics, setMetrics] = useState<ApplicationMetrics | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all([api.listApplications(role), api.applicationMetrics(role)])
      .then(([list, m]) => {
        setApps(list)
        setMetrics(m)
      })
      .catch((err) =>
        setError(
          err instanceof ApiError
            ? err.message
            : 'Backend unreachable — start the API on port 8000.',
        ),
      )
      .finally(() => setLoading(false))
  }, [role])

  // "Queue" = the officer's own turn (awaiting or under scrutiny). Applications waiting on the
  // applicant are counted separately so they do not inflate the workload.
  const queue = useMemo(
    () => apps.filter((a) => a.stage === 'awaiting_scrutiny' || a.stage === 'under_scrutiny'),
    [apps],
  )
  const highPriority = useMemo(
    () =>
      [...queue]
        .sort((a, b) => (b.priorityScore ?? 0) - (a.priorityScore ?? 0))
        .slice(0, 5),
    [queue],
  )

  const by = metrics?.byStage
  const stats = {
    awaiting: by?.awaiting_scrutiny ?? 0,
    underScrutiny: by?.under_scrutiny ?? 0,
    waitingOnApplicant: by?.awaiting_applicant ?? 0,
    manualReview: metrics?.requiresManualReview ?? 0,
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

      <div className="mb-3 grid gap-2 sm:grid-cols-4">
        <StatCard label="Awaiting scrutiny" value={loading ? '…' : stats.awaiting} icon={ClipboardList} />
        <StatCard label="Under scrutiny" value={loading ? '…' : stats.underScrutiny} icon={FileSearch} />
        <StatCard label="Waiting on applicant" value={loading ? '…' : stats.waitingOnApplicant} icon={AlertTriangle} />
        <StatCard label="Needs manual review" value={loading ? '…' : stats.manualReview} icon={ShieldAlert} />
      </div>

      <div className="mb-3 flex flex-wrap gap-2">
        <Link to="/officer/queue">
          <Button size="sm">Open review queue</Button>
        </Link>
        <Link to="/officer/comparison">
          <Button size="sm" variant="outline">Cross-doc comparison</Button>
        </Link>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card padding={false} className="p-4">
          <div className="mb-3">
            <h2 className="text-sm font-semibold text-ink">Highest priority (score)</h2>
            <p className="text-[11px] text-ink-muted">From persisted score_breakdown contributions</p>
          </div>
          <ul className="space-y-1.5">
            {highPriority.length === 0 && (
              <li className="text-sm text-ink-muted">No applications in queue yet.</li>
            )}
            {highPriority.map((a) => (
              <li
                key={a.id}
                className="flex items-center justify-between gap-2 rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2"
              >
                <div className="min-w-0">
                  <Link
                    className="truncate text-sm font-semibold text-brand hover:underline"
                    to={`/officer/applications/${a.id}`}
                  >
                    {a.applicationNumber}
                  </Link>
                  <div className="truncate text-[11px] text-ink-muted">{a.institutionName}</div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <PriorityBadge priority={a.priority} />
                  <span className="text-sm font-bold tabular-nums text-ink">{a.priorityScore ?? 0}</span>
                  <ApplicationStatusBadge status={a.status} />
                </div>
              </li>
            ))}
          </ul>
        </Card>

        <Card padding={false} className="p-4">
          <div className="mb-3">
            <h2 className="text-sm font-semibold text-ink">Queue snapshot</h2>
            <p className="text-[11px] text-ink-muted">{queue.length} applications</p>
          </div>
          <ApplicationTable rows={queue.slice(0, 8)} detailBasePath="/officer/applications" />
        </Card>
      </div>
    </AppShell>
  )
}
