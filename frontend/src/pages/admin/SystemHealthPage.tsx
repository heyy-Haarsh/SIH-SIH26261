import { useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { Link } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { HealthBadge, overallLabel } from '@/components/admin/HealthBadge'
import { errorText } from '@/components/scrutiny/scrutinyUi'
import { useRole } from '@/app/RoleContext'
import { useRefreshable } from '@/hooks/useRefreshable'
import { formatDateTime } from '@/lib/format'
import { api } from '@/services/api'
import type { HealthComponent, SystemHealth } from '@/types'

export function SystemHealthPanel({ health }: { health: SystemHealth }) {
  const overall = overallLabel(health.status)
  const a = health.activity
  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <Badge tone={overall.tone}>{overall.label}</Badge>
              <span className="text-xs text-ink-muted">
                {health.environment} · v{health.version} · checked {formatDateTime(health.checkedAt)}
              </span>
            </div>
            {health.warnings.length > 0 && (
              <ul className="mt-3 list-disc space-y-1 pl-4 text-xs text-status-warning">
                {health.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Core services" description="What the platform needs to run" />
          <ComponentList items={health.components} />
        </Card>
        <Card>
          <CardHeader
            title="External sources"
            description="Connections to outside systems"
            action={
              <Link to="/admin/integrations" className="text-xs text-accent underline">
                Manage
              </Link>
            }
          />
          <ComponentList items={health.integrations} />
        </Card>
      </div>

      <Card>
        <CardHeader
          title={`Activity — last ${a.windowHours} hours`}
          description="Counts come straight from the database"
        />
        <dl className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Applications (all time)" value={a.applicationsTotal} />
          <Stat label="Validation runs" value={a.validationRuns} warn={a.validationRunsFailed} warnLabel="failed" />
          <Stat
            label="Extraction runs"
            value={a.extractionRuns}
            warn={a.extractionRunsNeedingAttention}
            warnLabel="need attention"
          />
          <Stat label="Audit events" value={a.auditEvents} />
          <Stat label="Source-unavailable checks" value={a.verificationChecksUnavailable ?? 0} />
          <Stat label="Last validation" value={a.lastValidationAt ? formatDateTime(a.lastValidationAt) : 'none yet'} />
          <Stat label="Last audit event" value={a.lastAuditEventAt ? formatDateTime(a.lastAuditEventAt) : 'none yet'} />
        </dl>
        {Object.keys(a.applicationsByStatus).length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2 border-t border-border pt-3">
            {Object.entries(a.applicationsByStatus).map(([status, n]) => (
              <Badge key={status} tone="neutral">
                {status.replace(/_/g, ' ')}: {n}
              </Badge>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

function ComponentList({ items }: { items: HealthComponent[] }) {
  return (
    <ul className="space-y-2">
      {items.map((c) => (
        <li key={c.id} className="rounded-[var(--radius-md)] border border-border px-3 py-2">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium text-ink">{c.label}</span>
            <HealthBadge health={c.health} />
          </div>
          <p className="mt-0.5 text-xs text-ink-secondary">{c.message}</p>
          {c.limitations.map((l) => (
            <p key={l} className="mt-0.5 text-[11px] text-ink-muted">
              {l}
            </p>
          ))}
        </li>
      ))}
    </ul>
  )
}

function Stat({
  label,
  value,
  warn,
  warnLabel,
}: {
  label: string
  value: number | string
  warn?: number
  warnLabel?: string
}) {
  return (
    <div className="rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2">
      <dt className="text-[11px] uppercase tracking-wide text-ink-muted">{label}</dt>
      <dd className="mt-0.5 text-base font-semibold text-ink">{value}</dd>
      {warn ? (
        <dd className="text-[11px] text-status-warning">
          {warn} {warnLabel}
        </dd>
      ) : null}
    </div>
  )
}

export function SystemHealthPage() {
  const { role } = useRole()
  const { data, loading, error, reload, refreshing } = useRefreshable<SystemHealth>(
    () => api.systemHealth(role),
    role,
  )
  const [msg, setMsg] = useState<string | null>(null)
  const [chainMsg, setChainMsg] = useState<string | null>(null)

  async function refresh() {
    setMsg(null)
    try {
      await reload()
    } catch (err) {
      setMsg(errorText(err, 'Refresh failed'))
    }
  }

  async function verifyChain() {
    setChainMsg('Verifying…')
    try {
      const r = await api.verifyAuditChain(role)
      setChainMsg(
        r.ok
          ? `Audit chain intact — ${r.checked} event(s) verified.`
          : `Audit chain broken at sequence ${r.firstBadSequence}: ${r.detail}`,
      )
    } catch (err) {
      setChainMsg(errorText(err, 'Verification failed'))
    }
  }

  return (
    <AppShell
      title="System health"
      breadcrumbs={['Administrator', 'Health']}
      actions={
        <>
          <Button size="sm" variant="outline" onClick={() => void verifyChain()}>
            Verify audit chain
          </Button>
          <Button
            size="sm"
            leftIcon={<RefreshCw size={14} />}
            disabled={refreshing}
            onClick={() => void refresh()}
          >
            Refresh
          </Button>
        </>
      }
    >
      {chainMsg && (
        <div role="status" className="mb-4 rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2 text-xs">
          {chainMsg}
        </div>
      )}
      {(error || msg) && !data && (
        <p role="alert" className="mb-3 text-sm text-status-failed">
          {msg ?? error}
        </p>
      )}
      {loading && <p className="text-sm text-ink-muted">Checking services…</p>}
      {data && <SystemHealthPanel health={data} />}
    </AppShell>
  )
}
