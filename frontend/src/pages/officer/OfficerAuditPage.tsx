/**
 * OfficerAuditPage — read-only audit trail view for scrutiny officers.
 * Shows audit events scoped to the officer's own activity and their applications.
 * Uses the same GET /admin/audit endpoint (officer role is authorized).
 */
import { useCallback, useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import { formatDate, formatRelative } from '@/lib/format'
import type { AdminAuditPage } from '@/types'

const PAGE = 20

export function OfficerAuditPage() {
  const { role } = useRole()
  const [page, setPage] = useState<AdminAuditPage | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [offset, setOffset] = useState(0)
  const [query, setQuery] = useState('')
  const [draftQ, setDraftQ] = useState('')

  const load = useCallback(
    (q: string, off: number) => {
      setLoading(true)
      api
        .searchAudit(role, { q: q || undefined, limit: PAGE, offset: off })
        .then((data) => { setPage(data); setError(null) })
        .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load audit trail.'))
        .finally(() => setLoading(false))
    },
    [role],
  )

  useEffect(() => { load(query, 0); setOffset(0) }, [role]) // eslint-disable-line react-hooks/exhaustive-deps

  function applySearch(e: React.FormEvent) {
    e.preventDefault()
    setQuery(draftQ)
    setOffset(0)
    load(draftQ, 0)
  }

  const items = page?.items ?? []
  const total = page?.total ?? 0
  const from = total === 0 ? 0 : offset + 1
  const to = Math.min(offset + PAGE, total)

  return (
    <AppShell
      title="Audit Trail"
      description="A chronological record of review actions on your assigned applications."
      breadcrumbs={['Scrutiny Officer', 'Audit Trail']}
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
        {/* Search bar */}
        <form
          onSubmit={applySearch}
          className="flex items-center gap-3 px-5 py-4"
          style={{ borderBottom: '1px solid #F0F0F0' }}
        >
          <div
            className="flex flex-1 items-center gap-2 rounded-lg border px-3 py-2"
            style={{ border: '1px solid #E0E0E0', background: '#FAFAFA' }}
          >
            <Search size={13} style={{ color: '#AAAAAA' }} />
            <input
              type="text"
              placeholder="Search by application number, action, or actor…"
              value={draftQ}
              onChange={(e) => setDraftQ(e.target.value)}
              className="flex-1 bg-transparent text-xs outline-none"
              style={{ color: '#333333' }}
              aria-label="Search audit trail"
            />
          </div>
          <button
            type="submit"
            className="rounded-lg px-4 py-2 text-xs font-semibold text-white transition-colors"
            style={{ background: '#E8622A' }}
          >
            Search
          </button>
          {query && (
            <button
              type="button"
              className="text-xs"
              style={{ color: '#888888' }}
              onClick={() => {
                setDraftQ('')
                setQuery('')
                setOffset(0)
                load('', 0)
              }}
            >
              Clear
            </button>
          )}
        </form>

        <div
          className="px-6 py-2 text-[11px]"
          style={{ color: '#AAAAAA', borderBottom: '1px solid #F0F0F0' }}
        >
          {loading ? 'Loading…' : `${from}–${to} of ${total} events`}
        </div>

        <ul>
          {loading ? (
            <SkeletonTable rows={6} cols={4} />
          ) : items.length === 0 ? (
            <li className="px-6 py-12 text-center text-sm" style={{ color: '#AAAAAA' }}>
              No audit events found.
            </li>
          ) : (
            items.map((ev) => (
              <li key={ev.id} style={{ borderBottom: '1px solid #F0F0F0' }}>
                <div className="px-6 py-4 hover:bg-[#FAFAFA] transition-colors">
                  <div className="flex flex-wrap items-start gap-2 justify-between">
                    <div>
                      <span className="text-sm font-medium" style={{ color: '#111111' }}>
                        {ev.label ?? ev.action}
                      </span>
                      {ev.category && (
                        <span
                          className="ml-2 rounded-md border px-2 py-0.5 text-[10px]"
                          style={{ border: '1px solid #E0E0E0', color: '#555555' }}
                        >
                          {ev.category}
                        </span>
                      )}
                    </div>
                    <span className="text-[11px]" style={{ color: '#AAAAAA' }}>
                      {formatRelative(ev.timestamp)} · {formatDate(ev.timestamp)}
                    </span>
                  </div>
                  <div className="text-[12px] mt-1" style={{ color: '#555555' }}>
                    {ev.detail}
                  </div>
                  <div className="text-[11px] mt-0.5" style={{ color: '#AAAAAA' }}>
                    {ev.actor}
                    {ev.actorRole ? ` (${ev.actorRole})` : ''}
                    {ev.applicationNumber ? ` · ${ev.applicationNumber}` : ''}
                  </div>
                </div>
              </li>
            ))
          )}
        </ul>

        {/* Pagination */}
        <div
          className="flex items-center justify-between px-6 py-4"
          style={{ borderTop: '1px solid #F0F0F0' }}
        >
          <button
            type="button"
            disabled={offset <= 0 || loading}
            onClick={() => {
              const newOff = Math.max(0, offset - PAGE)
              setOffset(newOff)
              load(query, newOff)
            }}
            className="rounded-lg border px-3 py-1.5 text-xs font-medium disabled:opacity-40 transition-colors"
            style={{ border: '1px solid #E0E0E0', color: '#333333' }}
            onMouseEnter={(e) => !e.currentTarget.disabled && (e.currentTarget.style.background = '#F5F5F5')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            Previous
          </button>
          <span className="text-xs" style={{ color: '#888888' }}>
            {from}–{to} of {total}
          </span>
          <button
            type="button"
            disabled={offset + PAGE >= total || loading}
            onClick={() => {
              const newOff = offset + PAGE
              setOffset(newOff)
              load(query, newOff)
            }}
            className="rounded-lg border px-3 py-1.5 text-xs font-medium disabled:opacity-40 transition-colors"
            style={{ border: '1px solid #E0E0E0', color: '#333333' }}
            onMouseEnter={(e) => !e.currentTarget.disabled && (e.currentTarget.style.background = '#F5F5F5')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            Next
          </button>
        </div>
      </div>
    </AppShell>
  )
}
