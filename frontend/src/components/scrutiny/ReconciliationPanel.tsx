import { useState } from 'react'
import { GitCompare, RefreshCw } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { api } from '@/services/api'
import type { ApplicationDetail, Discrepancy } from '@/types'
import { ResolveControl } from './ResolveControl'
import { errorText, type Resolution } from './scrutinyUi'

const BUCKETS = ['MISMATCH', 'MISSING_DATA', 'POSSIBLE_DUPLICATE', 'MANUAL_REVIEW', 'MATCH'] as const

const BUCKET_LABEL: Record<(typeof BUCKETS)[number], string> = {
  MISMATCH: 'Values differ',
  MISSING_DATA: 'Detail missing on some documents',
  POSSIBLE_DUPLICATE: 'Possible duplicate files',
  MANUAL_REVIEW: 'Needs officer review',
  MATCH: 'Matching across documents',
}

function tone(outcome: string): 'pass' | 'failed' | 'warning' | 'manual' | 'neutral' {
  switch (outcome) {
    case 'MATCH':
      return 'pass'
    case 'MISMATCH':
      return 'failed'
    case 'MISSING_DATA':
      return 'warning'
    case 'POSSIBLE_DUPLICATE':
    case 'MANUAL_REVIEW':
      return 'manual'
    default:
      return 'neutral'
  }
}

interface Props {
  detail: ApplicationDetail
  role: string
  onChanged: () => Promise<unknown> | void
}

export function ReconciliationPanel({ detail, role, onChanged }: Props) {
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const canAct = role === 'officer' || role === 'admin'

  async function run() {
    setBusy(true)
    setMsg(null)
    try {
      const r = await api.runReconciliation(role, detail.id)
      const c = (r.summary?.counts as Record<string, number>) || {}
      setMsg(
        `Re-compared the current documents: ${c.MATCH ?? 0} match, ${c.MISMATCH ?? 0} differ, ${c.MISSING_DATA ?? 0} missing, ${c.POSSIBLE_DUPLICATE ?? 0} duplicate. Not a fraud determination.`,
      )
      await onChanged()
    } catch (err) {
      setMsg(errorText(err, 'Reconciliation failed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm font-semibold text-ink">
          <GitCompare size={16} /> Cross-document reconciliation
        </div>
        {canAct && (
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            leftIcon={<RefreshCw size={14} />}
            onClick={() => void run()}
          >
            {busy ? 'Comparing…' : 'Re-compare documents'}
          </Button>
        )}
      </div>
      <p className="text-xs text-ink-muted">
        Compares the same detail (institution name, registration numbers, dates, survey numbers,
        land area, addresses) across the <strong>current</strong> version of every document. It
        updates automatically when a document is replaced.
      </p>
      {msg && (
        <div className="rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2 text-xs text-ink-secondary">
          {msg}
        </div>
      )}
      {detail.discrepancies.length === 0 && (
        <EmptyState
          icon={GitCompare}
          title="Nothing to compare yet"
          description="Upload at least two documents that state the same details."
        />
      )}
      {BUCKETS.map((bucket) => {
        const rows = detail.discrepancies.filter((d) => d.outcome === bucket)
        if (!rows.length) return null
        return (
          <section key={bucket} className="space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
              {BUCKET_LABEL[bucket]} ({rows.length})
            </h4>
            {rows.map((d) => (
              <Item key={d.id} d={d} canAct={canAct && bucket !== 'MATCH'} role={role} onChanged={onChanged} />
            ))}
          </section>
        )
      })}
    </div>
  )
}

function Item({
  d,
  canAct,
  role,
  onChanged,
}: {
  d: Discrepancy
  canAct: boolean
  role: string
  onChanged: () => Promise<unknown> | void
}) {
  async function resolve(status: Resolution, reason: string) {
    await api.resolveReconciliationItem(role, d.id, { status, reason })
    await onChanged()
  }
  return (
    <div className="rounded-[var(--radius-md)] border border-border p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-ink">{d.title || d.fieldName}</span>
        <Badge tone={tone(d.outcome)}>{d.outcome.replace(/_/g, ' ').toLowerCase()}</Badge>
        {d.status !== 'open' && <Badge>{d.status}</Badge>}
      </div>
      {d.description && <p className="mb-3 text-xs text-ink-secondary">{d.description}</p>}
      <div className="grid gap-2 sm:grid-cols-2">
        {d.values.map((v) => (
          <div key={`${v.documentId}-${v.value}`} className="rounded border border-border bg-surface p-3">
            <div className="text-[11px] text-ink-muted">
              {v.documentName}
              {v.page ? ` · ${v.page}` : ''}
              {v.pageNumber != null ? ` · page ${v.pageNumber}` : ''}
            </div>
            <div className="mt-1 text-sm font-medium text-ink">{v.value}</div>
            {v.normalizedValue && v.normalizedValue !== v.value && (
              <div className="mt-1 text-[11px] text-ink-muted">Normalized: {v.normalizedValue}</div>
            )}
          </div>
        ))}
      </div>
      {d.resolutionReason && (
        <p className="mt-2 text-[11px] text-ink-muted">Officer note: {d.resolutionReason}</p>
      )}
      {canAct && d.status === 'open' && <ResolveControl onResolve={resolve} />}
    </div>
  )
}
