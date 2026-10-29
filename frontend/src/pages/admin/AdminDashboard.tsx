import { Activity, Plug, Scale, Users, Download, Search, HeartPulse } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { HealthBadge, overallLabel } from '@/components/admin/HealthBadge'
import { Skeleton, SkeletonMetricRow, SkeletonTable } from '@/components/ui/Skeleton'
import { api } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import type { AdminStats, HealthComponent, SystemHealth } from '@/types'

const STATUS_DOT: Record<string, string> = {
  healthy: '#2E7D52',
  warning: '#B45309',
  degraded: '#B91C1C',
  unavailable: '#6B7280',
}

type SystemTab = 'core' | 'integrations'

const SYSTEM_TABS: { key: SystemTab; label: string }[] = [
  { key: 'core', label: 'Core Services' },
  { key: 'integrations', label: 'External Sources' },
]

const QUICK_LINKS = [
  { to: '/admin/delegation', label: 'Delegation' },
  { to: '/admin/users', label: 'Users' },
  { to: '/admin/categories', label: 'Categories' },
  { to: '/admin/rules', label: 'Rules & Validation' },
  { to: '/admin/handbook', label: 'Handbook References' },
  { to: '/admin/integrations', label: 'Integrations' },
  { to: '/admin/health', label: 'System Health' },
  { to: '/admin/audit', label: 'Audit Trail' },
  { to: '/admin/settings', label: 'Settings' },
]

function CompactHealthRow({ item }: { item: HealthComponent }) {
  const dot = STATUS_DOT[item.health] ?? '#888888'
  return (
    <div
      className="flex items-center justify-between gap-4 px-6 py-4 transition-colors hover:bg-[#FAFAFA]"
      style={{ borderBottom: '1px solid #F0F0F0' }}
    >
      <div className="flex items-center gap-2.5">
        <span className="status-dot" style={{ background: dot }} />
        <span className="text-sm" style={{ color: '#333333' }} title={item.message}>
          {item.label}
        </span>
      </div>
      <HealthBadge health={item.health} />
    </div>
  )
}

export function AdminDashboard() {
  const { role } = useRole()
  const [health, setHealth] = useState<SystemHealth | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [statsError, setStatsError] = useState<string | null>(null)
  const [unassigned, setUnassigned] = useState<number | null>(null)
  const [atCap, setAtCap] = useState<number | null>(null)
  const [systemTab, setSystemTab] = useState<SystemTab>('core')
  const [search, setSearch] = useState('')

  useEffect(() => {
    api
      .systemHealth(role)
      .then((h) => { setHealth(h); setHealthError(null) })
      .catch(() => setHealthError('System health is unavailable — sign in as a regional officer with the API running.'))
    api
      .adminStats(role)
      .then((s) => { setStats(s); setStatsError(null) })
      .catch(() => setStatsError('Regional officer statistics unavailable'))
    Promise.all([api.getDelegationQueue(role), api.listOfficersWithLoad(role)])
      .then(([queue, officers]) => {
        setUnassigned(queue.length)
        setAtCap(officers.filter((o) => o.isAtCap).length)
      })
      .catch(() => { setUnassigned(null); setAtCap(null) })
  }, [role])

  const overall = health ? overallLabel(health.status) : null

  const METRIC_CELLS = [
    { label: 'Unassigned', value: unassigned ?? '—', hint: 'Need delegation', icon: Activity },
    { label: 'Officers at Cap', value: atCap ?? '—', hint: 'Queue full', icon: Users },
    { label: 'Managed Users', value: stats?.userCount ?? '—', hint: statsError ? 'Unavailable' : 'Live', icon: Users },
    { label: 'Active Rules', value: stats?.activeRuleCount ?? '—', hint: 'Synthetic + official', icon: Scale },
    { label: 'Live Verification', value: stats?.liveVerificationEnabled ? 'On' : 'Off', hint: 'Server config', icon: Plug },
    { label: 'Audit Events (24h)', value: stats?.auditEvents24h ?? '—', hint: 'Append-only', icon: Activity },
  ]

  // Stage progress data
  const appStats = stats?.applications
  const stageEntries = appStats
    ? Object.entries(appStats.stageLabels).map(([stage, label]) => ({
        label,
        count: appStats.byStage[stage as keyof typeof appStats.byStage] ?? 0,
        total: appStats.total || 1,
      }))
    : []

  const stageColors = ['#1D4ED8', '#E8622A', '#B45309', '#2E7D52', '#6D28D9']

  // Filtered health items
  const healthItems =
    systemTab === 'core' ? (health?.components ?? []) : (health?.integrations ?? [])
  const filteredHealthItems = healthItems.filter(
    (item) =>
      !search ||
      item.label.toLowerCase().includes(search.toLowerCase()),
  )

  return (
    <AppShell
      title="Regional Overview"
      description="System-wide administration · Oversight of applications, officers, and integrations."
      breadcrumbs={['Regional Officer', 'Overview']}
      actions={
        <div className="flex items-center gap-2">
          <Link to="/admin/delegation">
            <button
              type="button"
              className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white transition-colors"
              style={{ background: '#E8622A' }}
              onMouseEnter={(e) => (e.currentTarget.style.background = '#D4541F')}
              onMouseLeave={(e) => (e.currentTarget.style.background = '#E8622A')}
            >
              Manage Delegation
            </button>
          </Link>
          <Link to="/admin/health">
            <button
              type="button"
              className="flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-colors"
              style={{ border: '1px solid #E0E0E0', color: '#333333' }}
              onMouseEnter={(e) => (e.currentTarget.style.background = '#F5F5F5')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <HeartPulse size={14} />
              System Health
            </button>
          </Link>
        </div>
      }
    >
      {/* ── Metrics Row ─────────────────────────────────────────── */}
      {stats === null && !statsError ? (
        <SkeletonMetricRow cells={6} />
      ) : (
        <div
          className="flex flex-wrap overflow-hidden rounded-xl mb-6"
          style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
        >
          {METRIC_CELLS.map((cell) => (
            <div
              key={cell.label}
              className="flex-1 px-6 py-5 metric-divider"
              style={{ minWidth: '140px' }}
            >
              <div
                className="text-[11px] font-medium uppercase tracking-wider mb-1"
                style={{ color: '#999999' }}
              >
                {cell.label}
              </div>
              <div
                className="text-[28px] font-bold leading-none tracking-tight"
                style={{ color: '#111111' }}
              >
                {cell.value}
              </div>
              <div className="mt-1.5 text-[11px]" style={{ color: '#888888' }}>
                {cell.hint}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Applications by Stage ────────────────────────────────── */}
      {!appStats && !statsError ? (
        <div
          className="rounded-xl mb-6 px-6 py-5"
          style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
        >
          <div className="mb-4">
            <Skeleton variant="rounded" className="h-4 w-40 mb-1.5" />
            <Skeleton variant="rounded" className="h-3 w-56" />
          </div>
          <div className="space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4">
                <Skeleton variant="rounded" className="h-3 w-40 shrink-0" />
                <div className="flex-1 flex items-center gap-3">
                  <Skeleton variant="rounded" className="h-2 flex-1 rounded-full" />
                  <Skeleton variant="rounded" className="h-3 w-8" />
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : appStats ? (
        <div
          className="rounded-xl mb-6 px-6 py-5"
          style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
        >
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold" style={{ color: '#111111' }}>
                Applications by Stage
              </h2>
              <p className="text-[11px] mt-0.5" style={{ color: '#888888' }}>
                {appStats.total} total · {appStats.openClarifications} open clarification(s)
              </p>
            </div>
          </div>
          <div className="space-y-3">
            {stageEntries.map((stage, i) => {
              const pct = Math.max(2, Math.round((stage.count / stage.total) * 100))
              return (
                <div key={stage.label} className="flex items-center gap-4">
                  <div className="w-44 shrink-0 text-xs" style={{ color: '#888888' }}>
                    {stage.label}
                  </div>
                  <div className="flex-1 flex items-center gap-3">
                    <div className="flex-1 rounded-full" style={{ background: '#F0F0F0', height: '6px' }}>
                      <div
                        className="rounded-full transition-all duration-500"
                        style={{
                          width: `${pct}%`,
                          background: stageColors[i % stageColors.length],
                          height: '6px',
                        }}
                      />
                    </div>
                    <span className="w-6 text-right text-xs font-semibold" style={{ color: '#333333' }}>
                      {stage.count}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      ) : null}

      {statsError && (
        <div
          className="mb-6 rounded-xl px-4 py-3 text-sm"
          style={{ background: '#FEF3C7', color: '#B45309', border: '1px solid #FDE68A' }}
        >
          {statsError}
        </div>
      )}

      {/* ── Quick Links ──────────────────────────────────────────── */}
      <div
        className="rounded-xl mb-6 px-6 py-5"
        style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
      >
        <h2 className="text-sm font-semibold mb-4" style={{ color: '#111111' }}>
          Quick Navigation
        </h2>
        <div className="flex flex-wrap gap-2">
          {QUICK_LINKS.map(({ to, label }) => (
            <Link key={to} to={to}>
              <button
                type="button"
                className="rounded-lg border px-3.5 py-2 text-[13px] font-medium transition-colors"
                style={{ border: '1px solid #E0E0E0', color: '#333333' }}
                onMouseEnter={(e) => (e.currentTarget.style.background = '#F5F5F5')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              >
                {label}
              </button>
            </Link>
          ))}
        </div>
      </div>

      {/* ── System Health Table ──────────────────────────────────── */}
      {healthError && (
        <div
          className="mb-6 rounded-xl px-4 py-3 text-sm"
          style={{ background: '#FEE2E2', color: '#B91C1C', border: '1px solid #FECACA' }}
        >
          {healthError}
        </div>
      )}

      {health && (
        <>
          {/* Overall status bar */}
          {overall && (
            <div
              className="flex items-center gap-3 rounded-xl mb-6 px-6 py-4"
              style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
            >
              <span
                className="status-dot"
                style={{ background: STATUS_DOT[health.status] ?? '#888888', width: '8px', height: '8px' }}
              />
              <span className="text-sm font-semibold" style={{ color: '#111111' }}>
                {overall.label}
              </span>
              <span className="text-[12px]" style={{ color: '#888888' }}>
                {health.environment} · {health.activity.applicationsTotal} application(s) · {health.activity.auditEvents} audit event(s) in 24h
              </span>
            </div>
          )}

          {/* Warnings */}
          {health.warnings.length > 0 && (
            <div
              className="rounded-xl mb-6 px-6 py-4"
              style={{ background: '#FEF3C7', border: '1px solid #FDE68A' }}
            >
              <ul className="list-disc pl-4 space-y-1">
                {health.warnings.map((w) => (
                  <li key={w} className="text-xs" style={{ color: '#B45309' }}>
                    {w}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Tabbed component list */}
          <div
            className="rounded-xl overflow-hidden"
            style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
          >
            <div
              className="flex items-center justify-between px-6 pt-1"
              style={{ borderBottom: '1px solid #F0F0F0' }}
            >
              <div className="flex items-center">
                {SYSTEM_TABS.map((tab) => (
                  <button
                    key={tab.key}
                    type="button"
                    onClick={() => { setSystemTab(tab.key); setSearch('') }}
                    className={`px-4 py-3.5 text-sm transition-colors ${
                      systemTab === tab.key ? 'tab-active' : 'tab-inactive'
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
                <Link
                  to={systemTab === 'core' ? '/admin/health' : '/admin/integrations'}
                  className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors"
                  style={{ border: '1px solid #E0E0E0', color: '#555555' }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = '#F5F5F5')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  <Download size={13} />
                  {systemTab === 'core' ? 'View Details' : 'Manage'}
                </Link>
              </div>
            </div>

            {/* Table header */}
            <div style={{ borderBottom: '1px solid #F0F0F0' }}>
              <div className="flex items-center justify-between px-6 py-3">
                <span
                  className="text-[11px] font-semibold uppercase tracking-wider"
                  style={{ color: '#AAAAAA' }}
                >
                  Service / Source
                </span>
                <span
                  className="text-[11px] font-semibold uppercase tracking-wider"
                  style={{ color: '#AAAAAA' }}
                >
                  Status
                </span>
              </div>
            </div>

            {filteredHealthItems.length === 0 ? (
              <div className="px-6 py-10 text-center text-sm" style={{ color: '#AAAAAA' }}>
                No items found.
              </div>
            ) : (
              filteredHealthItems.map((item) => <CompactHealthRow key={item.id} item={item} />)
            )}
          </div>
        </>
      )}

      {!health && !healthError && (
        <div
          className="rounded-xl overflow-hidden mt-6"
          style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
        >
          <div className="p-5 border-b border-[#F0F0F0] flex items-center justify-between">
            <Skeleton variant="rounded" className="h-4 w-36" />
            <Skeleton variant="rounded" className="h-6 w-24 rounded-full" />
          </div>
          <SkeletonTable rows={4} cols={2} />
        </div>
      )}
    </AppShell>
  )
}
