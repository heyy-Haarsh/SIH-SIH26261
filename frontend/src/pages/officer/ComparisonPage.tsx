import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { GitCompare } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { Card, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import type { ApplicationSummary, Discrepancy } from '@/types'

type Row = {
  app: ApplicationSummary
  openConflicts: number
  items: Discrepancy[]
}

export function ComparisonPage() {
  const { role } = useRole()
  const [rows, setRows] = useState<Row[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    api
      .listApplications(role)
      .then(async (apps) => {
        const enriched: Row[] = []
        for (const app of apps.slice(0, 25)) {
          try {
            const items = await api.listReconciliationItems(role, app.id)
            const openConflicts = items.filter(
              (i) => i.outcome !== 'MATCH' && i.status === 'open',
            ).length
            enriched.push({ app, openConflicts, items })
          } catch {
            enriched.push({ app, openConflicts: 0, items: [] })
          }
        }
        if (!cancelled) setRows(enriched)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err instanceof ApiError
              ? err.message
              : 'Backend unreachable — start the API on port 8000.',
          )
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [role])

  const withConflicts = useMemo(
    () => rows.filter((r) => r.openConflicts > 0).sort((a, b) => b.openConflicts - a.openConflicts),
    [rows],
  )

  return (
    <AppShell title="Cross-document Comparison" breadcrumbs={['Scrutiny Officer', 'Comparison']}>
      <DemoBanner>
        Application-level reconciliation of extracted fields. Outcomes never label fraud. Open an
        application&apos;s Reconciliation tab to review evidence and record a resolution.
      </DemoBanner>

      <Card>
        <CardHeader
          title="Open reconciliation issues"
          description={
            loading
              ? 'Loading…'
              : `${withConflicts.length} application(s) with open mismatches / missing data / duplicates`
          }
        />
        {error && (
          <div className="mb-4 rounded-[var(--radius-md)] border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
            {error}
          </div>
        )}
        {!loading && !error && withConflicts.length === 0 && (
          <EmptyState
            icon={GitCompare}
            title="No open cross-document conflicts"
            description="Matched fields and cleared items stay on each application’s Reconciliation tab."
          />
        )}
        <ul className="space-y-2">
          {withConflicts.map(({ app, openConflicts, items }) => (
            <li
              key={app.id}
              className="flex flex-col gap-2 rounded-[var(--radius-md)] border border-border px-3 py-3 sm:flex-row sm:items-center sm:justify-between"
            >
              <div>
                <div className="text-sm font-medium text-ink">{app.applicationNumber}</div>
                <div className="text-[11px] text-ink-muted">
                  {app.institutionName} · {app.category}
                </div>
                <div className="mt-1 flex flex-wrap gap-1">
                  {items
                    .filter((i) => i.outcome !== 'MATCH' && i.status === 'open')
                    .slice(0, 4)
                    .map((i) => (
                      <Badge key={i.id} tone="manual">
                        {i.outcome}: {i.fieldName}
                      </Badge>
                    ))}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone="warning">{openConflicts} open</Badge>
                <Link to={`/officer/applications/${app.id}`}>
                  <Button size="sm" variant="outline">
                    Open reconciliation
                  </Button>
                </Link>
              </div>
            </li>
          ))}
        </ul>
      </Card>
    </AppShell>
  )
}
