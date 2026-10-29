import { useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { Link } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { SkeletonCard, SkeletonTable } from '@/components/ui/Skeleton'
import { HealthBadge, overallLabel } from '@/components/admin/HealthBadge'
import { errorText } from '@/components/scrutiny/scrutinyUi'
import { useRole } from '@/app/RoleContext'
import { useRefreshable } from '@/hooks/useRefreshable'
import { formatDateTime } from '@/lib/format'
import { api } from '@/services/api'
import type { HealthComponent, ProcessingJob, ProcessingJobList, SystemHealth } from '@/types'

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

const OUTCOME_LABEL: Record<ProcessingJob['outcome'], string> = {
  ok: 'Completed',
  active: 'In progress',
  failed: 'Failed',
  needs_attention: 'Needs attention',
}
const OUTCOME_TONE: Record<ProcessingJob['outcome'], 'pass' | 'info' | 'failed' | 'warning'> = {
  ok: 'pass',
  active: 'info',
  failed: 'failed',
  needs_attention: 'warning',
}

/** Recent validation and extraction runs, read from the run records themselves. */
export function ProcessingJobs({ role }: { role: string }) {
  const [outcome, setOutcome] = useState('')
  const { data, loading, error } = useRefreshable<ProcessingJobList>(
    () => api.listProcessingJobs(role, outcome ? { outcome } : undefined),
    `${role}:${outcome}`,
  )
  return (
    <Card className="mt-4">
      <CardHeader
        title="Processing jobs"
        description={data?.message ?? 'Recent validation and extraction runs'}
        action={
          <select
            aria-label="Filter jobs by outcome"
            value={outcome}
            onChange={(e) => setOutcome(e.target.value)}
            className="rounded border border-border bg-white px-2 py-1 text-xs"
          >
            <option value="">All outcomes</option>
            {Object.entries(OUTCOME_LABEL).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        }
      />
      {error && !data && (
        <p role="alert" className="text-xs text-status-failed">
          {error}
        </p>
      )}
      {loading && !data && (
        <div className="py-2">
          <SkeletonTable rows={4} cols={6} />
        </div>
      )}
      {data && data.items.length === 0 && (
        <p className="text-xs text-ink-muted">No runs match this filter.</p>
      )}
      {data && data.items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-[11px] uppercase tracking-wide text-ink-muted">
              <tr>
                <th className="py-1 pr-3">Run</th>
                <th className="py-1 pr-3">Application</th>
                <th className="py-1 pr-3">Result</th>
                <th className="py-1 pr-3">Started</th>
                <th className="py-1 pr-3">Took</th>
                <th className="py-1">Error</th>
              </tr>
            </thead>
            <tbody>
              {data.items.slice(0, 25).map((j) => (
                <tr key={j.id} className="border-t border-border align-top">
                  <td className="py-1.5 pr-3 capitalize">{j.kind}</td>
                  <td className="py-1.5 pr-3">
                    <Link to={`/officer/applications/${j.applicationId}`} className="text-accent underline">
                      {j.applicationNumber ?? j.applicationId.slice(0, 8)}
                    </Link>
                  </td>
                  <td className="py-1.5 pr-3">
                    <Badge tone={OUTCOME_TONE[j.outcome]}>{OUTCOME_LABEL[j.outcome]}</Badge>
                    <span className="ml-1 text-ink-muted">{j.status.replace(/_/g, ' ')}</span>
                  </td>
                  <td className="py-1.5 pr-3">{formatDateTime(j.startedAt ?? j.createdAt)}</td>
                  <td className="py-1.5 pr-3">
                    {typeof j.durationSeconds === 'number' ? `${j.durationSeconds}s` : '—'}
                  </td>
                  <td className="py-1.5 text-status-failed">{j.error ?? ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
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
      breadcrumbs={['Regional Officer', 'Health']}
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
      {loading && !data && (
        <div className="grid gap-4 md:grid-cols-2 mb-6">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} lines={3} />
          ))}
        </div>
      )}
      {data && <SystemHealthPanel health={data} />}
      <ProcessingJobs role={role} />
    </AppShell>
  )
}
