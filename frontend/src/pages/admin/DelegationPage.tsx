import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { RefreshCw, Workflow, CheckCircle2 } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { Select } from '@/components/ui/Input'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { StatusDot } from '@/components/ui/StatusDot'
import { useRole } from '@/app/RoleContext'
import { api, ApiError } from '@/services/api'
import { formatRelative } from '@/lib/format'
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
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pick, setPick] = useState<Record<string, string>>({})

  const reload = useCallback(async () => {
    setLoading(true)
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
    } finally {
      setLoading(false)
    }
  }, [role])

  useEffect(() => { void reload() }, [reload])

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
    <AppShell
      title="Delegation Queue"
      description="Incoming applications are auto-assigned on submit. Clear leftovers, reassign, and tune load-balancing weights."
      breadcrumbs={['Regional Officer', 'Delegation']}
      actions={
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={busy || queue.length === 0}
            onClick={() => void autoAll()}
            className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white transition-colors disabled:opacity-40"
            style={{ background: '#E8622A' }}
            onMouseEnter={(e) => (e.currentTarget.style.background = '#D4541F')}
            onMouseLeave={(e) => (e.currentTarget.style.background = '#E8622A')}
          >
            <Workflow size={14} />
            Auto-delegate all ({queue.length})
          </button>
          <button
            type="button"
            aria-label="Refresh delegation queue"
            disabled={busy}
            onClick={() => void reload()}
            className="flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-colors disabled:opacity-40"
            style={{ border: '1px solid #E0E0E0', color: '#333333' }}
            onMouseEnter={(e) => (e.currentTarget.style.background = '#F5F5F5')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            <RefreshCw size={14} />
            Refresh
          </button>
        </div>
      }
    >
      {/* Feedback messages */}
      {error && (
        <div
          className="mb-6 rounded-xl px-4 py-3 text-sm"
          style={{ background: '#FEF3C7', color: '#B45309', border: '1px solid #FDE68A' }}
        >
          {error}
        </div>
      )}
      {msg && (
        <div
          className="mb-6 flex items-center gap-2 rounded-xl px-4 py-3 text-sm"
          style={{ background: '#F0FDF4', color: '#166534', border: '1px solid #BBF7D0' }}
        >
          <CheckCircle2 size={15} />
          {msg}
        </div>
      )}

      {/* ── Two-column layout ───────────────────────────────── */}
      <div className="grid gap-6 xl:grid-cols-[1fr_320px]">
        {/* Left: Unassigned queue */}
        <div
          className="rounded-xl overflow-hidden"
          style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
        >
          <div className="px-6 py-4" style={{ borderBottom: '1px solid #F0F0F0' }}>
            <div className="text-sm font-semibold" style={{ color: '#111111' }}>
              Unassigned Applications
            </div>
            <div className="text-[11px] mt-0.5" style={{ color: '#888888' }}>
              {loading ? 'Loading…' : `${queue.length} waiting for a scrutiny officer`}
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[600px] text-left">
              <thead>
                <tr style={{ borderBottom: '1px solid #F0F0F0' }}>
                  {['Application', 'Institution', 'Submitted', 'Assign to', ''].map((col) => (
                    <th
                      key={col}
                      className="px-6 py-3 text-[11px] font-semibold uppercase tracking-wider"
                      style={{ color: '#AAAAAA' }}
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <SkeletonTable rows={4} cols={5} />
                ) : queue.length === 0 ? (
                  <tr>
                    <td
                      colSpan={5}
                      className="px-6 py-12 text-center text-sm"
                      style={{ color: '#AAAAAA' }}
                    >
                      <div className="mb-1">✓ No unassigned applications</div>
                      <div className="text-[11px]">All applications have been delegated.</div>
                    </td>
                  </tr>
                ) : (
                  queue.map((a) => (
                    <tr
                      key={a.id}
                      className="transition-colors hover:bg-[#FAFAFA]"
                      style={{ borderBottom: '1px solid #F0F0F0' }}
                    >
                      <td className="px-6 py-4">
                        <Link
                          to={`/officer/applications/${a.id}`}
                          className="mono text-sm font-semibold hover:underline"
                          style={{ color: '#111111' }}
                        >
                          {a.applicationNumber}
                        </Link>
                        <div className="text-[11px] mt-0.5" style={{ color: '#888888' }}>
                          {a.category}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm" style={{ color: '#333333' }}>
                        {a.institutionName}
                      </td>
                      <td className="px-6 py-4 text-[12px]" style={{ color: '#888888' }}>
                        {formatRelative(a.submittedAt)}
                      </td>
                      <td className="px-6 py-4">
                        <Select
                          value={pick[a.id] ?? ''}
                          onChange={(e) => setPick((p) => ({ ...p, [a.id]: e.target.value }))}
                          aria-label={`Assign ${a.applicationNumber} to officer`}
                          className="!w-44 !text-xs"
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
                      <td className="px-6 py-4 text-right">
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void assignOne(a.id, pick[a.id] || undefined)}
                          className="rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-40"
                          style={{ border: '1px solid #E0E0E0', color: '#333333' }}
                          onMouseEnter={(e) => (e.currentTarget.style.background = '#F5F5F5')}
                          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                        >
                          Assign
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-4">
          {/* Officer workload cards */}
          <div
            className="rounded-xl overflow-hidden"
            style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
          >
            <div className="px-5 py-4" style={{ borderBottom: '1px solid #F0F0F0' }}>
              <div className="text-sm font-semibold" style={{ color: '#111111' }}>Officer Workload</div>
              <div className="text-[11px] mt-0.5" style={{ color: '#888888' }}>Active queue vs capacity</div>
            </div>
            <div className="divide-y divide-[#F0F0F0]">
              {loading
                ? Array.from({ length: 3 }).map((_, i) => (
                    <div key={i} className="animate-pulse px-5 py-4">
                      <div className="h-3 w-28 rounded bg-[#F0F0F0] mb-2" />
                      <div className="h-2 w-full rounded-full bg-[#F0F0F0]" />
                    </div>
                  ))
                : officers.map((o) => {
                    const pct = o.maxQueueCap > 0
                      ? Math.round((o.activeCount / o.maxQueueCap) * 100)
                      : 0
                    const barColor = o.isAtCap ? '#B91C1C' : pct > 70 ? '#E8622A' : '#2E7D52'
                    return (
                      <div key={o.id} className="px-5 py-4">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium" style={{ color: '#111111' }}>
                            {o.name}
                          </span>
                          <StatusDot
                            status={o.isAtCap ? 'failed' : 'pass'}
                            label={o.isAtCap ? 'At cap' : 'Available'}
                          />
                        </div>
                        {/* Capacity bar */}
                        <div
                          className="w-full rounded-full mb-1"
                          style={{ background: '#F0F0F0', height: '5px' }}
                        >
                          <div
                            className="rounded-full transition-all"
                            style={{
                              width: `${Math.min(pct, 100)}%`,
                              background: barColor,
                              height: '5px',
                            }}
                          />
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-[11px]" style={{ color: '#888888' }}>
                            {o.activeCount} / {o.maxQueueCap} · {o.openIssues} open issues
                          </span>
                          <span className="text-[11px]" style={{ color: '#AAAAAA' }}>
                            {o.lastAssignedAt ? formatRelative(o.lastAssignedAt) : 'never assigned'}
                          </span>
                        </div>
                      </div>
                    )
                  })}
            </div>
          </div>

          {/* Delegation weight settings */}
          {settings && (
            <div
              className="rounded-xl px-5 py-4"
              style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
            >
              <div className="text-sm font-semibold mb-1" style={{ color: '#111111' }}>
                Load-Balancing Weights
              </div>
              <div className="text-[11px] mb-4" style={{ color: '#888888' }}>
                Adjust how officers are scored for auto-assignment.
              </div>
              <div className="space-y-3">
                {(
                  [
                    ['active_count_weight', 'Active count weight'],
                    ['open_issues_weight', 'Open issues weight'],
                    ['recency_weight', 'Recency weight'],
                    ['max_queue_cap', 'Max queue cap'],
                  ] as const
                ).map(([key, label]) => (
                  <label key={key} className="block">
                    <span className="text-[11px] font-medium" style={{ color: '#555555' }}>
                      {label}
                    </span>
                    <input
                      type="number"
                      className="mt-1 w-full rounded-lg border bg-[#FAFAFA] px-3 py-1.5 text-sm outline-none focus:border-[#E8622A] focus:ring-2 focus:ring-[#E8622A]/15 transition-colors"
                      style={{ border: '1px solid #E0E0E0', color: '#111111' }}
                      value={settings[key]}
                      step={key === 'max_queue_cap' ? 1 : 0.1}
                      onChange={(e) =>
                        setSettings({ ...settings, [key]: Number(e.target.value) })
                      }
                    />
                  </label>
                ))}
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void saveSettings()}
                  className="w-full rounded-lg py-2 text-sm font-semibold text-white transition-colors disabled:opacity-40"
                  style={{ background: '#E8622A' }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = '#D4541F')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = '#E8622A')}
                >
                  Save weights
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  )
}
