import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { RefreshCw, Workflow } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Select } from '@/components/ui/Input'
import { useRole } from '@/app/RoleContext'
import { api, ApiError } from '@/services/api'
import { formatDateTime } from '@/lib/format'
import type { ApplicationSummary } from '@/types'

interface OfficerLoad {
  id: string
  name: string
  email: string
  isActive: boolean
  activeCount: number
  openIssues: number
  lastAssignedAt?: string | null
  maxQueueCap: number
  isAtCap: boolean
}

interface DelegationSettings {
  active_count_weight: number
  open_issues_weight: number
  recency_weight: number
  max_queue_cap: number
}

export function DelegationPage() {
  const { role } = useRole()
  const [queue, setQueue] = useState<ApplicationSummary[]>([])
  const [officers, setOfficers] = useState<OfficerLoad[]>([])
  const [settings, setSettings] = useState<DelegationSettings | null>(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pick, setPick] = useState<Record<string, string>>({})

  const reload = useCallback(async () => {
    setError(null)
    try {
      const [q, o, s] = await Promise.all([
        api.getDelegationQueue(role),
        api.listOfficersWithLoad(role),
        api.getDelegationSettings(role),
      ])
      setQueue(q)
      setOfficers(o)
      setSettings(s)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load delegation data.')
    }
  }, [role])

  useEffect(() => {
    void reload()
  }, [reload])

  async function autoAll() {
    setBusy(true)
    setMsg(null)
    try {
      const res = await api.bulkDelegate(role)
      const ok = res.results.filter((r) => r.ok).length
      const fail = res.results.length - ok
      setMsg(`Auto-delegated ${ok} application(s)${fail ? `, ${fail} still unassigned` : ''}.`)
      await reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Bulk delegate failed.')
    } finally {
      setBusy(false)
    }
  }

  async function assignOne(appId: string, officerId?: string) {
    setBusy(true)
    setMsg(null)
    try {
      await api.delegateApplication(role, appId, officerId)
      setMsg(officerId ? 'Assigned manually.' : 'Auto-assigned to the least-burdened officer.')
      await reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Assignment failed.')
    } finally {
      setBusy(false)
    }
  }

  async function saveSettings() {
    if (!settings) return
    setBusy(true)
    try {
      const next = await api.updateDelegationSettings(role, settings)
      setSettings(next)
      setMsg('Delegation weights saved.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save settings.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AppShell title="Delegation Queue" breadcrumbs={['Regional Officer', 'Delegation']}>
      <p className="mb-4 text-sm text-ink-secondary">
        Incoming applications are auto-assigned on submit. Use this page to clear leftovers, reassign,
        and tune load-balancing weights.
      </p>

      {error && (
        <div className="mb-4 rounded-[var(--radius-md)] border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          {error}
        </div>
      )}
      {msg && (
        <div className="mb-4 rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2 text-xs text-ink-secondary">
          {msg}
        </div>
      )}

      <div className="mb-4 flex flex-wrap gap-2">
        <Button size="sm" leftIcon={<Workflow size={14} />} disabled={busy || queue.length === 0} onClick={() => void autoAll()}>
          Auto-delegate all ({queue.length})
        </Button>
        <Button size="sm" variant="outline" leftIcon={<RefreshCw size={14} />} disabled={busy} onClick={() => void reload()}>
          Refresh
        </Button>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2" padding={false}>
          <div className="border-b border-border px-5 py-3">
            <CardHeader title="Unassigned applications" description={`${queue.length} waiting for a scrutiny officer`} />
          </div>
          {queue.length === 0 ? (
            <p className="px-5 py-6 text-sm text-ink-muted">No unassigned applications.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead>
                  <tr className="border-b border-border bg-surface text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                    <th className="px-4 py-2">Application</th>
                    <th className="px-4 py-2">Institution</th>
                    <th className="px-4 py-2">Submitted</th>
                    <th className="px-4 py-2">Assign to</th>
                    <th className="px-4 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {queue.map((a) => (
                    <tr key={a.id} className="border-b border-border last:border-0">
                      <td className="px-4 py-2.5 font-medium text-ink">
                        <Link className="text-brand underline" to={`/officer/applications/${a.id}`}>
                          {a.applicationNumber}
                        </Link>
                      </td>
                      <td className="px-4 py-2.5 text-ink-secondary">{a.institutionName}</td>
                      <td className="px-4 py-2.5 text-xs text-ink-muted">
                        {a.submittedAt ? formatDateTime(a.submittedAt) : '—'}
                      </td>
                      <td className="px-4 py-2.5">
                        <Select
                          value={pick[a.id] ?? ''}
                          onChange={(e) => setPick((p) => ({ ...p, [a.id]: e.target.value }))}
                          aria-label={`Assign ${a.applicationNumber}`}
                        >
                          <option value="">Auto (least burdened)</option>
                          {officers.map((o) => (
                            <option key={o.id} value={o.id} disabled={o.isAtCap}>
                              {o.name} ({o.activeCount}/{o.maxQueueCap})
                              {o.isAtCap ? ' — at cap' : ''}
                            </option>
                          ))}
                        </Select>
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={busy}
                          onClick={() => void assignOne(a.id, pick[a.id] || undefined)}
                        >
                          Assign
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader title="Officer workload" description="Active queue vs cap" />
            <ul className="space-y-2">
              {officers.map((o) => (
                <li
                  key={o.id}
                  className="rounded-[var(--radius-md)] border border-border px-3 py-2 text-sm"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-ink">{o.name}</span>
                    {o.isAtCap ? <Badge tone="warning">At cap</Badge> : <Badge tone="pass">Available</Badge>}
                  </div>
                  <div className="mt-1 text-xs text-ink-muted">
                    Active {o.activeCount}/{o.maxQueueCap} · Open issues {o.openIssues}
                  </div>
                  <div className="text-[11px] text-ink-muted">
                    Last assigned:{' '}
                    {o.lastAssignedAt ? formatDateTime(o.lastAssignedAt) : 'never'}
                  </div>
                </li>
              ))}
            </ul>
          </Card>

          {settings && (
            <Card>
              <CardHeader title="Delegation weights" description="Editable load-balancing knobs" />
              <div className="space-y-2 text-sm">
                {(
                  [
                    ['active_count_weight', 'Active count weight'],
                    ['open_issues_weight', 'Open issues weight'],
                    ['recency_weight', 'Recency weight'],
                    ['max_queue_cap', 'Max queue cap'],
                  ] as const
                ).map(([key, label]) => (
                  <label key={key} className="block text-xs text-ink-secondary">
                    {label}
                    <input
                      type="number"
                      className="mt-1 w-full rounded-[var(--radius-md)] border border-border px-2 py-1.5 text-sm text-ink"
                      value={settings[key]}
                      step={key === 'max_queue_cap' ? 1 : 0.1}
                      onChange={(e) =>
                        setSettings({ ...settings, [key]: Number(e.target.value) })
                      }
                    />
                  </label>
                ))}
                <Button size="sm" disabled={busy} onClick={() => void saveSettings()}>
                  Save weights
                </Button>
              </div>
            </Card>
          )}
        </div>
      </div>
    </AppShell>
  )
}
