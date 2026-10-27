import { useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { HealthBadge } from '@/components/admin/HealthBadge'
import { errorText } from '@/components/scrutiny/scrutinyUi'
import { useRole } from '@/app/RoleContext'
import { useRefreshable } from '@/hooks/useRefreshable'
import { formatDateTime } from '@/lib/format'
import { api } from '@/services/api'
import type { Integration, IntegrationList } from '@/types'

const CATEGORY_LABEL: Record<string, string> = {
  infrastructure: 'Infrastructure',
  document_processing: 'Document processing',
  ai: 'AI assistance',
  verification: 'Verification sources',
}
const CATEGORY_ORDER = ['infrastructure', 'document_processing', 'ai', 'verification']

function detailsText(details: Record<string, unknown>): string[] {
  return Object.entries(details)
    .filter(([, v]) => v !== null && v !== undefined && v !== '')
    .map(([k, v]) => {
      const label = k.replace(/([A-Z])/g, ' $1').toLowerCase()
      const value = Array.isArray(v) ? v.join(', ') || 'none' : typeof v === 'boolean' ? (v ? 'yes' : 'no') : String(v)
      return `${label}: ${value}`
    })
}

export function IntegrationsPage() {
  const { role } = useRole()
  const { data, loading, error, reload } = useRefreshable<IntegrationList>(
    () => api.listIntegrations(role),
    role,
  )
  const [busy, setBusy] = useState<string | null>(null)
  const [reasons, setReasons] = useState<Record<string, string>>({})
  const [message, setMessage] = useState<string | null>(null)
  const [openId, setOpenId] = useState<string | null>(null)

  async function toggle(item: Integration, enable: boolean) {
    const reason = (reasons[item.id] ?? '').trim()
    if (reason.length < 3) {
      setMessage(`Enter a reason (at least 3 characters) before changing ${item.label}.`)
      return
    }
    setBusy(item.id)
    setMessage(null)
    try {
      await api.setIntegrationEnabled(role, item.id, enable, reason)
      setReasons((r) => ({ ...r, [item.id]: '' }))
      setMessage(enable ? `${item.label}: kill switch cleared.` : `${item.label} switched off.`)
      await reload()
    } catch (err) {
      setMessage(errorText(err, 'Could not change the integration'))
    } finally {
      setBusy(null)
    }
  }

  async function check(item: Integration) {
    setBusy(item.id)
    setMessage(null)
    try {
      await api.checkIntegration(role, item.id)
      await reload()
    } catch (err) {
      setMessage(errorText(err, 'Check failed'))
    } finally {
      setBusy(null)
    }
  }

  const grouped = CATEGORY_ORDER.map((cat) => ({
    cat,
    items: (data?.items ?? []).filter((i) => i.category === cat),
  })).filter((g) => g.items.length)

  return (
    <AppShell title="Integrations" breadcrumbs={['Administrator', 'Integrations']}>
      <DemoBanner>
        This page shows what is really connected. Endpoints and credentials are set in the server
        configuration and are never shown or edited here. You can switch a connected source off
        (for example during an outage); you cannot switch on something that is not configured.
      </DemoBanner>

      {error && !data && (
        <p role="alert" className="mb-3 text-sm text-status-failed">
          {error}
        </p>
      )}
      {message && (
        <div
          role="status"
          className="mb-4 rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2 text-xs text-ink-secondary"
        >
          {message}
        </div>
      )}
      {loading && <p className="text-sm text-ink-muted">Checking integrations…</p>}

      {data && (
        <div className="mb-4 flex flex-wrap gap-2 text-xs text-ink-muted">
          {Object.entries(data.summary).map(([k, v]) => (
            <span key={k} className="inline-flex items-center gap-1.5">
              <HealthBadge health={k as Integration['health']} /> {v}
            </span>
          ))}
        </div>
      )}

      <div className="space-y-6">
        {grouped.map((g) => (
          <section key={g.cat}>
            <h3 className="mb-2 text-sm font-semibold text-ink">{CATEGORY_LABEL[g.cat] ?? g.cat}</h3>
            <div className="grid gap-3 lg:grid-cols-2">
              {g.items.map((item) => {
                const details = detailsText(item.details)
                const open = openId === item.id
                return (
                  <Card key={item.id}>
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <h4 className="text-sm font-semibold text-ink">{item.label}</h4>
                          <HealthBadge health={item.health} />
                          <Badge tone="neutral">{item.mode}</Badge>
                        </div>
                        <p className="mt-0.5 text-xs text-ink-muted">{item.description}</p>
                      </div>
                    </div>
                    <p className="mt-2 text-sm text-ink-secondary">{item.message}</p>

                    {item.requiresCredentials && (
                      <p className="mt-1 text-[11px] text-ink-muted">
                        Credentials in server configuration:{' '}
                        <strong>{item.credentialsConfigured ? 'present' : 'not present'}</strong>
                        {' '}(values are never shown)
                      </p>
                    )}
                    {item.lastCheck && (
                      <p className="mt-1 text-[11px] text-ink-muted">
                        Last check {formatDateTime(item.lastCheck.checkedAt)}:{' '}
                        {item.lastCheck.ok === null ? 'not probed' : item.lastCheck.ok ? 'ok' : 'failed'} —{' '}
                        {item.lastCheck.message}
                      </p>
                    )}
                    {item.adminEnabled === false && (
                      <p className="mt-1 text-[11px] text-status-warning">
                        Switched off by {item.adminChangedBy || 'an administrator'}
                        {item.adminChangedAt ? ` on ${formatDateTime(item.adminChangedAt)}` : ''}
                        {item.adminReason ? ` — ${item.adminReason}` : ''}
                      </p>
                    )}

                    {item.limitations.length > 0 && (
                      <ul className="mt-2 list-disc space-y-0.5 pl-4 text-[11px] text-ink-muted">
                        {item.limitations.map((l) => (
                          <li key={l}>{l}</li>
                        ))}
                      </ul>
                    )}

                    {details.length > 0 && (
                      <button
                        type="button"
                        className="mt-2 text-[11px] text-accent underline"
                        onClick={() => setOpenId(open ? null : item.id)}
                      >
                        {open ? 'Hide details' : 'Show details'}
                      </button>
                    )}
                    {open && (
                      <ul className="mt-1 space-y-0.5 text-[11px] text-ink-muted">
                        {details.map((d) => (
                          <li key={d}>{d}</li>
                        ))}
                      </ul>
                    )}

                    <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-border pt-3">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={busy === item.id}
                        onClick={() => void check(item)}
                      >
                        Run check
                      </Button>
                      {item.canToggle && (
                        <>
                          <Input
                            aria-label={`Reason for changing ${item.label}`}
                            className="h-8 max-w-[220px] text-xs"
                            placeholder="Reason (required)"
                            value={reasons[item.id] ?? ''}
                            onChange={(e) => setReasons((r) => ({ ...r, [item.id]: e.target.value }))}
                          />
                          {item.adminEnabled ? (
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={busy === item.id}
                              onClick={() => void toggle(item, false)}
                            >
                              Switch off
                            </Button>
                          ) : (
                            <Button
                              size="sm"
                              disabled={busy === item.id}
                              onClick={() => void toggle(item, true)}
                            >
                              Clear switch-off
                            </Button>
                          )}
                        </>
                      )}
                    </div>
                  </Card>
                )
              })}
            </div>
          </section>
        ))}
      </div>
    </AppShell>
  )
}
