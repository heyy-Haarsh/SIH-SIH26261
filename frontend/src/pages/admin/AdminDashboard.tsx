import { Activity, Plug, Scale, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { StatCard } from '@/components/dashboard/StatCard'
import { Card, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { HealthBadge, overallLabel } from '@/components/admin/HealthBadge'
import { api } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import type { AdminStats, HealthComponent, SystemHealth } from '@/types'

function CompactList({ items }: { items: HealthComponent[] }) {
  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li
          key={item.id}
          className="flex items-center justify-between gap-3 rounded-[var(--radius-md)] border border-border px-3 py-2"
        >
          <span className="min-w-0 truncate text-sm text-ink" title={item.message}>
            {item.label}
          </span>
          <HealthBadge health={item.health} />
        </li>
      ))}
    </ul>
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

  useEffect(() => {
    api
      .systemHealth(role)
      .then((h) => {
        setHealth(h)
        setHealthError(null)
      })
      .catch(() =>
        setHealthError(
          'System health is unavailable — sign in as a regional officer with the API running.',
        ),
      )
    api
      .adminStats(role)
      .then((s) => {
        setStats(s)
        setStatsError(null)
      })
      .catch(() => setStatsError('Regional officer statistics unavailable'))
    Promise.all([api.getDelegationQueue(role), api.listOfficersWithLoad(role)])
      .then(([queue, officers]) => {
        setUnassigned(queue.length)
        setAtCap(officers.filter((o) => o.isAtCap).length)
      })
      .catch(() => {
        setUnassigned(null)
        setAtCap(null)
      })
  }, [role])

  const overall = health ? overallLabel(health.status) : null

  return (
    <AppShell title="Regional overview" breadcrumbs={['Regional Officer', 'Overview']}>
      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
        <StatCard
          label="Unassigned"
          value={unassigned ?? '—'}
          hint="Need delegation"
          icon={Activity}
        />
        <StatCard
          label="Officers at cap"
          value={atCap ?? '—'}
          hint="Queue full"
          icon={Users}
        />
        <StatCard
          label="Managed users"
          value={stats?.userCount ?? '—'}
          hint={statsError ? 'Unavailable' : 'Live'}
          icon={Users}
        />
        <StatCard
          label="Active rules"
          value={stats?.activeRuleCount ?? '—'}
          hint="Synthetic + official"
          icon={Scale}
        />
        <StatCard
          label="Live verification"
          value={stats?.liveVerificationEnabled ? 'On' : 'Off'}
          hint="Set in server configuration"
          icon={Plug}
        />
        <StatCard
          label="Audit events (24h)"
          value={stats?.auditEvents24h ?? '—'}
          hint="Append-only"
          icon={Activity}
        />
      </div>

      {stats?.applications && (
        <Card className="mb-5">
          <CardHeader
            title="Applications by stage"
            description="Same counts the Scrutiny Officer dashboard shows — one source for every role."
          />
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
            {Object.entries(stats.applications.stageLabels).map(([stage, label]) => (
              <div key={stage} className="rounded-[var(--radius-md)] border border-border px-3 py-2">
                <div className="text-[11px] uppercase tracking-wide text-ink-muted">{label}</div>
                <div className="text-xl font-semibold text-ink">
                  {stats.applications?.byStage[stage as keyof typeof stats.applications.byStage] ?? 0}
                </div>
              </div>
            ))}
          </div>
          <p className="mt-2 text-xs text-ink-muted">
            {stats.applications.total} applications in total · {stats.applications.openClarifications}{' '}
            open clarification(s) · regional officers oversee workload; scrutiny officers decide applications.
          </p>
        </Card>
      )}

      <div className="mb-5 flex flex-wrap gap-2">
        {[
          ['/admin/delegation', 'Delegation'],
          ['/admin/users', 'Users'],
          ['/admin/categories', 'Categories'],
          ['/admin/rules', 'Rules'],
          ['/admin/handbook', 'Handbook references'],
          ['/admin/integrations', 'Integrations'],
          ['/admin/health', 'System health'],
          ['/admin/audit', 'Audit trail'],
          ['/admin/settings', 'Settings'],
        ].map(([to, label]) => (
          <Link key={to} to={to}>
            <Button size="sm" variant="outline">
              {label}
            </Button>
          </Link>
        ))}
      </div>

      {healthError && (
        <p role="alert" className="mb-4 text-sm text-status-failed">
          {healthError}
        </p>
      )}

      {health && (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-2">
            {overall && <Badge tone={overall.tone}>{overall.label}</Badge>}
            <span className="text-xs text-ink-muted">
              {health.environment} · {health.activity.applicationsTotal} application(s) ·{' '}
              {health.activity.auditEvents} audit event(s) in 24h
            </span>
          </div>
          {health.warnings.length > 0 && (
            <ul className="mb-4 list-disc space-y-1 rounded-[var(--radius-md)] border border-amber-200 bg-status-warning-bg px-6 py-2 text-xs text-status-warning">
              {health.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          )}
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader
                title="Core services"
                action={
                  <Link to="/admin/health" className="text-xs text-accent underline">
                    Details
                  </Link>
                }
              />
              <CompactList items={health.components} />
            </Card>
            <Card>
              <CardHeader
                title="External sources"
                description="Shown as connected only when they truly are"
                action={
                  <Link to="/admin/integrations" className="text-xs text-accent underline">
                    Manage
                  </Link>
                }
              />
              <CompactList items={health.integrations} />
            </Card>
          </div>
        </>
      )}
      {!health && !healthError && <p className="text-sm text-ink-muted">Checking services…</p>}
    </AppShell>
  )
}
