import { useState } from 'react'
import { History as HistoryIcon } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { formatDateTime } from '@/lib/format'
import { api } from '@/services/api'
import type { FindingLifecycle as Lifecycle, FindingTransition, ScrutinyIssue } from '@/types'
import { errorText } from './scrutinyUi'

export const LIFECYCLE_LABEL: Record<Lifecycle, string> = {
  open: 'Open',
  under_review: 'Under review',
  clarification_requested: 'Clarification requested',
  reopened: 'Reopened',
  resolved: 'Resolved',
  waived: 'Waived',
  accepted: 'Accepted',
  superseded: 'Superseded',
}

const CLOSED = new Set<Lifecycle>(['resolved', 'waived', 'accepted'])

interface Props {
  issue: ScrutinyIssue
  role: string
  canAct: boolean
  onChanged: () => Promise<unknown> | void
}

/** Lifecycle actions and the recorded history for the findings behind one issue. */
export function FindingLifecycleControls({ issue, role, canAct, onChanged }: Props) {
  const lifecycle = (issue.lifecycleStatus ?? issue.status) as Lifecycle
  const findingIds = issue.findingIds
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reopening, setReopening] = useState(false)
  const [reason, setReason] = useState('')
  const [history, setHistory] = useState<FindingTransition[] | null>(null)
  const [showHistory, setShowHistory] = useState(false)

  if (findingIds.length === 0) return null

  const canMarkUnderReview =
    canAct && issue.status === 'open' && lifecycle !== 'under_review'
  const canReopen = canAct && CLOSED.has(lifecycle)

  async function move(status: Lifecycle, why = '') {
    setBusy(true)
    setError(null)
    try {
      for (const id of findingIds) await api.transitionFinding(role, id, { status, reason: why })
      setReopening(false)
      setReason('')
      setHistory(null)
      await onChanged()
    } catch (err) {
      setError(errorText(err, 'Could not change the status'))
    } finally {
      setBusy(false)
    }
  }

  async function toggleHistory() {
    const next = !showHistory
    setShowHistory(next)
    if (!next || history) return
    try {
      const lists = await Promise.all(findingIds.map((id) => api.getFindingHistory(role, id)))
      setHistory(
        lists.flat().sort((a, b) => a.createdAt.localeCompare(b.createdAt)),
      )
    } catch (err) {
      setError(errorText(err, 'Could not load the history'))
    }
  }

  return (
    <div className="space-y-2 border-t border-border pt-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
          Status
        </span>
        <span className="text-xs font-medium text-ink">{LIFECYCLE_LABEL[lifecycle] ?? lifecycle}</span>
        {canMarkUnderReview && (
          <Button size="sm" variant="outline" disabled={busy} onClick={() => void move('under_review')}>
            Mark under review
          </Button>
        )}
        {canReopen && !reopening && (
          <Button size="sm" variant="outline" disabled={busy} onClick={() => setReopening(true)}>
            Reopen…
          </Button>
        )}
        <Button
          size="sm"
          variant="ghost"
          leftIcon={<HistoryIcon size={12} />}
          aria-expanded={showHistory}
          onClick={() => void toggleHistory()}
        >
          {showHistory ? 'Hide history' : 'History'}
        </Button>
      </div>

      {reopening && (
        <div className="flex flex-wrap items-center gap-2">
          <Input
            className="min-w-[14rem] flex-1 text-xs"
            value={reason}
            placeholder="Why is this being reopened?"
            aria-label="Reason for reopening"
            onChange={(e) => setReason(e.target.value)}
          />
          <Button
            size="sm"
            disabled={busy || reason.trim().length < 5}
            onClick={() => void move('reopened', reason.trim())}
          >
            Reopen finding
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setReopening(false)}>
            Cancel
          </Button>
        </div>
      )}

      {error && (
        <p role="alert" className="text-[11px] text-status-failed">
          {error}
        </p>
      )}

      {showHistory && (
        <ol className="space-y-1 text-[11px] text-ink-secondary" aria-label="Finding history">
          {history === null && <li className="text-ink-muted">Loading history…</li>}
          {history?.length === 0 && <li className="text-ink-muted">No recorded changes yet.</li>}
          {history?.map((h) => (
            <li key={h.id}>
              <span className="font-medium text-ink">
                {LIFECYCLE_LABEL[h.fromStatus] ?? h.fromStatus} → {LIFECYCLE_LABEL[h.toStatus] ?? h.toStatus}
              </span>{' '}
              · {h.actorName} ({h.actorRole}) · {formatDateTime(h.createdAt)}
              {h.reason && <span className="block text-ink-muted">{h.reason}</span>}
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
