/**
 * OfficerClarificationsPage — shows all clarification requests the officer has
 * sent to institutions, along with the response status.
 *
 * Data: GET /deficiencies (all across assigned applications)
 * If the applicant has responded (status=responded), the row is highlighted.
 */
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Eye, Search } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { StatusDot } from '@/components/ui/StatusDot'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import { formatDate, formatRelative } from '@/lib/format'
import type { DeficiencyNotice } from '@/types'

type StatusFilter = 'all' | 'open' | 'responded' | 'closed'

const STATUS_TABS: { key: StatusFilter; label: string }[] = [
  { key: 'all', label: 'All Requests' },
  { key: 'open', label: 'Awaiting Response' },
  { key: 'responded', label: 'Response Received' },
  { key: 'closed', label: 'Resolved' },
]

const STATUS_DOT_MAP: Record<string, { status: string; label: string }> = {
  open: { status: 'clarification_required', label: 'Awaiting response' },
  responded: { status: 'resubmitted', label: 'Response received' },
  closed: { status: 'pass', label: 'Resolved' },
}

export function OfficerClarificationsPage() {
  const { role } = useRole()
  const [items, setItems] = useState<DeficiencyNotice[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<StatusFilter>('all')
  const [query, setQuery] = useState('')

  useEffect(() => {
    setLoading(true)
    api
      .listDeficiencies(role)
      .then((data) => { setItems(data); setError(null) })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load clarifications.'))
      .finally(() => setLoading(false))
  }, [role])

  const counts = useMemo(() => {
    const base: Record<StatusFilter, number> = { all: items.length, open: 0, responded: 0, closed: 0 }
    for (const d of items) {
      if (d.status === 'open') base.open++
      else if (d.status === 'responded') base.responded++
      else if (d.status === 'closed') base.closed++
    }
    return base
  }, [items])

  const rows = useMemo(() => {
    const q = query.toLowerCase()
    return items.filter((d) => {
      const matchTab = tab === 'all' || d.status === tab
      const matchQ =
        !q ||
        d.title.toLowerCase().includes(q) ||
        (d.applicationNumber ?? '').toLowerCase().includes(q)
      return matchTab && matchQ
    })
  }, [items, tab, query])

  return (
    <AppShell
      title="Clarifications"
      description="Requests you have sent to institutions · Highlighted rows have received a response."
      breadcrumbs={['Scrutiny Officer', 'Clarifications']}
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
            {STATUS_TABS.map((t) => (
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
                placeholder="Search by title or application ID…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-52 bg-transparent text-xs outline-none"
                style={{ color: '#333333' }}
                aria-label="Search clarification requests"
              />
            </div>
          </div>
        </div>

        {/* Summary bar */}
        <div
          className="px-6 py-2 text-[11px]"
          style={{ color: '#AAAAAA', borderBottom: '1px solid #F0F0F0' }}
        >
          {loading ? 'Loading…' : `${rows.length} request${rows.length !== 1 ? 's' : ''} shown`}
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr style={{ borderBottom: '1px solid #F0F0F0' }}>
                {['Application', 'Title', 'Sent', 'Responded', 'Status', ''].map((col) => (
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
                    {tab === 'responded'
                      ? 'No institution has responded yet.'
                      : 'No clarification requests in this filter.'}
                  </td>
                </tr>
              ) : (
                rows.map((d) => {
                  const dot = STATUS_DOT_MAP[d.status] ?? { status: 'neutral', label: d.status }
                  const hasResponse = d.status === 'responded'
                  return (
                    <tr
                      key={d.id}
                      className="transition-colors hover:bg-[#FAFAFA]"
                      style={{
                        borderBottom: '1px solid #F0F0F0',
                        background: hasResponse ? '#FFFBF8' : undefined,
                      }}
                    >
                      <td className="px-6 py-4">
                        {d.applicationId ? (
                          <Link
                            to={`/officer/applications/${d.applicationId}?tab=clarifications`}
                            className="mono text-sm font-semibold hover:underline"
                            style={{ color: '#111111' }}
                          >
                            {d.applicationNumber ?? d.applicationId.slice(0, 8)}
                          </Link>
                        ) : (
                          <span className="mono text-sm text-[#888888]">—</span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-sm" style={{ color: '#333333' }}>
                          {d.title}
                        </div>
                        {d.description && (
                          <div
                            className="text-[11px] mt-0.5 line-clamp-1"
                            style={{ color: '#888888' }}
                          >
                            {d.description}
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4 text-[12px]" style={{ color: '#888888' }}>
                        <div>{formatDate(d.createdAt)}</div>
                        <div className="text-[10px]">{formatRelative(d.createdAt)}</div>
                      </td>
                      <td className="px-6 py-4 text-[12px]" style={{ color: '#888888' }}>
                        {d.respondedAt ? (
                          <>
                            <div>{formatDate(d.respondedAt)}</div>
                            <div className="text-[10px]">{formatRelative(d.respondedAt)}</div>
                          </>
                        ) : (
                          <span style={{ color: '#AAAAAA' }}>—</span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <StatusDot status={dot.status} label={dot.label} />
                      </td>
                      <td className="px-6 py-4 text-right">
                        {d.applicationId && (
                          <Link
                            to={`/officer/applications/${d.applicationId}?tab=clarifications`}
                          >
                            <button
                              type="button"
                              className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors"
                              style={{ border: '1px solid #E0E0E0', color: '#333333' }}
                              onMouseEnter={(e) =>
                                (e.currentTarget.style.background = '#F5F5F5')
                              }
                              onMouseLeave={(e) =>
                                (e.currentTarget.style.background = 'transparent')
                              }
                            >
                              <Eye size={12} />
                              {hasResponse ? 'Review response' : 'View'}
                            </button>
                          </Link>
                        )}
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
