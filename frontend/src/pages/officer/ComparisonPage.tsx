/**
 * CrossDocumentAnalysisPage — hub showing all applications with cross-document
 * discrepancies, ordered by severity. Links to each application's Cross-Document tab.
 *
 * Data: GET /applications + GET /applications/{id}/reconciliation-items (per-app)
 * No synthetic data — outcomes never label fraud.
 */
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, GitCompare, RefreshCw } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { StatusDot } from '@/components/ui/StatusDot'
import { SkeletonCard, SkeletonMetricRow } from '@/components/ui/Skeleton'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import type { ApplicationSummary, Discrepancy } from '@/types'

type Row = {
  app: ApplicationSummary
  openConflicts: number
  items: Discrepancy[]
  loadError: boolean
}

const OUTCOME_COLORS: Record<string, string> = {
  MISMATCH: '#B91C1C',
  MISSING_DATA: '#B45309',
  POSSIBLE_DUPLICATE: '#7C3AED',
  MANUAL_REVIEW: '#555555',
  MATCH: '#2E7D52',
}

const OUTCOME_LABELS: Record<string, string> = {
  MISMATCH: 'Mismatch',
  MISSING_DATA: 'Missing data',
  POSSIBLE_DUPLICATE: 'Possible duplicate',
  MANUAL_REVIEW: 'Needs review',
  MATCH: 'Match',
}

export function CrossDocumentAnalysisPage() {
  const { role } = useRole()
  const [rows, setRows] = useState<Row[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showAll, setShowAll] = useState(false)

  function load() {
    let cancelled = false
    setLoading(true)
    setError(null)
    api
      .listApplications(role)
      .then(async (apps) => {
        const enriched: Row[] = []
        for (const app of apps.slice(0, 40)) {
          try {
            const items = await api.listReconciliationItems(role, app.id)
            const openConflicts = items.filter(
              (i) => i.outcome !== 'MATCH' && i.status === 'open',
            ).length
            enriched.push({ app, openConflicts, items, loadError: false })
          } catch {
            enriched.push({ app, openConflicts: 0, items: [], loadError: true })
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
    return () => { cancelled = true }
  }

  useEffect(load, [role]) // eslint-disable-line react-hooks/exhaustive-deps

  const withConflicts = useMemo(
    () => rows.filter((r) => r.openConflicts > 0).sort((a, b) => b.openConflicts - a.openConflicts),
    [rows],
  )
  const clean = useMemo(() => rows.filter((r) => r.openConflicts === 0), [rows])

  const displayRows = showAll ? withConflicts : withConflicts.slice(0, 10)

  return (
    <AppShell
      title="Cross-Document Analysis"
      description="Applications with open cross-document discrepancies. Outcomes describe data comparisons only — they never label fraud or imply rejection."
      breadcrumbs={['Scrutiny Officer', 'Cross-Document']}
      actions={
        <button
          type="button"
          onClick={load}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-40"
          style={{ border: '1px solid #E0E0E0', color: '#555555' }}
          onMouseEnter={(e) => (e.currentTarget.style.background = '#F5F5F5')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          aria-label="Refresh"
        >
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      }
    >
      {/* Note banner */}
      <div
        className="mb-5 rounded-xl px-4 py-3 text-xs leading-relaxed"
        style={{ background: '#F0F9FF', border: '1px solid #BAE6FD', color: '#0369A1' }}
      >
        <strong>Note:</strong> Cross-document discrepancies represent comparison outcomes between
        extracted fields in uploaded documents. A mismatch indicates the same field has different
        values across documents, not that any document is fraudulent. Each finding should be
        reviewed in context using the linked evidence.
      </div>

      {error && (
        <div
          className="mb-5 rounded-xl px-4 py-3 text-sm"
          style={{ background: '#FEF3C7', color: '#B45309', border: '1px solid #FDE68A' }}
        >
          {error}
        </div>
      )}

      {/* Summary metrics */}
      {loading ? (
        <SkeletonMetricRow cells={4} />
      ) : !error && (
        <div
          className="flex overflow-hidden rounded-xl mb-5"
          style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
        >
          {[
            { label: 'Checked', value: rows.length, hint: 'Applications reviewed' },
            { label: 'Open Conflicts', value: withConflicts.length, hint: 'Need attention' },
            {
              label: 'Total Open Findings',
              value: withConflicts.reduce((s, r) => s + r.openConflicts, 0),
              hint: 'Across all applications',
            },
            { label: 'Clean', value: clean.length, hint: 'No open conflicts' },
          ].map((m) => (
            <div key={m.label} className="flex-1 px-6 py-5">
              <div
                className="text-[11px] font-semibold uppercase tracking-widest mb-1"
                style={{ color: '#AAAAAA' }}
              >
                {m.label}
              </div>
              <div className="text-3xl font-bold tabular-nums" style={{ color: '#111111' }}>
                {m.value}
              </div>
              <div className="text-[11px] mt-1" style={{ color: '#888888' }}>
                {m.hint}
              </div>
            </div>
          ))}
        </div>
      )}

      {loading ? (
        <div className="space-y-4">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : withConflicts.length === 0 && !error ? (
        <div
          className="rounded-xl px-6 py-14 text-center"
          style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
        >
          <GitCompare size={36} className="mx-auto mb-3" style={{ color: '#D4FAE6' }} />
          <div className="text-sm font-medium" style={{ color: '#111111' }}>
            No open cross-document conflicts
          </div>
          <div className="text-[12px] mt-1" style={{ color: '#888888' }}>
            All extracted fields match across documents for your assigned applications. Resolved items
            remain visible in each application's Cross-Document tab.
          </div>
        </div>
      ) : (
        <div
          className="rounded-xl overflow-hidden"
          style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
        >
          <div className="px-6 py-4" style={{ borderBottom: '1px solid #F0F0F0' }}>
            <div className="text-sm font-semibold" style={{ color: '#111111' }}>
              {withConflicts.length} application{withConflicts.length !== 1 ? 's' : ''} with open discrepancies
            </div>
            <div className="text-[11px] mt-0.5" style={{ color: '#888888' }}>
              Ordered by number of open conflicts · Open an application to review evidence and record a resolution.
            </div>
          </div>

          <ul>
            {displayRows.map(({ app, openConflicts, items }) => {
              const openItems = items.filter((i) => i.outcome !== 'MATCH' && i.status === 'open')
              return (
                <li
                  key={app.id}
                  className="px-6 py-5 transition-colors hover:bg-[#FAFAFA]"
                  style={{ borderBottom: '1px solid #F0F0F0' }}
                >
                  <div className="flex items-start justify-between gap-4 flex-wrap">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-3 flex-wrap">
                        <span className="mono text-sm font-semibold" style={{ color: '#111111' }}>
                          {app.applicationNumber}
                        </span>
                        <span className="text-[12px]" style={{ color: '#888888' }}>
                          {app.institutionName}
                        </span>
                        <StatusDot status={app.stage ?? app.status} label={app.stageLabel ?? app.status} />
                      </div>
                      <div className="text-[11px] mt-1" style={{ color: '#888888' }}>
                        {app.category}
                      </div>

                      {/* Discrepancy chips */}
                      <div className="flex flex-wrap gap-2 mt-3">
                        {openItems.slice(0, 5).map((item) => (
                          <span
                            key={item.id}
                            className="rounded-lg px-2.5 py-1 text-[11px] font-medium"
                            style={{
                              background: '#F8F8F8',
                              border: '1px solid #E0E0E0',
                              color: OUTCOME_COLORS[item.outcome] ?? '#555555',
                            }}
                          >
                            {OUTCOME_LABELS[item.outcome] ?? item.outcome} · {item.fieldName}
                          </span>
                        ))}
                        {openItems.length > 5 && (
                          <span
                            className="rounded-lg px-2.5 py-1 text-[11px]"
                            style={{
                              background: '#F5F5F5',
                              border: '1px solid #E0E0E0',
                              color: '#888888',
                            }}
                          >
                            +{openItems.length - 5} more
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      <div className="text-right">
                        <div
                          className="text-lg font-bold tabular-nums"
                          style={{ color: openConflicts > 0 ? '#B91C1C' : '#2E7D52' }}
                        >
                          {openConflicts}
                        </div>
                        <div className="text-[10px]" style={{ color: '#888888' }}>
                          open finding{openConflicts !== 1 ? 's' : ''}
                        </div>
                      </div>
                      <Link to={`/officer/applications/${app.id}?tab=cross`}>
                        <button
                          type="button"
                          className="flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-semibold text-white transition-opacity hover:opacity-90"
                          style={{ background: '#E8622A' }}
                        >
                          Review
                          <ArrowRight size={12} />
                        </button>
                      </Link>
                    </div>
                  </div>
                </li>
              )
            })}
          </ul>

          {withConflicts.length > 10 && !showAll && (
            <div className="px-6 py-4 text-center" style={{ borderTop: '1px solid #F0F0F0' }}>
              <button
                type="button"
                onClick={() => setShowAll(true)}
                className="text-sm font-medium"
                style={{ color: '#E8622A' }}
              >
                Show all {withConflicts.length} applications →
              </button>
            </div>
          )}
        </div>
      )}
    </AppShell>
  )
}
