import { Activity, HeartPulse, Plug, Scale, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { StatCard } from '@/components/dashboard/StatCard'
import { Card, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { api } from '@/services/api'
import type { ApiHealth } from '@/types'

export function AdminDashboard() {
  const [health, setHealth] = useState<ApiHealth | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setHealthError('Backend health endpoint unreachable'))
  }, [])

  return (
    <AppShell title="System Overview" breadcrumbs={['Administrator', 'Overview']}>
      <DemoBanner>
        Administrator workspace. Integration tiles reflect configuration state — no live AICTE or
        government connectors are implied unless explicitly configured.
      </DemoBanner>

      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Managed users" value={12} hint="Demo count" icon={Users} />
        <StatCard label="Active rule versions" value={4} hint="Synthetic rules" icon={Scale} />
        <StatCard label="Integrations configured" value={0} hint="Live connectors" icon={Plug} />
        <StatCard label="Open audit events (24h)" value={36} hint="Demo" icon={Activity} />
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
              { name: 'Redis / Celery workers', status: 'Not configured — sync local runner', tone: 'neutral' as const },
              { name: 'AICTE institutional API', status: 'No authorized access configured', tone: 'warning' as const },
              { name: 'Issuing-authority verification', status: 'Mock adapter only', tone: 'info' as const },
              { name: 'LLM extraction service', status: 'Disabled — no API key', tone: 'neutral' as const },
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
    <div className="flex items-center justify-between border-b border-border pb-2 last:border-0">
      <dt className="text-ink-muted">{label}</dt>
      <dd className="flex items-center gap-2 font-medium text-ink">
        {value}
        {typeof ok === 'boolean' && (
          <Badge tone={ok ? 'pass' : 'warning'}>{ok ? 'OK' : 'Review'}</Badge>
        )}
      </dd>
    </div>
  )
}
