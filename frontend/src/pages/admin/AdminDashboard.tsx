import { Activity, HeartPulse, Plug, Scale, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { StatCard } from '@/components/dashboard/StatCard'
import { Card, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { api } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import type { AdminStats, ApiHealth } from '@/types'

export function AdminDashboard() {
  const { role } = useRole()
  const [health, setHealth] = useState<ApiHealth | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [statsError, setStatsError] = useState<string | null>(null)

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setHealthError('Backend health endpoint unreachable'))
    api
      .adminStats(role)
      .then(setStats)
      .catch(() => setStatsError('Admin stats unavailable — sign in as admin with API running'))
  }, [role])

  return (
    <AppShell title="System Overview" breadcrumbs={['Administrator', 'Overview']}>
      <DemoBanner>
        Administrator workspace. Integration tiles reflect configuration state — no live AICTE or
        government connectors are implied unless explicitly configured.
      </DemoBanner>

      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Managed users"
          value={stats?.userCount ?? '—'}
          hint={statsError ? 'API offline' : 'Live'}
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
          hint="Safe default: off"
          icon={Plug}
        />
        <StatCard
          label="Audit events (24h)"
          value={stats?.auditEvents24h ?? '—'}
          hint="Append-only"
          icon={Activity}
        />
      </div>

      <div className="mb-5 flex flex-wrap gap-2">
        <Link to="/admin/users">
          <Button size="sm" variant="outline">
            Users
          </Button>
        </Link>
        <Link to="/admin/categories">
          <Button size="sm" variant="outline">
            Categories
          </Button>
        </Link>
        <Link to="/admin/rules">
          <Button size="sm" variant="outline">
            Rules
          </Button>
        </Link>
        <Link to="/admin/audit">
          <Button size="sm" variant="outline">
            Audit
          </Button>
        </Link>
        <Link to="/admin/settings">
          <Button size="sm" variant="outline">
            Settings
          </Button>
        </Link>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="System health" description="Live probe when API is running" />
          {health ? (
            <dl className="space-y-2 text-sm">
              <HealthRow label="Status" value={health.status} ok={health.status === 'ok'} />
              <HealthRow label="Environment" value={health.environment} />
              <HealthRow label="Database" value={health.database} />
              <HealthRow label="Storage backend" value={health.storageBackend} />
              <HealthRow
                label="Demo auth"
                value={health.demoAuth ? 'Enabled (dev only)' : 'Disabled'}
                ok={!health.demoAuth}
              />
            </dl>
          ) : (
            <div className="flex items-center gap-2 text-sm text-ink-muted">
              <HeartPulse size={16} />
              {healthError ?? 'Checking…'}
            </div>
          )}
        </Card>

        <Card>
          <CardHeader title="Integration status" description="Truthful connector states" />
          <ul className="space-y-2">
            {[
              { name: 'Local filesystem storage', status: 'Active (dev adapter)', tone: 'pass' as const },
              { name: 'MinIO object storage', status: 'Not configured', tone: 'neutral' as const },
              {
                name: 'Redis / Celery workers',
                status: 'Not configured — sync local runner',
                tone: 'neutral' as const,
              },
              {
                name: 'AICTE institutional API',
                status: 'No authorized access configured',
                tone: 'warning' as const,
              },
              {
                name: 'Issuing-authority verification',
                status: stats?.liveVerificationEnabled
                  ? 'Flag enabled — connector still requires credentials'
                  : 'Mock adapter only',
                tone: 'info' as const,
              },
              {
                name: 'LLM extraction service',
                status: 'Disabled — no API key',
                tone: 'neutral' as const,
              },
            ].map((item) => (
              <li
                key={item.name}
                className="flex items-center justify-between gap-3 rounded-[var(--radius-md)] border border-border px-3 py-2.5"
              >
                <span className="text-sm text-ink">{item.name}</span>
                <Badge tone={item.tone}>{item.status}</Badge>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </AppShell>
  )
}

function HealthRow({
  label,
  value,
  ok,
}: {
  label: string
  value: string
  ok?: boolean
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border pb-2 last:border-0">
      <dt className="text-ink-muted">{label}</dt>
      <dd className={ok === false ? 'font-medium text-amber-700' : 'font-medium text-ink'}>{value}</dd>
    </div>
  )
}
