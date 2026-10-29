/**
 * CompletedReviewsPage — shows applications where the officer has recorded a
 * recommendation or rejection. Status: recommended | rejected.
 *
 * Data: GET /applications?status=recommended + GET /applications?status=rejected
 */
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Download, ExternalLink, Search } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { StatusDot } from '@/components/ui/StatusDot'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import { formatDate, formatRelative } from '@/lib/format'
import type { ApplicationSummary } from '@/types'

type OutcomeFilter = 'all' | 'recommended' | 'rejected'

const OUTCOME_TABS: { key: OutcomeFilter; label: string }[] = [
  { key: 'all', label: 'All Completed' },
  { key: 'recommended', label: 'Recommended' },
  { key: 'rejected', label: 'Rejected' },
]

export function CompletedReviewsPage() {
  const { role } = useRole()
  const [apps, setApps] = useState<ApplicationSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<OutcomeFilter>('all')
  const [query, setQuery] = useState('')

  useEffect(() => {
    setLoading(true)
    // Fetch both recommended and rejected (two calls, both filtered server-side)
    Promise.all([
      api.listApplications(role, { status: 'recommended' }),
      api.listApplications(role, { status: 'rejected' }),
    ])
      .then(([recommended, rejected]) => {
        setApps([...recommended, ...rejected])
        setError(null)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load completed reviews.'))
      .finally(() => setLoading(false))
  }, [role])

  const counts = useMemo(() => {
    const base: Record<OutcomeFilter, number> = { all: apps.length, recommended: 0, rejected: 0 }
    for (const a of apps) {
      if (a.status === 'recommended') base.recommended++
      if (a.status === 'rejected') base.rejected++
    }
    return base
  }, [apps])

  const rows = useMemo(() => {
    const q = query.toLowerCase()
    return apps.filter((a) => {
      const matchTab = tab === 'all' || a.status === tab
      const matchQ =
        !q ||
        a.applicationNumber.toLowerCase().includes(q) ||
        a.institutionName?.toLowerCase().includes(q)
      return matchTab && matchQ
    })
  }, [apps, tab, query])

  return (
    <AppShell
      title="Completed Reviews"
      description="Applications where you have recorded a recommendation or rejection."
      breadcrumbs={['Scrutiny Officer', 'Completed Reviews']}
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
        {/* Tabs + search */}
        <div
          className="flex items-center justify-between flex-wrap gap-2 px-4 pt-1"
          style={{ borderBottom: '1px solid #F0F0F0' }}
        >
          <div className="flex items-center">
            {OUTCOME_TABS.map((t) => (
              <button
                key={t.key}
                type="button"
                onClick={() => setTab(t.key)}
                className={`flex items-center gap-1.5 px-4 py-3.5 text-sm transition-colors ${
                  tab === t.key ? 'tab-active' : 'tab-inactive'
                }`}
              >
                {t.label}
                <span
                  className="rounded-full px-1.5 py-0.5 text-[10px] font-semibold leading-none"
                  style={{
                    background: tab === t.key ? '#111111' : '#F0F0F0',
                    color: tab === t.key ? '#FFFFFF' : '#888888',
                  }}
                >
                  {counts[t.key]}
                </span>
              </button>
            ))}
          </div>
          <div className="py-2">
            <div
              className="flex items-center gap-2 rounded-lg border px-3 py-1.5"
              style={{ border: '1px solid #E0E0E0', background: '#FAFAFA' }}
            >
              <Search size={13} style={{ color: '#AAAAAA' }} />
              <input
                type="text"
                placeholder="Search by application ID or institution…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-56 bg-transparent text-xs outline-none"
                style={{ color: '#333333' }}
                aria-label="Search completed reviews"
              />
            </div>
          </div>
        </div>

        <div
          className="px-6 py-2 text-[11px]"
          style={{ color: '#AAAAAA', borderBottom: '1px solid #F0F0F0' }}
        >
          {loading ? 'Loading…' : `${rows.length} completed review${rows.length !== 1 ? 's' : ''}`}
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr style={{ borderBottom: '1px solid #F0F0F0' }}>
                {['Application', 'Institution', 'Category', 'Submitted', 'Outcome', 'Actions'].map((col) => (
                  <th
                    key={col}
                    className="px-6 py-3 text-[11px] font-semibold uppercase tracking-wider"
                    style={{ color: '#AAAAAA' }}
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <SkeletonTable rows={5} cols={6} />
              ) : rows.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-6 py-12 text-center text-sm"
                    style={{ color: '#AAAAAA' }}
                  >
                    {tab === 'all'
                      ? 'No completed reviews yet. Applications you recommend or reject will appear here.'
                      : `No ${tab} reviews found.`}
                  </td>
                </tr>
              ) : (
                rows.map((app) => (
                  <tr
                    key={app.id}
                    className="transition-colors hover:bg-[#FAFAFA]"
                    style={{ borderBottom: '1px solid #F0F0F0' }}
                  >
                    <td className="px-6 py-4">
                      <Link
                        to={`/officer/applications/${app.id}`}
                        className="mono text-sm font-semibold hover:underline"
                        style={{ color: '#111111' }}
                      >
                        {app.applicationNumber}
                      </Link>
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-sm" style={{ color: '#333333' }}>
                        {app.institutionName}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-[12px]" style={{ color: '#888888' }}>
                        {app.category}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-[12px]" style={{ color: '#888888' }}>
                        {formatDate(app.submittedAt)}
                      </div>
                      <div className="text-[10px]" style={{ color: '#AAAAAA' }}>
                        {formatRelative(app.submittedAt)}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <StatusDot
                        status={app.status}
                        label={app.status === 'recommended' ? 'Recommended' : 'Rejected'}
                      />
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <Link to={`/officer/applications/${app.id}`}>
                          <button
                            type="button"
                            className="flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors"
                            style={{ border: '1px solid #E0E0E0', color: '#333333' }}
                            onMouseEnter={(e) => (e.currentTarget.style.background = '#F5F5F5')}
                            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                          >
                            <ExternalLink size={11} />
                            Open
                          </button>
                        </Link>
                        <button
                          type="button"
                          className="flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors"
                          style={{ border: '1px solid #E0E0E0', color: '#333333' }}
                          onMouseEnter={(e) => (e.currentTarget.style.background = '#F5F5F5')}
                          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                          onClick={() =>
                            api.downloadScrutinyPdf(role, app.id).then(({ blob, fileName }) => {
                              const url = URL.createObjectURL(blob)
                              const a = document.createElement('a')
                              a.href = url
                              a.download = fileName ?? `scrutiny-report-${app.applicationNumber}.pdf`
                              a.click()
                              URL.revokeObjectURL(url)
                            })
                          }
                        >
                          <Download size={11} />
                          Report
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </AppShell>
  )
}
