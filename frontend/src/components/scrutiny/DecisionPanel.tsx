import { useState } from 'react'
import { AlertTriangle, CheckCircle2, History, MessageSquare, Wand2 } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input, Textarea } from '@/components/ui/Input'
import { formatDateTime } from '@/lib/format'
import { api } from '@/services/api'
import type { ApplicationDetail, ScrutinyReview } from '@/types'
import { errorText } from './scrutinyUi'

const TERMINAL = new Set(['recommended', 'rejected', 'approved'])

interface Props {
  detail: ApplicationDetail
  review?: ScrutinyReview
  role: string
  onChanged: () => Promise<unknown> | void
}

export function DecisionPanel({ detail, review, role, onChanged }: Props) {
  const canAct = role === 'officer' || role === 'admin'
  const decision = review?.decision
  const closed = TERMINAL.has(detail.status)
  const [note, setNote] = useState('')
  const [title, setTitle] = useState('Clarification required')
  const [body, setBody] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ tone: 'ok' | 'error'; text: string } | null>(null)

  async function act(fn: () => Promise<unknown>, ok: string, after?: () => void) {
    setBusy(true)
    setMsg(null)
    try {
      await fn()
      after?.()
      setMsg({ tone: 'ok', text: ok })
      await onChanged()
    } catch (err) {
      setMsg({ tone: 'error', text: errorText(err, 'Action failed') })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <div className="space-y-4">
        {msg && (
          <div
            role={msg.tone === 'error' ? 'alert' : 'status'}
            className={`rounded-[var(--radius-md)] border px-3 py-2 text-xs ${
              msg.tone === 'error'
                ? 'border-red-200 bg-red-50 text-red-800'
                : 'border-border bg-surface text-ink-secondary'
            }`}
          >
            {msg.text}
          </div>
        )}

        {decision?.finalDecision && (
          <div
            className={`rounded-[var(--radius-md)] border p-3 text-sm ${
              decision.finalDecision === 'rejected'
                ? 'border-red-200 bg-red-50'
                : 'border-emerald-200 bg-emerald-50'
            }`}
          >
            <div className="flex items-center gap-2 font-semibold text-ink">
              Recorded decision:{' '}
              <Badge tone={decision.finalDecision === 'rejected' ? 'failed' : 'pass'}>
                {decision.finalDecision}
              </Badge>
            </div>
            <p className="mt-1 text-xs text-ink-secondary">{decision.finalDecisionReason}</p>
            <p className="mt-1 text-[11px] text-ink-muted">
              {decision.finalDecisionBy ?? 'Officer'}
              {decision.finalDecisionAt ? ` · ${formatDateTime(decision.finalDecisionAt)}` : ''}
            </p>
          </div>
        )}

        {decision && decision.mustCorrect.length > 0 && (
          <div className="rounded-[var(--radius-md)] border border-amber-200 bg-amber-50 p-3">
            <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-amber-950">
              <AlertTriangle size={15} /> What the applicant must correct
            </div>
            <ol className="list-decimal space-y-1 pl-5 text-xs text-amber-950">
              {decision.mustCorrect.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ol>
          </div>
        )}

        {canAct && !closed && (
          <>
            <div className="rounded-[var(--radius-md)] border border-border p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <div className="text-sm font-semibold text-ink">Request clarification</div>
                {decision?.clarificationDraftBody && (
                  <Button
                    size="sm"
                    variant="outline"
                    leftIcon={<Wand2 size={13} />}
                    onClick={() => {
                      setTitle(decision.clarificationDraftTitle || title)
                      setBody(decision.clarificationDraftBody)
                    }}
                  >
                    Use suggested text
                  </Button>
                )}
              </div>
              <Input
                className="mb-2"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Title"
                aria-label="Clarification title"
              />
              <Textarea
                rows={5}
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="Tell the applicant exactly what to correct and which document it is in…"
                aria-label="Clarification details"
              />
              <p className="mt-1 text-[11px] text-ink-muted">
                The applicant sees this text word for word. The suggested text lists open issues in
                plain language; edit it before sending.
              </p>
              <Button
                className="mt-2"
                size="sm"
                variant="outline"
                leftIcon={<AlertTriangle size={14} />}
                disabled={busy || body.trim().length < 5 || title.trim().length < 3}
                onClick={() =>
                  void act(
                    () =>
                      api.requestClarification(role, detail.id, {
                        title: title.trim(),
                        description: body.trim(),
                      }),
                    'Clarification sent. The application is now waiting for the applicant.',
                    () => setBody(''),
                  )
                }
              >
                Send clarification request
              </Button>
            </div>

            <div className="rounded-[var(--radius-md)] border border-border p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <div className="text-sm font-semibold text-ink">Final recommendation</div>
                {decision?.rejectionDraftBody && (
                  <Button
                    size="sm"
                    variant="outline"
                    leftIcon={<Wand2 size={13} />}
                    onClick={() => setReason(decision.rejectionDraftBody)}
                  >
                    Use suggested reasons
                  </Button>
                )}
              </div>
              <p className="mb-2 text-[11px] text-ink-muted">
                Never decided by score alone. The reason is shown to the applicant and kept in the
                audit trail together with all earlier findings.
              </p>
              <Textarea
                rows={4}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Reason for the decision…"
                aria-label="Decision reason"
              />
              {detail.status === 'clarification_required' && (
                <p className="mt-1 text-[11px] text-amber-800">
                  A clarification is still open — the applicant has not resubmitted yet.
                </p>
              )}
              <div className="mt-2 flex flex-wrap gap-2">
                <Button
                  size="sm"
                  leftIcon={<CheckCircle2 size={14} />}
                  disabled={busy || reason.trim().length < 5}
                  onClick={() =>
                    void act(
                      () => api.recordDecision(role, detail.id, { reason: reason.trim(), recommend: true }),
                      'Recorded: recommended.',
                    )
                  }
                >
                  Recommend
                </Button>
                <Button
                  size="sm"
                  variant="danger"
                  disabled={busy || reason.trim().length < 5}
                  onClick={() =>
                    void act(
                      () => api.recordDecision(role, detail.id, { reason: reason.trim(), recommend: false }),
                      'Recorded: rejected. The applicant can see the reason.',
                    )
                  }
                >
                  Reject
                </Button>
              </div>
            </div>
          </>
        )}

        <div>
          <h4 className="mb-2 text-sm font-semibold text-ink">Clarification history</h4>
          {(decision?.clarificationRequests ?? []).length === 0 ? (
            <p className="text-xs text-ink-muted">No clarification has been requested.</p>
          ) : (
            <ul className="space-y-2">
              {decision?.clarificationRequests.map((c) => (
                <li key={c.id} className="rounded border border-border p-2 text-xs">
                  <Badge tone={c.status === 'open' ? 'warning' : c.status === 'responded' ? 'info' : 'neutral'}>
                    {c.status}
                  </Badge>{' '}
                  <span className="font-medium">{c.title}</span>
                  <p className="mt-1 whitespace-pre-line text-ink-secondary">{c.description}</p>
                  {c.applicantResponse && (
                    <p className="mt-1 text-[11px] text-ink-muted">
                      Applicant response: {c.applicantResponse}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="space-y-4">
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink">
            <MessageSquare size={15} /> Reviewer notes (internal)
          </div>
          <ul className="mb-3 space-y-2">
            {detail.reviewNotes.map((n) => (
              <li key={n.id} className="rounded-[var(--radius-md)] border border-border p-3">
                <div className="text-xs font-medium text-ink">
                  {n.author} · {n.role}
                </div>
                <p className="mt-1 whitespace-pre-line text-sm text-ink-secondary">{n.content}</p>
                <div className="mt-1 text-[11px] text-ink-muted">{formatDateTime(n.createdAt)}</div>
              </li>
            ))}
            {detail.reviewNotes.length === 0 && (
              <li className="text-xs text-ink-muted">No notes yet.</li>
            )}
          </ul>
          {canAct && !closed && (
            <>
              <Textarea
                rows={2}
                placeholder="Add an internal note…"
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
              <Button
                className="mt-2"
                size="sm"
                disabled={busy || note.trim().length < 3}
                onClick={() =>
                  void act(() => api.addReviewNote(role, detail.id, note.trim()), 'Note saved.', () =>
                    setNote(''),
                  )
                }
              >
                Save note
              </Button>
            </>
          )}
        </div>

        <div>
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink">
            <History size={15} /> Audit history
          </div>
          <ul className="max-h-[420px] space-y-2 overflow-auto">
            {detail.auditEvents.map((ev) => (
              <li
                key={ev.id}
                className="rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2"
              >
                <div className="text-sm font-medium text-ink">{ev.action}</div>
                <div className="text-xs text-ink-secondary">{ev.detail}</div>
                <div className="mt-1 text-[11px] text-ink-muted">
                  {ev.actor} · {formatDateTime(ev.timestamp)}
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
