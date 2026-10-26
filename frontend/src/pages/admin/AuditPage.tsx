import { useEffect, useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input, Label } from '@/components/ui/Input'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import { formatDateTime } from '@/lib/format'
import type { AdminAuditEvent } from '@/types'

export function AuditPage() {
  const { role } = useRole()
  const [items, setItems] = useState<AdminAuditEvent[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [action, setAction] = useState('')
  const [actor, setActor] = useState('')
  const [q, setQ] = useState('')
  const [error, setError] = useState<string | null>(null)
  const limit = 40

  function load(nextOffset = 0) {
    api
      .searchAudit(role, {
        action: action || undefined,
        actor: actor || undefined,
        q: q || undefined,
        limit,
        offset: nextOffset,
      })
      .then((page) => {
        setItems(page.items)
        setTotal(page.total)
        setOffset(page.offset)
        setError(null)
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : 'Failed to load audit log'),
      )
  }

  useEffect(() => {
    load(0)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role])

  return (
    <AppShell title="Audit Trail" breadcrumbs={['Administrator', 'Audit']}>
      <DemoBanner>
        Searchable append-only audit log for uploads, extraction, rule changes, verification,
        reviewer actions, and status transitions. Secrets and document contents are never shown.
      </DemoBanner>

      {error && (
        <div className="mb-4 rounded-[var(--radius-md)] border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          {error}
        </div>
      )}

      <Card className="mb-4">
        <CardHeader title="Filters" description={`${total} matching event(s)`} />
        <div className="grid gap-3 md:grid-cols-4">
          <div>
            <Label>Action contains</Label>
            <Input
              value={action}
              onChange={(e) => setAction(e.target.value)}
              placeholder="workflow. / admin.rule"
            />
          </div>
          <div>
            <Label>Actor</Label>
            <Input value={actor} onChange={(e) => setActor(e.target.value)} placeholder="Name" />
          </div>
          <div>
            <Label>Free text</Label>
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="detail search" />
          </div>
          <div className="flex items-end">
            <Button onClick={() => load(0)}>Search</Button>
          </div>
        </div>
      </Card>

      <Card>
        <ul className="divide-y divide-border">
          {items.map((ev) => (
            <li key={ev.id} className="py-3">
              <div className="text-sm font-medium text-ink">{ev.action}</div>
              <div className="text-xs text-ink-secondary">{ev.detail}</div>
              <div className="mt-1 text-[11px] text-ink-muted">
                {ev.actor}
                {ev.actorRole ? ` (${ev.actorRole})` : ''} · {formatDateTime(ev.timestamp)}
                {ev.applicationId ? ` · app ${ev.applicationId}` : ''}
                {ev.entityType ? ` · ${ev.entityType}` : ''}
              </div>
            </li>
          ))}
          {items.length === 0 && !error && (
            <li className="py-6 text-center text-sm text-ink-muted">No events match filters.</li>
          )}
        </ul>
        <div className="mt-3 flex items-center justify-between">
          <Button
            size="sm"
            variant="outline"
            disabled={offset <= 0}
            onClick={() => load(Math.max(0, offset - limit))}
          >
            Previous
          </Button>
          <span className="text-xs text-ink-muted">
            {offset + 1}–{Math.min(offset + limit, total)} of {total}
          </span>
          <Button
            size="sm"
            variant="outline"
            disabled={offset + limit >= total}
            onClick={() => load(offset + limit)}
          >
            Next
          </Button>
        </div>
      </Card>
    </AppShell>
  )
}
