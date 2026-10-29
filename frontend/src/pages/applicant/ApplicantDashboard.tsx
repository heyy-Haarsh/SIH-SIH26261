import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { FilePlus2, FolderOpen, Download, Search } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Notice } from '@/components/ui/Notice'
import { Skeleton, SkeletonMetricRow, SkeletonTable } from '@/components/ui/Skeleton'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import { CARD_HINT, CARD_LABEL, matchesCard, type CardKey } from '@/lib/applicantLifecycle'
import { stagePresentation } from '@/lib/applicantLifecycle'
import { formatDateTime } from '@/lib/format'
import type { ApplicantApplicationSummary, ApplicantOverview } from '@/types'

const CARDS: CardKey[] = ['active', 'action_required', 'under_scrutiny', 'decision_recorded']

const STATUS_COLORS: Record<CardKey, string> = {
  active: '#2E7D52',
  action_required: '#E8622A',
  under_scrutiny: '#1D4ED8',
  decision_recorded: '#6B7280',
}

const STAGE_BARS = [
  { key: 'active' as CardKey, color: '#2D2D2D', width: '65%' },
  { key: 'under_scrutiny' as CardKey, color: '#1D4ED8', width: '45%' },
  { key: 'action_required' as CardKey, color: '#E8622A', width: '25%' },
  { key: 'decision_recorded' as CardKey, color: '#2E7D52', width: '80%' },
]

const TABS: { key: CardKey | null; label: string }[] = [
  { key: null, label: 'All Statuses' },
  { key: 'active', label: 'Active' },
  { key: 'action_required', label: 'Action Required' },
  { key: 'under_scrutiny', label: 'Under Scrutiny' },
  { key: 'decision_recorded', label: 'Decided' },
]

export function ApplicantDashboard() {
  const { user, role } = useRole()
  const [apps, setApps] = useState<ApplicantApplicationSummary[] | null>(null)
  const [overview, setOverview] = useState<ApplicantOverview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [card, setCard] = useState<CardKey | null>(null)
  const [search, setSearch] = useState('')

  function load() {
    setError(null)
    Promise.all([api.listMyApplications(role), api.getApplicantOverview(role)])
      .then(([list, ov]) => {
        setApps(list)
        setOverview(ov)
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : 'Applications could not be loaded.'),
      )
  }

  useEffect(() => {
    if (role === 'applicant') load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role])

  const counts: Record<CardKey, number> = {
    active: overview?.active ?? 0,
    action_required: overview?.actionRequired ?? 0,
    under_scrutiny: overview?.underScrutiny ?? 0,
    decision_recorded: overview?.decisionRecorded ?? 0,
  }

  const total = Object.values(counts).reduce((a, b) => a + b, 0)

  const filtered = (card && apps ? apps.filter((a) => matchesCard(a, card)) : apps ?? []).filter(
    (a) =>
      !search ||
      a.applicationNumber.toLowerCase().includes(search.toLowerCase()) ||
      a.institutionName?.toLowerCase().includes(search.toLowerCase()) ||
      a.category?.toLowerCase().includes(search.toLowerCase()),
  )

  return (
    <AppShell
      title="Applications Overview"
      description={
        user.institutionName
          ? `${user.institutionName} · Institution workspace`
          : 'Status of your applications and what needs attention next.'
      }
      breadcrumbs={['Applicant', 'Overview']}
      actions={
        <Link to="/applicant/applications/new">
          <button
            type="button"
            className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white transition-colors"
            style={{ background: '#E8622A' }}
            onMouseEnter={(e) => (e.currentTarget.style.background = '#D4541F')}
            onMouseLeave={(e) => (e.currentTarget.style.background = '#E8622A')}
          >
            <FilePlus2 size={15} strokeWidth={2} />
            New Application
          </button>
        </Link>
      }
    >
      {error && (
        <Notice tone="error" className="mb-6" title="Could not load overview" onRetry={load}>
          {error}
        </Notice>
      )}

      {/* ── Metrics Row ─────────────────────────────────────────── */}
      {overview === null ? (
        <SkeletonMetricRow cells={4} />
      ) : (
        <div
          className="flex overflow-hidden rounded-xl mb-6"
          style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
        >
          {CARDS.map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => setCard((c) => (c === key ? null : key))}
              aria-pressed={card === key}
              className={`flex-1 px-6 py-5 text-left transition-colors metric-divider ${
                card === key ? 'bg-[#FAFAFA]' : 'bg-white hover:bg-[#FAFAFA]'
              }`}
            >
              <div
                className="text-[11px] font-medium uppercase tracking-wider mb-1"
                style={{ color: '#999999' }}
              >
                {CARD_LABEL[key]}
              </div>
              <div
                className="text-[28px] font-bold leading-none tracking-tight"
                style={{ color: '#111111' }}
              >
                {counts[key]}
              </div>
              <div className="mt-1.5 flex items-center gap-1 text-[11px]" style={{ color: STATUS_COLORS[key] }}>
                <span
                  className="status-dot"
                  style={{ background: STATUS_COLORS[key] }}
                />
                {CARD_HINT[key]}
              </div>
            </button>
          ))}
        </div>
      )}

      {/* ── Pipeline Stage Bars ──────────────────────────────────── */}
      <div
        className="rounded-xl mb-6 px-6 py-5"
        style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
      >
        <h2 className="text-sm font-semibold mb-4" style={{ color: '#111111' }}>
          Application Pipeline
        </h2>
        {overview === null ? (
          <div className="space-y-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4">
                <Skeleton variant="rounded" className="h-3.5 w-32 shrink-0" />
                <div className="flex-1 flex items-center gap-3">
                  <Skeleton variant="rounded" className="h-2 flex-1 rounded-full" />
                  <Skeleton variant="rounded" className="h-3 w-6" />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {STAGE_BARS.map((stage) => {
              const count = counts[stage.key]
              const pct = total > 0 ? Math.max(4, Math.round((count / total) * 100)) : 0
              return (
                <div key={stage.key} className="flex items-center gap-4">
                  <div className="w-36 shrink-0 text-xs" style={{ color: '#888888' }}>
                    {CARD_LABEL[stage.key]}
                  </div>
                  <div className="flex-1 flex items-center gap-3">
                    <div className="flex-1 rounded-full" style={{ background: '#F0F0F0', height: '6px' }}>
                      <div
                        className="rounded-full transition-all duration-500"
                        style={{ width: `${pct}%`, background: stage.color, height: '6px' }}
                      />
                    </div>
                    <span className="w-6 text-right text-xs font-semibold" style={{ color: '#333333' }}>
                      {count}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* ── Action Required Alert ────────────────────────────────── */}
      {overview && overview.nextActions.length > 0 && (
        <div
          className="rounded-xl mb-6 overflow-hidden"
          style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
        >
          <div className="px-6 pt-5 pb-3">
            <h2 className="text-sm font-semibold" style={{ color: '#111111' }}>
              Next Actions Required
            </h2>
            <p className="text-[11px] mt-0.5" style={{ color: '#888888' }}>
              Items only your institution can complete.
            </p>
          </div>
          <div style={{ borderTop: '1px solid #F0F0F0' }}>
            {overview.nextActions.map((item) => (
              <div
                key={`${item.applicationId}:${item.kind}`}
                className="flex flex-wrap items-center justify-between gap-3 px-6 py-3.5"
                style={{ borderBottom: '1px solid #F0F0F0' }}
              >
                <div>
                  <div className="mono text-[11px]" style={{ color: '#888888' }}>
                    {item.applicationNumber}
                  </div>
                  <div className="text-sm font-medium" style={{ color: '#111111' }}>
                    {item.title}
                  </div>
                  <div className="text-[12px]" style={{ color: '#888888' }}>
                    {item.reason}
                  </div>
                </div>
                <Link to={`/applicant/applications/${item.applicationId}`}>
                  <button
                    type="button"
                    className="rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors"
                    style={{ border: '1px solid #E0E0E0', color: '#333333' }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = '#F5F5F5')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                  >
                    Open
                  </button>
                </Link>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Applications Table ───────────────────────────────────── */}
      <div
        className="rounded-xl overflow-hidden"
        style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
      >
        {/* Tab bar + search/export */}
        <div
          className="flex items-center justify-between px-6 pt-1"
          style={{ borderBottom: '1px solid #F0F0F0' }}
        >
          <div className="flex items-center gap-0">
            {TABS.map((tab) => (
              <button
                key={String(tab.key)}
                type="button"
                onClick={() => setCard(tab.key)}
                className={`px-4 py-3.5 text-sm transition-colors ${
                  card === tab.key ? 'tab-active' : 'tab-inactive'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2 py-2">
            <div
              className="flex items-center gap-2 rounded-lg border px-3 py-1.5"
              style={{ border: '1px solid #E0E0E0', background: '#FAFAFA' }}
            >
              <Search size={13} style={{ color: '#AAAAAA' }} />
              <input
                type="text"
                placeholder="Search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-32 bg-transparent text-xs outline-none"
                style={{ color: '#333333' }}
              />
            </div>
            <button
              type="button"
              className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors"
              style={{ border: '1px solid #E0E0E0', color: '#555555' }}
              onMouseEnter={(e) => (e.currentTarget.style.background = '#F5F5F5')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <Download size={13} />
              Export
            </button>
          </div>
        </div>

        {/* Table */}
        {apps === null && !error ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left">
              <thead>
                <tr style={{ borderBottom: '1px solid #F0F0F0' }}>
                  {['Application ID', 'Institution', 'Category', 'Status', 'Last Updated', 'Next Action'].map(
                    (col) => (
                      <th
                        key={col}
                        className="px-6 py-3 text-[11px] font-semibold uppercase tracking-wider"
                        style={{ color: '#AAAAAA' }}
                      >
                        {col}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
            </table>
            <SkeletonTable rows={5} cols={6} />
          </div>
        ) : apps?.length === 0 ? (
          <EmptyState
            icon={FolderOpen}
            title="No applications yet"
            description="Create an application to load its document checklist from the published category configuration."
            action={
              <Link to="/applicant/applications/new">
                <Button size="sm">Create application</Button>
              </Link>
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left">
              <thead>
                <tr style={{ borderBottom: '1px solid #F0F0F0' }}>
                  {['Application ID', 'Institution', 'Category', 'Status', 'Last Updated', 'Next Action'].map(
                    (col) => (
                      <th
                        key={col}
                        className="px-6 py-3 text-[11px] font-semibold uppercase tracking-wider"
                        style={{ color: '#AAAAAA' }}
                      >
                        {col}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-10 text-center text-sm" style={{ color: '#AAAAAA' }}>
                      No applications match this filter.
                    </td>
                  </tr>
                ) : (
                  filtered.map((row) => {
                    const st = stagePresentation(row.stage)
                    const cardKey = CARDS.find((k) => matchesCard(row, k)) ?? 'active'
                    const dotColor = STATUS_COLORS[cardKey] ?? '#888888'
                    return (
                      <tr
                        key={row.id}
                        style={{ borderBottom: '1px solid #F0F0F0', minHeight: '52px' }}
                        className="transition-colors hover:bg-[#FAFAFA]"
                      >
                        <td className="px-6 py-4">
                          <Link
                            to={`/applicant/applications/${row.id}`}
                            className="mono text-sm font-medium hover:underline"
                            style={{ color: '#111111' }}
                          >
                            {row.applicationNumber}
                          </Link>
                        </td>
                        <td className="px-6 py-4 text-sm" style={{ color: '#333333' }}>
                          {row.institutionName}
                        </td>
                        <td className="px-6 py-4 text-sm" style={{ color: '#555555' }}>
                          {row.category}
                        </td>
                        <td className="px-6 py-4">
                          <span className="flex items-center gap-1.5 text-sm" style={{ color: '#333333' }}>
                            <span
                              className="status-dot"
                              style={{ background: dotColor }}
                            />
                            {st.label}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-[12px]" style={{ color: '#888888' }}>
                          {formatDateTime(row.updatedAt ?? row.submittedAt)}
                        </td>
                        <td className="px-6 py-4">
                          {row.openClarifications > 0 ? (
                            <span
                              className="flex items-center gap-1 text-[12px] font-medium"
                              style={{ color: '#E8622A' }}
                            >
                              <span className="status-dot" style={{ background: '#E8622A' }} />
                              {row.openClarifications} to answer
                            </span>
                          ) : (
                            <span className="text-[12px]" style={{ color: '#888888' }}>
                              {row.nextAction?.title ?? st.meaning}
                            </span>
                          )}
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AppShell>
  )
}
