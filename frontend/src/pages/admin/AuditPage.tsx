import { useCallback, useEffect, useState } from 'react'
import { Download, ShieldCheck } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Input, Label, Select } from '@/components/ui/Input'
import { errorText } from '@/components/scrutiny/scrutinyUi'
import { api, type AuditSearchParams } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import { formatDateTime } from '@/lib/format'
import type { AdminAuditDetail, AdminAuditEvent, AuditFacets } from '@/types'

const PAGE = 40

interface Filters {
  q: string
  category: string
  actorRole: string
  actor: string
  applicationNumber: string
  entityType: string
  dateFrom: string
  dateTo: string
}

const EMPTY: Filters = {
  q: '',
  category: '',
  actorRole: '',
  actor: '',
  applicationNumber: '',
  entityType: '',
  dateFrom: '',
  dateTo: '',
}

function toParams(f: Filters): AuditSearchParams {
  return {
    q: f.q.trim() || undefined,
    category: f.category || undefined,
    actorRole: f.actorRole || undefined,
    actor: f.actor.trim() || undefined,
    applicationNumber: f.applicationNumber.trim() || undefined,
    entityType: f.entityType || undefined,
    dateFrom: f.dateFrom ? `${f.dateFrom}T00:00:00` : undefined,
    dateTo: f.dateTo ? `${f.dateTo}T23:59:59` : undefined,
  }
}

function MetaView({ metadata }: { metadata: Record<string, unknown> }) {
  const before = metadata.before as Record<string, unknown> | undefined
  const after = metadata.after as Record<string, unknown> | undefined
  const rest = Object.fromEntries(
    Object.entries(metadata).filter(([k]) => k !== 'before' && k !== 'after'),
  )
  const keys = Array.from(new Set([...Object.keys(before ?? {}), ...Object.keys(after ?? {})]))
  return (
    <div className="space-y-2">
      {keys.length > 0 && (
        <table className="w-full text-left text-[11px]">
          <thead className="text-ink-muted">
            <tr>
              <th className="py-1 pr-3 font-medium">Field</th>
              <th className="py-1 pr-3 font-medium">Before</th>
              <th className="py-1 font-medium">After</th>
            </tr>
          </thead>
          <tbody>
            {keys.map((k) => (
              <tr key={k} className="border-t border-border align-top">
                <td className="py-1 pr-3 font-medium text-ink-secondary">{k}</td>
                <td className="py-1 pr-3 text-ink-muted">{JSON.stringify(before?.[k] ?? null)}</td>
                <td className="py-1 text-ink">{JSON.stringify(after?.[k] ?? null)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {Object.keys(rest).length > 0 && (
        <pre className="max-h-48 overflow-auto rounded-[var(--radius-md)] bg-surface px-2 py-1.5 text-[11px] text-ink-secondary">
          {JSON.stringify(rest, null, 2)}
        </pre>
      )}
    </div>
  )
}

export function AuditPage() {
  const { role } = useRole()
  const [draft, setDraft] = useState<Filters>(EMPTY)
  const [applied, setApplied] = useState<Filters>(EMPTY)
  const [items, setItems] = useState<AdminAuditEvent[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [facets, setFacets] = useState<AuditFacets | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [openId, setOpenId] = useState<string | null>(null)
  const [detail, setDetail] = useState<AdminAuditDetail | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(
    async (filters: Filters, nextOffset: number) => {
      try {
        const page = await api.searchAudit(role, { ...toParams(filters), limit: PAGE, offset: nextOffset })
        setItems(page.items)
        setTotal(page.total)
        setOffset(page.offset)
        setError(null)
      } catch (err) {
        setError(errorText(err, 'Failed to load the audit trail'))
      } finally {
        setLoading(false)
      }
    },
    [role],
  )

  useEffect(() => {
    void load(EMPTY, 0)
    api
      .auditFacets(role)
      .then(setFacets)
      .catch(() => setFacets(null))
  }, [role, load])

  function search() {
    setApplied(draft)
    setOpenId(null)
    void load(draft, 0)
  }

  function clear() {
    setDraft(EMPTY)
    setApplied(EMPTY)
    setOpenId(null)
    void load(EMPTY, 0)
  }

  async function toggleRow(id: string) {
    if (openId === id) {
      setOpenId(null)
      return
    }
    setOpenId(id)
    setDetail(null)
    try {
      setDetail(await api.getAuditEvent(role, id))
    } catch (err) {
      setNote(errorText(err, 'Could not load event details'))
    }
  }

  async function exportCsv() {
    setNote(null)
    try {
      const { blob, fileName } = await api.exportAuditCsv(role, toParams(applied))
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = fileName ?? 'praman-audit-log.csv'
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      setNote('Export downloaded. The export itself has been recorded in the audit trail.')
    } catch (err) {
      setNote(errorText(err, 'Export failed'))
    }
  }

  async function verifyChain() {
    setNote('Verifying…')
    try {
      const r = await api.verifyAuditChain(role)
      setNote(
        r.ok
          ? `Tamper-evident chain intact — ${r.checked} event(s) verified.`
          : `Chain broken at sequence ${r.firstBadSequence}: ${r.detail}`,
      )
    } catch (err) {
      setNote(errorText(err, 'Verification failed'))
    }
  }

  const set = (key: keyof Filters) => (e: { target: { value: string } }) =>
    setDraft((d) => ({ ...d, [key]: e.target.value }))

  const from = total === 0 ? 0 : offset + 1
  const to = Math.min(offset + PAGE, total)

  return (
    <AppShell
      title="Audit trail"
      breadcrumbs={['Regional Officer', 'Audit']}
      actions={
        <>
          <Button size="sm" variant="outline" leftIcon={<ShieldCheck size={14} />} onClick={() => void verifyChain()}>
            Verify chain
          </Button>
          <Button size="sm" variant="outline" leftIcon={<Download size={14} />} onClick={() => void exportCsv()}>
            Export CSV
          </Button>
        </>
      }
    >
      {error && (
        <p role="alert" className="mb-3 text-sm text-status-failed">
          {error}
        </p>
      )}
      {note && (
        <div role="status" className="mb-4 rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2 text-xs">
          {note}
        </div>
      )}

      <Card className="mb-4">
        <CardHeader
          title="Search"
          description={`${total} matching event(s)${facets ? ` of ${facets.total} recorded` : ''}`}
        />
        <form
          className="grid gap-3 md:grid-cols-4"
          onSubmit={(e) => {
            e.preventDefault()
            search()
          }}
        >
          <div className="md:col-span-2">
            <Label>Search text</Label>
            <Input
              value={draft.q}
              onChange={set('q')}
              placeholder="Application number, institution, action, actor, detail…"
            />
          </div>
          <div>
            <Label>Application number</Label>
            <Input value={draft.applicationNumber} onChange={set('applicationNumber')} placeholder="e.g. AIC-2026" />
          </div>
          <div>
            <Label>Actor</Label>
            <Input value={draft.actor} onChange={set('actor')} placeholder="Name" />
          </div>
          <div>
            <Label>Area</Label>
            <Select value={draft.category} onChange={set('category')}>
              <option value="">All areas</option>
              {facets?.categories.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.value} ({c.count})
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label>Actor role</Label>
            <Select value={draft.actorRole} onChange={set('actorRole')}>
              <option value="">Any role</option>
              {facets?.actorRoles.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.value} ({c.count})
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label>Record type</Label>
            <Select value={draft.entityType} onChange={set('entityType')}>
              <option value="">Any record</option>
              {facets?.entityTypes.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.value.replace(/_/g, ' ')} ({c.count})
                </option>
              ))}
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <Label>From</Label>
              <Input type="date" value={draft.dateFrom} onChange={set('dateFrom')} />
            </div>
            <div>
              <Label>To</Label>
              <Input type="date" value={draft.dateTo} onChange={set('dateTo')} />
            </div>
          </div>
          <div className="flex items-end gap-2 md:col-span-4">
            <Button type="submit">Search</Button>
            <Button type="button" variant="outline" onClick={clear}>
              Clear
            </Button>
          </div>
        </form>
      </Card>

      <Card padding={false}>
        <ul className="divide-y divide-border">
          {items.map((ev) => {
            const open = openId === ev.id
            return (
              <li key={ev.id}>
                <button
                  type="button"
                  className="flex w-full flex-col gap-0.5 px-4 py-3 text-left hover:bg-surface"
                  aria-expanded={open}
                  onClick={() => void toggleRow(ev.id)}
                >
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-ink">{ev.label ?? ev.action}</span>
                    {ev.category && <Badge tone="neutral">{ev.category}</Badge>}
                    <code className="text-[11px] text-ink-muted">{ev.action}</code>
                  </span>
                  <span className="text-xs text-ink-secondary">{ev.detail}</span>
                  <span className="text-[11px] text-ink-muted">
                    {ev.actor}
                    {ev.actorRole ? ` (${ev.actorRole})` : ''} · {formatDateTime(ev.timestamp)}
                    {ev.applicationNumber ? ` · ${ev.applicationNumber}` : ''}
                    {ev.entityType ? ` · ${ev.entityType.replace(/_/g, ' ')}` : ''}
                  </span>
                </button>
                {open && (
                  <div className="space-y-3 border-t border-border bg-surface px-4 py-3 text-xs">
                    {!detail || detail.id !== ev.id ? (
                      <p className="text-ink-muted">Loading details…</p>
                    ) : (
                      <>
                        <p className="whitespace-pre-wrap text-ink-secondary">{detail.detail}</p>
                        <dl className="grid gap-1 text-[11px] text-ink-muted sm:grid-cols-2">
                          <div>Event ID: {detail.id}</div>
                          {detail.entityId && <div>Record ID: {detail.entityId}</div>}
                          {detail.applicationId && <div>Application ID: {detail.applicationId}</div>}
                          {detail.actorId && <div>Actor ID: {detail.actorId}</div>}
                        </dl>
                        {detail.metadata && Object.keys(detail.metadata).length > 0 && (
                          <MetaView metadata={detail.metadata} />
                        )}
                        {detail.related.length > 0 && (
                          <div>
                            <div className="mb-1 font-semibold text-ink-secondary">Related events</div>
                            <ul className="space-y-0.5 text-[11px] text-ink-muted">
                              {detail.related.map((r) => (
                                <li key={r.id}>
                                  {formatDateTime(r.timestamp)} · {r.label ?? r.action} · {r.actor}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )}
              </li>
            )
          })}
          {items.length === 0 && !error && !loading && (
            <li className="px-4 py-8 text-center text-sm text-ink-muted">No events match these filters.</li>
          )}
        </ul>
        <div className="flex items-center justify-between border-t border-border px-4 py-3">
          <Button
            size="sm"
            variant="outline"
            disabled={offset <= 0}
            onClick={() => void load(applied, Math.max(0, offset - PAGE))}
          >
            Previous
          </Button>
          <span className="text-xs text-ink-muted">
            {from}–{to} of {total}
          </span>
          <Button
            size="sm"
            variant="outline"
            disabled={offset + PAGE >= total}
            onClick={() => void load(applied, offset + PAGE)}
          >
            Next
          </Button>
        </div>
      </Card>
    </AppShell>
  )
}
