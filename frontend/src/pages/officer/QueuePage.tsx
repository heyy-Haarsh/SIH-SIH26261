/**
 * Review Queue — officer's work-focused application list.
 *
 * Work filter tabs (per Phase 4 spec):
 *   All Work | In Progress | Clarification Responses | Ready to Complete
 *
 * Secondary filters: category, sort, search.
 * Filter state persisted in URL (?work=&q=&sort=).
 * Links to /officer/applications/:id preserve filter state via browser history.
 */
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Search, Eye, X } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { Select } from '@/components/ui/Input'
import { StatusDot } from '@/components/ui/StatusDot'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import { formatDate, formatRelative } from '@/lib/format'
import type { ApplicationSummary } from '@/types'

// Work filter definitions — derived from actual application states
type WorkFilter = 'all' | 'in_progress' | 'clarification_response' | 'ready_to_complete'

const WORK_TABS: { key: WorkFilter; label: string; hint: string }[] = [
  { key: 'all', label: 'All Work', hint: 'All assigned applications' },
  { key: 'in_progress', label: 'In Progress', hint: 'Under active scrutiny' },
  { key: 'clarification_response', label: 'Clarification Responses', hint: 'Institution has responded' },
  { key: 'ready_to_complete', label: 'Ready to Complete', hint: 'No open findings' },
]

function matchesWorkFilter(a: ApplicationSummary, f: WorkFilter): boolean {
  if (f === 'all') return true
  if (f === 'in_progress') {
    return (
      a.status === 'under_scrutiny' ||
      a.stage === 'under_scrutiny' ||
      a.status === 'submitted' ||
      a.status === 'processing' ||
      a.stage === 'awaiting_scrutiny'
    )
  }
  if (f === 'clarification_response') {
    return a.status === 'resubmitted'
  }
  if (f === 'ready_to_complete') {
    return (
      (a.status === 'under_scrutiny' || a.stage === 'under_scrutiny') &&
      a.findingCount === 0
    )
  }
  return true
}

function nextActionLabel(a: ApplicationSummary): string {
  if (a.status === 'resubmitted') return 'Review clarification response'
  if (a.status === 'submitted' || a.status === 'processing' || a.stage === 'awaiting_scrutiny')
    return 'Start scrutiny'
  if (a.findingCount === 0 && (a.status === 'under_scrutiny' || a.stage === 'under_scrutiny'))
    return 'Record recommendation'
  if (a.status === 'under_scrutiny' || a.stage === 'under_scrutiny') return 'Continue review'
  if (a.status === 'clarification_required') return 'Awaiting institution response'
  if (a.status === 'recommended') return 'Recommended'
  if (a.status === 'rejected') return 'Rejected'
  return a.stageLabel ?? a.status?.replace(/_/g, ' ') ?? '—'
}

export function QueuePage() {
  const { role } = useRole()
  const [searchParams, setSearchParams] = useSearchParams()
  const [apps, setApps] = useState<ApplicationSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // URL-backed filters
  const urlWork = searchParams.get('work') as WorkFilter | null
  const urlQ = searchParams.get('q') ?? ''
  const urlSort = searchParams.get('sort') ?? 'priority'

  const [workFilter, setWorkFilter] = useState<WorkFilter>(
    WORK_TABS.some((t) => t.key === urlWork) ? (urlWork as WorkFilter) : 'all',
  )
  const [query, setQuery] = useState(urlQ)
  const [draftQ, setDraftQ] = useState(urlQ)
  const [sort, setSort] = useState<string>(urlSort)

  function updateParam(key: string, val: string) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (val) next.set(key, val)
      else next.delete(key)
      return next
    }, { replace: true })
  }

  function changeWork(f: WorkFilter) {
    setWorkFilter(f)
    updateParam('work', f === 'all' ? '' : f)
  }
  function applySearch(e: React.FormEvent) {
    e.preventDefault()
    setQuery(draftQ)
    updateParam('q', draftQ)
  }
  function clearFilters() {
    setWorkFilter('all')
    setQuery('')
    setDraftQ('')
    setSort('priority')
    setSearchParams({}, { replace: true })
  }

  useEffect(() => {
    setLoading(true)
    api
      .listApplications(role)
      .then((data) => { setApps(data); setError(null) })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : 'Backend unreachable — start the API on port 8000.'),
      )
      .finally(() => setLoading(false))
  }, [role])

  // Count per work-filter tab
  const counts = useMemo(() => {
    const base: Record<WorkFilter, number> = { all: apps.length, in_progress: 0, clarification_response: 0, ready_to_complete: 0 }
    for (const a of apps) {
      if (matchesWorkFilter(a, 'in_progress')) base.in_progress++
      if (matchesWorkFilter(a, 'clarification_response')) base.clarification_response++
      if (matchesWorkFilter(a, 'ready_to_complete')) base.ready_to_complete++
    }
    return base
  }, [apps])

  const rows = useMemo(() => {
    const q = query.toLowerCase()
    let list = apps.filter((a) => {
      const matchQ =
        !q ||
        a.applicationNumber.toLowerCase().includes(q) ||
        a.institutionName?.toLowerCase().includes(q) ||
        a.category?.toLowerCase().includes(q)
      return matchesWorkFilter(a, workFilter) && matchQ
    })
    if (sort === 'priority') {
      list = [...list].sort((a, b) => (b.priorityScore ?? 0) - (a.priorityScore ?? 0))
    } else {
      list = [...list].sort(
        (a, b) => new Date(b.submittedAt ?? 0).getTime() - new Date(a.submittedAt ?? 0).getTime(),
      )
    }
    return list
  }, [apps, workFilter, query, sort])

  const hasFilters = workFilter !== 'all' || query !== '' || sort !== 'priority'

  return (
    <AppShell
      title="Review Queue"
      description="Applications assigned to you for scrutiny."
      breadcrumbs={['Scrutiny Officer', 'Review Queue']}
    >
      {error && (
        <div
          className="mb-5 rounded-xl px-4 py-3 text-sm"
          style={{ background: '#FEF3C7', color: '#B45309', border: '1px solid #FDE68A' }}
        >
          {error}
        </div>
      )}

      <div
        className="rounded-xl overflow-hidden"
        style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
      >
        {/* Work filter tabs */}
        <div
          className="flex items-center justify-between flex-wrap gap-2 px-4 pt-1"
          style={{ borderBottom: '1px solid #F0F0F0' }}
        >
          <div className="flex items-center overflow-x-auto">
            {WORK_TABS.map((t) => (
              <button
                key={t.key}
                type="button"
                onClick={() => changeWork(t.key)}
                title={t.hint}
                className={`flex items-center gap-1.5 whitespace-nowrap px-4 py-3.5 text-sm transition-colors ${
                  workFilter === t.key ? 'tab-active' : 'tab-inactive'
                }`}
              >
                {t.label}
                {!loading && (
                  <span
                    className="rounded-full px-1.5 py-0.5 text-[10px] font-semibold leading-none"
                    style={{
                      background: workFilter === t.key ? '#111111' : '#F0F0F0',
                      color: workFilter === t.key ? '#FFFFFF' : '#888888',
                    }}
                  >
                    {counts[t.key]}
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* Search + sort toolbar */}
          <div className="flex items-center gap-2 py-2 flex-wrap">
            <form onSubmit={applySearch} className="flex items-center gap-1.5">
              <div
                className="flex items-center gap-2 rounded-lg border px-3 py-1.5"
                style={{ border: '1px solid #E0E0E0', background: '#FAFAFA' }}
              >
                <Search size={13} style={{ color: '#AAAAAA' }} />
                <input
                  type="text"
                  placeholder="Application ID or institution…"
                  value={draftQ}
                  onChange={(e) => setDraftQ(e.target.value)}
                  className="w-44 bg-transparent text-xs outline-none"
                  style={{ color: '#333333' }}
                  aria-label="Search applications"
                />
              </div>
              <button
                type="submit"
                className="rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors"
                style={{ border: '1px solid #E0E0E0', color: '#555555' }}
                onMouseEnter={(e) => (e.currentTarget.style.background = '#F5F5F5')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              >
                Search
              </button>
            </form>

            <Select
              value={sort}
              onChange={(e) => {
                setSort(e.target.value)
                updateParam('sort', e.target.value)
              }}
              className="h-7 rounded-lg border px-2 py-0.5 text-xs"
              style={{ border: '1px solid #E0E0E0', color: '#555555', background: '#FAFAFA' }}
              aria-label="Sort by"
            >
              <option value="priority">Sort: Priority</option>
              <option value="submitted">Sort: Newest</option>
            </Select>

            {hasFilters && (
              <button
                type="button"
                onClick={clearFilters}
                className="flex items-center gap-1 text-xs transition-colors"
                style={{ color: '#888888' }}
                onMouseEnter={(e) => (e.currentTarget.style.color = '#111111')}
                onMouseLeave={(e) => (e.currentTarget.style.color = '#888888')}
              >
                <X size={11} />
                Reset
              </button>
            )}
          </div>
        </div>

        {/* Row count */}
        <div
          className="px-6 py-2 text-[11px] flex items-center justify-between"
          style={{ color: '#AAAAAA', borderBottom: '1px solid #F0F0F0' }}
        >
          <span>
            {loading ? 'Loading…' : `${rows.length} application${rows.length !== 1 ? 's' : ''}`}
            {query && <span> matching "{query}"</span>}
          </span>
          {sort === 'priority' && !loading && rows.some((r) => typeof r.priorityScore === 'number') && (
            <span className="italic">
              Sorted by queue priority score — ordering aid only, not a fraud probability
            </span>
          )}
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr style={{ borderBottom: '1px solid #F0F0F0' }}>
                {['Application', 'Institution', 'Category', 'Submitted', 'Stage', 'Next Action', 'Findings', ''].map(
                  (col) => (
                    <th
                      key={col}
                      className="px-5 py-3 text-[11px] font-semibold uppercase tracking-wider"
                      style={{ color: '#AAAAAA' }}
                    >
                      {col}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <SkeletonTable rows={6} cols={8} />
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-6 py-12 text-center text-sm" style={{ color: '#AAAAAA' }}>
                    {workFilter === 'ready_to_complete'
                      ? 'No applications are ready to complete right now. Review open findings first.'
                      : workFilter === 'clarification_response'
                      ? 'No clarification responses waiting for review.'
                      : apps.length === 0
                      ? 'No applications assigned to you yet.'
                      : 'No applications match the current filters.'}
                  </td>
                </tr>
              ) : (
                rows.map((app) => {
                  const nextAction = nextActionLabel(app)
                  return (
                    <tr
                      key={app.id}
                      className="transition-colors hover:bg-[#FAFAFA]"
                      style={{ borderBottom: '1px solid #F0F0F0' }}
                    >
                      <td className="px-5 py-4">
                        <Link
                          to={`/officer/applications/${app.id}`}
                          className="mono text-sm font-semibold hover:underline"
                          style={{ color: '#111111' }}
                        >
                          {app.applicationNumber}
                        </Link>
                      </td>
                      <td className="px-5 py-4">
                        <span className="text-sm" style={{ color: '#333333' }}>
                          {app.institutionName}
                        </span>
                        {app.assignedOfficer && (
                          <div className="text-[11px] mt-0.5" style={{ color: '#AAAAAA' }}>
                            {app.assignedOfficer}
                          </div>
                        )}
                      </td>
                      <td className="px-5 py-4 text-[12px]" style={{ color: '#888888' }}>
                        {app.category}
                      </td>
                      <td className="px-5 py-4">
                        <div className="text-[12px]" style={{ color: '#888888' }}>
                          {formatDate(app.submittedAt)}
                        </div>
                        <div className="text-[10px] mt-0.5" style={{ color: '#AAAAAA' }}>
                          {formatRelative(app.submittedAt)}
                        </div>
                      </td>
                      <td className="px-5 py-4">
                        <StatusDot status={app.stage ?? app.status} label={app.stageLabel ?? app.status?.replace(/_/g, ' ')} />
                      </td>
                      <td className="px-5 py-4">
                        <span className="text-[12px]" style={{ color: '#555555' }}>
                          {nextAction}
                        </span>
                      </td>
                      <td className="px-5 py-4">
                        {app.findingCount > 0 ? (
                          <span
                            className="rounded-md px-1.5 py-0.5 text-[10px] font-semibold"
                            style={{ background: '#FEF2F2', color: '#B91C1C' }}
                          >
                            {app.findingCount}
                          </span>
                        ) : (
                          <span style={{ color: '#AAAAAA' }}>—</span>
                        )}
                      </td>
                      <td className="px-5 py-4">
                        <Link to={`/officer/applications/${app.id}`}>
                          <button
                            type="button"
                            className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors"
                            style={{ border: '1px solid #E8622A', color: '#E8622A' }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.background = '#FFF5F0'
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.background = 'transparent'
                            }}
                          >
                            <Eye size={12} />
                            Open
                          </button>
                        </Link>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </AppShell>
  )
}
