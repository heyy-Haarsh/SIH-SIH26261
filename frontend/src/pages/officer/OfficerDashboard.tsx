/**
 * OfficerDashboard — Evidence-first command center for scrutiny officers.
 *
 * Data sources:
 * - /applications (assigned to me)
 * - /applications/metrics
 * - Derives "My Next Actions" from actual application states — no hardcoded tasks.
 */
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  CheckCircle2,
  Clock,
  FileSearch,
  MessageSquare,
  RefreshCw,
  AlertTriangle,
  TriangleAlert,
  ListChecks,
} from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { SkeletonCard, SkeletonMetricRow } from '@/components/ui/Skeleton'
import { StatusDot } from '@/components/ui/StatusDot'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import { formatDate, formatRelative } from '@/lib/format'
import type { ApplicationMetrics, ApplicationSummary } from '@/types'

// ── Task derivation ──────────────────────────────────────────────────────────

type TaskReason = 'new_submission' | 'clarification_response' | 'in_progress' | 'ready_to_complete'

interface NextAction {
  app: ApplicationSummary
  reason: TaskReason
  reasonLabel: string
  urgency: 'high' | 'normal' | 'low'
  link: string
}

function reasonLabel(r: TaskReason): string {
  return {
    new_submission: 'New submission — start scrutiny',
    clarification_response: 'Clarification response received',
    in_progress: 'Under scrutiny — active review',
    ready_to_complete: 'All checks resolved — record recommendation',
  }[r]
}

function deriveActions(apps: ApplicationSummary[]): NextAction[] {
  const actions: NextAction[] = []

  for (const app of apps) {
    if (
      app.status === 'submitted' ||
      app.status === 'processing' ||
      app.stage === 'awaiting_scrutiny'
    ) {
      actions.push({
        app,
        reason: 'new_submission',
        reasonLabel: reasonLabel('new_submission'),
        urgency: 'high',
        link: `/officer/applications/${app.id}`,
      })
    } else if (app.status === 'resubmitted') {
      actions.push({
        app,
        reason: 'clarification_response',
        reasonLabel: reasonLabel('clarification_response'),
        urgency: 'high',
        link: `/officer/applications/${app.id}?tab=clarifications`,
      })
    } else if (
      app.status === 'under_scrutiny' ||
      app.stage === 'under_scrutiny'
    ) {
      // If no open findings → ready to complete
      const reason: TaskReason =
        app.findingCount === 0 ? 'ready_to_complete' : 'in_progress'
      actions.push({
        app,
        reason,
        reasonLabel: reasonLabel(reason),
        urgency: reason === 'ready_to_complete' ? 'normal' : 'low',
        link: `/officer/applications/${app.id}`,
      })
    }
  }

  // Sort: high urgency first, then by priority score descending
  return actions.sort((a, b) => {
    const urgencyOrder = { high: 0, normal: 1, low: 2 }
    const ud = urgencyOrder[a.urgency] - urgencyOrder[b.urgency]
    if (ud !== 0) return ud
    return (b.app.priorityScore ?? 0) - (a.app.priorityScore ?? 0)
  })
}

// ── Metric Cell ──────────────────────────────────────────────────────────────

function MetricCell({
  label,
  value,
  hint,
  linkTo,
}: {
  label: string
  value: number
  hint: string
  linkTo?: string
}) {
  const inner = (
    <div className="px-6 py-5 metric-divider cursor-default">
      <div className="text-[11px] font-semibold uppercase tracking-widest mb-2" style={{ color: '#AAAAAA' }}>
        {label}
      </div>
      <div className="text-3xl font-bold tabular-nums" style={{ color: '#111111' }}>
        {value}
      </div>
      <div className="text-[11px] mt-1.5" style={{ color: '#888888' }}>
        {hint}
      </div>
    </div>
  )
  if (linkTo) {
    return (
      <Link to={linkTo} className="flex-1 hover:bg-[#FAFAFA] transition-colors">
        {inner}
      </Link>
    )
  }
  return <div className="flex-1">{inner}</div>
}

// ── Task Card ────────────────────────────────────────────────────────────────

const URGENCY_DOT: Record<string, string> = {
  high: '#E8622A',
  normal: '#1D4ED8',
  low: '#888888',
}

const REASON_ICON = {
  new_submission: FileSearch,
  clarification_response: MessageSquare,
  in_progress: ListChecks,
  ready_to_complete: CheckCircle2,
}

function TaskCard({ action }: { action: NextAction }) {
  const Icon = REASON_ICON[action.reason]
  return (
    <Link
      to={action.link}
      className="flex items-start gap-4 px-5 py-4 transition-colors hover:bg-[#FAFAFA] group"
      style={{ borderBottom: '1px solid #F0F0F0' }}
    >
      <div
        className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
        style={{ background: '#F5F5F5' }}
      >
        <Icon size={15} style={{ color: URGENCY_DOT[action.urgency] }} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-3">
          <span className="mono text-sm font-semibold" style={{ color: '#111111' }}>
            {action.app.applicationNumber}
          </span>
          <span className="text-[11px] shrink-0" style={{ color: '#888888' }}>
            {formatRelative(action.app.submittedAt)}
          </span>
        </div>
        <div className="text-[12px] mt-0.5 truncate" style={{ color: '#555555' }}>
          {action.app.institutionName}
          {action.app.category ? ` · ${action.app.category}` : ''}
        </div>
        <div className="flex items-center gap-2 mt-1.5">
          <span
            aria-hidden="true"
            style={{
              display: 'inline-block',
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              background: URGENCY_DOT[action.urgency],
              flexShrink: 0,
            }}
          />
          <span className="text-[11px]" style={{ color: '#555555' }}>
            {action.reasonLabel}
          </span>
          {action.app.findingCount > 0 && (
            <span
              className="rounded-md px-1.5 py-0.5 text-[10px] font-medium"
              style={{ background: '#FEF2F2', color: '#B91C1C' }}
            >
              {action.app.findingCount} open finding{action.app.findingCount !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      </div>
      <ArrowRight
        size={14}
        className="mt-1 shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
        style={{ color: '#888888' }}
      />
    </Link>
  )
}

// ── Main Dashboard ───────────────────────────────────────────────────────────

export function OfficerDashboard() {
  const { role } = useRole()
  const [apps, setApps] = useState<ApplicationSummary[]>([])
  const [metrics, setMetrics] = useState<ApplicationMetrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date())

  function load() {
    setLoading(true)
    setError(null)
    Promise.all([api.listApplications(role), api.applicationMetrics(role)])
      .then(([list, m]) => {
        setApps(list)
        setMetrics(m)
        setLastRefreshed(new Date())
      })
      .catch((err) =>
        setError(
          err instanceof ApiError
            ? err.message
            : 'Backend unreachable — start the API on port 8000.',
        ),
      )
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [role]) // eslint-disable-line react-hooks/exhaustive-deps

  const queue = useMemo(
    () => apps.filter((a) => a.stage === 'awaiting_scrutiny' || a.stage === 'under_scrutiny'),
    [apps],
  )
  const actions = useMemo(() => deriveActions(queue), [queue])
  const recentApps = useMemo(
    () =>
      [...queue]
        .sort(
          (a, b) =>
            new Date(b.submittedAt ?? 0).getTime() - new Date(a.submittedAt ?? 0).getTime(),
        )
        .slice(0, 6),
    [queue],
  )

  const by = metrics?.byStage ?? {}
  const metricCells = [
    {
      label: 'Assigned to Me',
      value: metrics?.inOfficerQueue ?? queue.length,
      hint: 'Total in my queue',
      linkTo: '/officer/queue',
    },
    {
      label: 'Awaiting Start',
      value: by.awaiting_scrutiny ?? 0,
      hint: 'New submissions',
      linkTo: '/officer/queue',
    },
    {
      label: 'Clarification Responses',
      value: metrics?.openClarifications ?? 0,
      hint: 'Awaiting officer review',
      linkTo: '/officer/clarifications',
    },
    {
      label: 'Under Scrutiny',
      value: by.under_scrutiny ?? 0,
      hint: 'Active review',
      linkTo: '/officer/queue',
    },
  ]

  const now = new Date()
  const hour = now.getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'

  return (
    <AppShell
      title="Overview"
      breadcrumbs={['Scrutiny Officer', 'Overview']}
      actions={
        <button
          type="button"
          onClick={load}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-40"
          style={{ border: '1px solid #E0E0E0', color: '#555555' }}
          onMouseEnter={(e) => (e.currentTarget.style.background = '#F5F5F5')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          aria-label="Refresh dashboard"
        >
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      }
    >
      {/* Greeting */}
      <div className="mb-5">
        <h2 className="text-xl font-semibold" style={{ color: '#111111' }}>
          {greeting}
        </h2>
        <p className="text-sm mt-0.5" style={{ color: '#888888' }}>
          {loading
            ? 'Loading your workload…'
            : `${apps.length} application${apps.length !== 1 ? 's' : ''} assigned · ${actions.length} action${actions.length !== 1 ? 's' : ''} pending`}
          {lastRefreshed && (
            <span className="ml-2 text-[11px]">
              · Refreshed {formatRelative(lastRefreshed.toISOString())}
            </span>
          )}
        </p>
      </div>

      {error && (
        <div
          className="mb-5 rounded-xl px-4 py-3 text-sm"
          style={{ background: '#FEF3C7', color: '#B45309', border: '1px solid #FDE68A' }}
        >
          <strong>Could not load workload:</strong> {error}
        </div>
      )}

      {/* ── Metric row ───────────────────────────────── */}
      {loading ? (
        <SkeletonMetricRow cells={4} />
      ) : (
        <div
          className="flex overflow-hidden rounded-xl mb-6"
          style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
        >
          {metricCells.map((c) => (
            <MetricCell key={c.label} {...c} />
          ))}
        </div>
      )}

      {/* ── Two-column: Next Actions + Recent Activity ── */}
      <div className="grid gap-5 lg:grid-cols-[1fr_340px]">
        {/* Left: My Next Actions */}
        <div
          className="rounded-xl overflow-hidden"
          style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
        >
          <div
            className="flex items-center justify-between px-5 py-4"
            style={{ borderBottom: '1px solid #F0F0F0' }}
          >
            <div>
              <div className="text-sm font-semibold" style={{ color: '#111111' }}>
                My Next Actions
              </div>
              <div className="text-[11px] mt-0.5" style={{ color: '#888888' }}>
                {loading ? 'Loading…' : `${actions.length} task${actions.length !== 1 ? 's' : ''} need attention`}
              </div>
            </div>
            <Link
              to="/officer/queue"
              className="text-xs font-medium transition-colors hover:underline"
              style={{ color: '#E8622A' }}
            >
              View full queue →
            </Link>
          </div>

          {loading ? (
            <div className="px-5 py-4 space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="animate-pulse flex gap-3">
                  <div className="h-8 w-8 rounded-lg bg-[#F0F0F0] shrink-0" />
                  <div className="flex-1 space-y-2">
                    <div className="h-3 w-32 rounded-full bg-[#F0F0F0]" />
                    <div className="h-2.5 w-48 rounded-full bg-[#F0F0F0]" />
                    <div className="h-2.5 w-40 rounded-full bg-[#F0F0F0]" />
                  </div>
                </div>
              ))}
            </div>
          ) : actions.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 px-5 text-center">
              <CheckCircle2 size={32} className="mb-3" style={{ color: '#D4FAE6' }} />
              <div className="text-sm font-medium" style={{ color: '#111111' }}>
                All caught up!
              </div>
              <div className="text-[12px] mt-1" style={{ color: '#888888' }}>
                No pending actions. Check back when new applications are assigned.
              </div>
            </div>
          ) : (
            <div>
              {actions.slice(0, 8).map((action) => (
                <TaskCard key={action.app.id} action={action} />
              ))}
              {actions.length > 8 && (
                <div className="px-5 py-3 text-center">
                  <Link
                    to="/officer/queue"
                    className="text-sm font-medium"
                    style={{ color: '#E8622A' }}
                  >
                    + {actions.length - 8} more in queue →
                  </Link>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right: Workload summary + Recent activity */}
        <div className="space-y-4">
          {/* Workload stage breakdown */}
          <div
            className="rounded-xl px-5 py-4"
            style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
          >
            <div className="text-sm font-semibold mb-4" style={{ color: '#111111' }}>
              Workload by Stage
            </div>
            {loading ? (
              <div className="space-y-3 animate-pulse">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i}>
                    <div className="flex justify-between mb-1">
                      <div className="h-2.5 w-24 rounded-full bg-[#F0F0F0]" />
                      <div className="h-2.5 w-6 rounded-full bg-[#F0F0F0]" />
                    </div>
                    <div className="h-1.5 w-full rounded-full bg-[#F0F0F0]" />
                  </div>
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                {[
                  { key: 'awaiting_scrutiny', label: 'Awaiting Start', color: '#1D4ED8' },
                  { key: 'under_scrutiny', label: 'Under Scrutiny', color: '#E8622A' },
                  { key: 'awaiting_applicant', label: 'Waiting on applicant', color: '#B45309' },
                  { key: 'decided', label: 'Decided', color: '#2E7D52' },
                ].map(({ key, label, color }) => {
                  const count = (by as Record<string, number>)[key] ?? 0
                  const pct = apps.length > 0 ? (count / apps.length) * 100 : 0
                  return (
                    <div key={key}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[12px]" style={{ color: '#555555' }}>{label}</span>
                        <span className="text-[12px] font-semibold tabular-nums" style={{ color: '#111111' }}>{count}</span>
                      </div>
                      <div className="h-1.5 w-full rounded-full" style={{ background: '#F0F0F0' }}>
                        <div
                          className="h-1.5 rounded-full transition-all"
                          style={{ width: `${Math.min(pct, 100)}%`, background: color }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Recent activity */}
          <div
            className="rounded-xl overflow-hidden"
            style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
          >
            <div className="px-5 py-4" style={{ borderBottom: '1px solid #F0F0F0' }}>
              <div className="text-sm font-semibold" style={{ color: '#111111' }}>
                Recent Activity
              </div>
              <div className="text-[11px] mt-0.5" style={{ color: '#888888' }}>
                Latest applications in your queue
              </div>
            </div>
            {loading ? (
              <div className="divide-y divide-[#F0F0F0]">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="animate-pulse px-5 py-3 flex items-center gap-3">
                    <div className="h-3 w-24 rounded-full bg-[#F0F0F0]" />
                    <div className="h-2.5 w-16 rounded-full bg-[#F0F0F0] ml-auto" />
                  </div>
                ))}
              </div>
            ) : recentApps.length === 0 ? (
              <div className="px-5 py-8 text-center text-sm" style={{ color: '#AAAAAA' }}>
                No applications assigned yet.
              </div>
            ) : (
              <ul>
                {recentApps.map((app) => (
                  <li key={app.id} style={{ borderBottom: '1px solid #F0F0F0' }}>
                    <Link
                      to={`/officer/applications/${app.id}`}
                      className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-[#FAFAFA]"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="mono text-[12px] font-semibold truncate" style={{ color: '#111111' }}>
                            {app.applicationNumber}
                          </span>
                          <StatusDot
                            status={app.stage ?? app.status}
                            label={app.stageLabel ?? app.status?.replace(/_/g, ' ')}
                          />
                        </div>
                        <div className="text-[11px] truncate mt-0.5" style={{ color: '#888888' }}>
                          {app.institutionName}
                        </div>
                      </div>
                      <span className="text-[10px] shrink-0" style={{ color: '#AAAAAA' }}>
                        {formatRelative(app.submittedAt)}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  )
}
