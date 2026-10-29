import { useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  FileCheck,
  History,
  MessageSquare,
  Wand2,
} from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input, Textarea } from '@/components/ui/Input'
import { CorrectionTable, rowsFromOfficerText } from '@/components/shared/CorrectionTable'
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
  /** Optional slide-over; primary UX is the dialog from Next actions. */
  onRequestClarificationDrawer?: () => void
}

type DialogKey = 'decision' | 'clarify' | 'notes' | 'audit' | null

export function DecisionPanel({
  detail,
  review,
  role,
  onChanged,
  onRequestClarificationDrawer,
}: Props) {
  const canAct = role === 'officer' || role === 'regional_officer'
  const decision = review?.decision
  const closed = TERMINAL.has(detail.status)

  const [dialog, setDialog] = useState<DialogKey>(null)
  const [note, setNote] = useState('')
  const [title, setTitle] = useState('Clarification required')
  const [body, setBody] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ tone: 'ok' | 'error'; text: string } | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [showPreview, setShowPreview] = useState(false)
  const [activeHistoryItem, setActiveHistoryItem] = useState<{
    id: string
    title: string
    status: string
    description?: string
    applicantResponse?: string | null
    createdAt?: string
  } | null>(null)

  const clarifiable = (review?.issueGroups ?? []).flatMap((g) =>
    g.issues.filter((i) => i.status === 'open' && i.findingIds.length > 0 && i.severity !== 'info'),
  )
  const chosen = clarifiable.filter((i) => selected.has(i.key))
  const chosenFindingIds = Array.from(new Set(chosen.flatMap((i) => i.findingIds)))
  const toggle = (key: string) =>
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })

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

  const openClarifs = (detail.deficiencies ?? []).filter((d) => d.status === 'open').length
  const notesCount = detail.reviewNotes?.length ?? 0
  const auditCount = detail.auditEvents?.length ?? 0

  function closeDialog() {
    setDialog(null)
  }

  const mustCorrectRows =
    decision?.mustCorrectRows && decision.mustCorrectRows.length > 0
      ? decision.mustCorrectRows
      : decision?.mustCorrect?.length
        ? rowsFromOfficerText(decision.mustCorrect.join('\n'))
        : rowsFromOfficerText(decision?.finalDecisionReason)

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
        <h3 className="text-[10px] font-semibold uppercase tracking-widest text-ink-muted">
          Next actions
        </h3>

        {msg && (
          <div
            role={msg.tone === 'error' ? 'alert' : 'status'}
            className={`rounded-[var(--radius-md)] border px-3 py-2 text-xs ${
              msg.tone === 'error'
                ? 'border-[#e2cbc8] bg-status-failed-bg text-status-failed'
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
                ? 'border-[#e2cbc8] bg-status-failed-bg'
                : 'border-[#cfdad2] bg-status-pass-bg'
            }`}
          >
            <div className="flex flex-wrap items-center gap-2 font-semibold text-ink">
              Recorded decision
              <Badge tone={decision.finalDecision === 'rejected' ? 'failed' : 'pass'}>
                {decision.finalDecision}
              </Badge>
            </div>
            <p className="mt-1 text-xs text-ink-muted">
              {decision.finalDecisionBy ?? 'Officer'}
              {decision.finalDecisionAt ? ` · ${formatDateTime(decision.finalDecisionAt)}` : ''}
            </p>
            {decision.finalDecisionReason && (
              <p className="mt-2 text-xs text-ink-secondary line-clamp-3">
                {decision.finalDecisionReason.split('\n')[0]}
              </p>
            )}
          </div>
        )}

        <div className="flex flex-col gap-1">
          {canAct && !closed && (
            <ActionButton
              icon={FileCheck}
              label="Mark for decision"
              hint="Recommend or reject"
              onClick={() => setDialog('decision')}
            />
          )}
          {canAct && !closed && (
            <ActionButton
              icon={AlertTriangle}
              label="Request clarification"
              hint="Ask applicant to correct"
              badge={openClarifs || (decision?.clarificationDraftBody ? 1 : 0) || undefined}
              onClick={() => {
                if (onRequestClarificationDrawer) onRequestClarificationDrawer()
                else setDialog('clarify')
              }}
            />
          )}
          <ActionButton
            icon={MessageSquare}
            label="Add internal note"
            hint={notesCount > 0 ? `${notesCount} on file` : 'Private to officers'}
            badge={notesCount || undefined}
            onClick={() => setDialog('notes')}
          />
          <ActionButton
            icon={History}
            label="Audit trail"
            hint={auditCount > 0 ? `${auditCount} events` : 'Case history'}
            badge={auditCount || undefined}
            onClick={() => setDialog('audit')}
          />
        </div>
      </div>

      {/* ── Decision dialog ── */}
      <Dialog
        open={dialog === 'decision'}
        onClose={closeDialog}
        title="Final recommendation"
        subtitle={`Application ${detail.applicationNumber}`}
        width="max-w-xl"
        dismissible={!busy}
      >
        <div className="space-y-4 p-4 sm:p-5">
          {mustCorrectRows.length > 0 && (
            <div className="rounded-[var(--radius-md)] border border-border p-3">
              <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-ink">
                <AlertTriangle size={14} className="text-status-warning" /> What the applicant must correct
              </div>
              <div className="overflow-x-auto text-xs">
                <CorrectionTable rows={mustCorrectRows} />
              </div>
            </div>
          )}

          {canAct && !closed && (
            <>
              <div className="flex items-center justify-between gap-2">
                <p className="text-[11px] text-ink-muted leading-relaxed">
                  Never decided by score alone. The reason is shown to the applicant and kept in the audit trail.
                </p>
                {decision?.rejectionDraftBody && (
                  <Button
                    size="sm"
                    variant="outline"
                    leftIcon={<Wand2 size={12} />}
                    onClick={() => setReason(decision.rejectionDraftBody)}
                  >
                    Use suggested reasons
                  </Button>
                )}
              </div>
              <Textarea
                rows={5}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Reason for the decision…"
                aria-label="Decision reason"
              />
              {detail.status === 'clarification_required' && (
                <div className="rounded border border-amber-200 bg-amber-50 px-2.5 py-1.5 text-[11px] text-amber-900">
                  A clarification is still open — the applicant has not resubmitted yet.
                </div>
              )}
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <Button
                  size="sm"
                  leftIcon={<CheckCircle2 size={14} />}
                  disabled={busy || reason.trim().length < 5}
                  onClick={() =>
                    void act(
                      () => api.recordDecision(role, detail.id, { reason: reason.trim(), recommend: true }),
                      'Recorded: recommended.',
                      closeDialog,
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
                      closeDialog,
                    )
                  }
                >
                  Reject
                </Button>
                <Button size="sm" variant="ghost" onClick={closeDialog}>
                  Cancel
                </Button>
              </div>
            </>
          )}
        </div>
      </Dialog>

      {/* ── Clarification dialog ── */}
      <Dialog
        open={dialog === 'clarify'}
        onClose={closeDialog}
        title="Request clarification"
        subtitle={`Application ${detail.applicationNumber} · The applicant sees this message word for word.`}
        width="max-w-2xl"
        dismissible={!busy}
      >
        <div className="space-y-4 p-4 sm:p-5">
          {canAct && !closed && (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs font-semibold text-ink">
                  {decision?.clarificationDraftBody ? 'Suggested clarification' : 'New request'}
                </span>
                {decision?.clarificationDraftBody && (
                  <Button
                    size="sm"
                    variant="outline"
                    leftIcon={<Wand2 size={12} />}
                    onClick={() => {
                      setTitle(decision.clarificationDraftTitle || title)
                      setBody(decision.clarificationDraftBody)
                      setSelected(new Set(clarifiable.map((i) => i.key)))
                    }}
                  >
                    Use suggested text
                  </Button>
                )}
              </div>

              {clarifiable.length > 0 && (
                <fieldset className="rounded-[var(--radius-md)] border border-border bg-[#FAFAF9] p-2">
                  <legend className="px-1 text-[11px] font-semibold text-ink">
                    Findings covered ({chosen.length} of {clarifiable.length})
                  </legend>
                  <ul className="max-h-40 space-y-1 overflow-y-auto pr-1">
                    {clarifiable.map((i) => (
                      <li key={i.key}>
                        <label className="flex cursor-pointer items-start gap-1.5 text-xs text-ink-secondary">
                          <input
                            type="checkbox"
                            className="mt-0.5 rounded"
                            checked={selected.has(i.key)}
                            onChange={() => toggle(i.key)}
                          />
                          <span className="min-w-0">
                            <span className="font-medium text-ink">{i.title}</span>
                            {i.documentName && <span className="text-ink-muted"> · {i.documentName}</span>}
                          </span>
                        </label>
                      </li>
                    ))}
                  </ul>
                </fieldset>
              )}

              <div>
                <label className="mb-1 block text-[11px] font-medium text-ink-muted">Request Title</label>
                <Input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Title"
                  aria-label="Clarification title"
                />
              </div>

              <div>
                <label className="mb-1 block text-[11px] font-medium text-ink-muted">Instructions for applicant</label>
                <Textarea
                  rows={6}
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  placeholder="Tell the applicant exactly what to correct and which document it is in…"
                  aria-label="Clarification details"
                />
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  size="sm"
                  leftIcon={<AlertTriangle size={13} />}
                  disabled={busy || body.trim().length < 5 || title.trim().length < 3}
                  onClick={() =>
                    void act(
                      () =>
                        api.requestClarification(role, detail.id, {
                          title: title.trim(),
                          description: body.trim(),
                          finding_ids: chosenFindingIds,
                        }),
                      'Clarification sent. The application is now waiting for the applicant.',
                      () => {
                        setBody('')
                        setSelected(new Set())
                        setShowPreview(false)
                        closeDialog()
                      },
                    )
                  }
                >
                  Send clarification request
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={body.trim().length < 5 || title.trim().length < 3}
                  onClick={() => setShowPreview((v) => !v)}
                >
                  {showPreview ? 'Hide preview' : 'Preview what the applicant sees'}
                </Button>
              </div>

              {showPreview && (
                <div
                  aria-label="Applicant preview"
                  className="rounded-[var(--radius-md)] border border-dashed border-border bg-[#FBFBFA] p-3 text-xs"
                >
                  <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-ink-muted">
                    Applicant View Preview
                  </div>
                  <p className="font-semibold text-ink">{title.trim() || 'Clarification required'}</p>
                  <p className="mt-1 whitespace-pre-wrap text-ink-secondary">{body.trim()}</p>
                </div>
              )}
            </div>
          )}

          <div className="space-y-2.5 border-t border-border pt-4">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-semibold text-ink">Clarification history</h4>
              <span className="text-[11px] text-ink-muted">
                {(decision?.clarificationRequests ?? []).length} recorded
              </span>
            </div>
            {(decision?.clarificationRequests ?? []).length === 0 ? (
              <p className="rounded-[var(--radius-md)] border border-border bg-[#FAFAF9] p-3 text-center text-xs text-ink-muted">
                No clarification has been requested.
              </p>
            ) : (
              <div className="max-h-48 space-y-2 overflow-y-auto">
                {decision?.clarificationRequests.map((c) => (
                  <div key={c.id} className="rounded-[var(--radius-md)] border border-border bg-white p-3 text-xs">
                    <div className="flex items-start justify-between gap-2">
                      <span className="font-semibold text-ink">{c.title}</span>
                      <Badge tone={c.status === 'open' ? 'warning' : c.status === 'responded' ? 'info' : 'neutral'}>
                        {c.status}
                      </Badge>
                    </div>
                    <button
                      type="button"
                      onClick={() => setActiveHistoryItem(c)}
                      className="mt-2 text-[11px] font-medium text-brand hover:underline"
                    >
                      View details →
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </Dialog>

      {/* ── Notes dialog ── */}
      <Dialog
        open={dialog === 'notes'}
        onClose={closeDialog}
        title="Internal notes"
        subtitle={`Application ${detail.applicationNumber} · Not visible to the applicant`}
        width="max-w-xl"
        dismissible={!busy}
      >
        <div className="space-y-3.5 p-4 sm:p-5">
          {canAct && !closed && (
            <div className="space-y-2 rounded-[var(--radius-md)] border border-border bg-white p-3">
              <label className="block text-[11px] font-medium text-ink-muted">Add note</label>
              <Textarea
                rows={3}
                placeholder="Add an internal note…"
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
              <Button
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
            </div>
          )}

          <ul className="max-h-72 space-y-2 overflow-y-auto">
            {detail.reviewNotes.map((n) => (
              <li key={n.id} className="rounded-[var(--radius-md)] border border-border bg-white p-3 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-ink">
                    {n.author} <span className="font-normal text-ink-muted">({n.role})</span>
                  </span>
                  <span className="text-[10px] text-ink-muted">{formatDateTime(n.createdAt)}</span>
                </div>
                <p className="mt-1.5 whitespace-pre-line leading-relaxed text-ink-secondary">{n.content}</p>
              </li>
            ))}
            {detail.reviewNotes.length === 0 && (
              <li className="rounded-[var(--radius-md)] border border-border bg-[#FAFAF9] p-4 text-center text-xs text-ink-muted">
                No notes recorded yet.
              </li>
            )}
          </ul>
        </div>
      </Dialog>

      {/* ── Audit dialog ── */}
      <Dialog
        open={dialog === 'audit'}
        onClose={closeDialog}
        title="Audit trail"
        subtitle={`Application ${detail.applicationNumber}`}
        width="max-w-xl"
      >
        <div className="p-4 sm:p-5">
          <ul className="max-h-[60vh] space-y-2 overflow-y-auto">
            {detail.auditEvents.map((ev) => (
              <li key={ev.id} className="rounded-[var(--radius-md)] border border-border bg-white p-2.5 text-xs">
                <div className="flex items-start justify-between gap-2">
                  <span className="font-mono text-[11px] font-medium text-ink">{ev.action}</span>
                  <span className="shrink-0 text-[10px] text-ink-muted">{formatDateTime(ev.timestamp)}</span>
                </div>
                <div className="mt-1 break-words text-[11px] leading-relaxed text-ink-secondary">{ev.detail}</div>
                <div className="mt-1.5 text-[10px] text-ink-muted">By: {ev.actor}</div>
              </li>
            ))}
            {detail.auditEvents.length === 0 && (
              <li className="rounded-[var(--radius-md)] border border-border bg-[#FAFAF9] p-4 text-center text-xs text-ink-muted">
                No audit events recorded yet.
              </li>
            )}
          </ul>
        </div>
      </Dialog>

      <Dialog
        open={!!activeHistoryItem}
        onClose={() => setActiveHistoryItem(null)}
        title={activeHistoryItem?.title ?? 'Clarification details'}
        subtitle={`Status: ${activeHistoryItem?.status ?? ''}`}
        width="max-w-2xl"
      >
        {activeHistoryItem && (
          <div className="space-y-4 p-4 text-sm sm:p-6">
            <div>
              <h4 className="mb-1 text-xs font-semibold uppercase tracking-wider text-ink-muted">
                Instructions sent to applicant
              </h4>
              {rowsFromOfficerText(activeHistoryItem.description).length > 0 ? (
                <div className="my-2 overflow-x-auto">
                  <CorrectionTable rows={rowsFromOfficerText(activeHistoryItem.description)} empty="" />
                </div>
              ) : (
                <p className="whitespace-pre-wrap rounded border border-border bg-[#FAFAF9] p-3 text-xs text-ink">
                  {activeHistoryItem.description}
                </p>
              )}
            </div>
            <div>
              <h4 className="mb-1 text-xs font-semibold uppercase tracking-wider text-ink-muted">
                Applicant reply
              </h4>
              {activeHistoryItem.applicantResponse ? (
                <div className="rounded border border-[#CFDAD2] bg-[#F4F8F5] p-3 text-xs leading-relaxed text-ink">
                  {activeHistoryItem.applicantResponse}
                </div>
              ) : (
                <p className="text-xs italic text-ink-muted">The applicant has not yet replied.</p>
              )}
            </div>
          </div>
        )}
      </Dialog>
    </div>
  )
}

function ActionButton({
  icon: Icon,
  label,
  hint,
  badge,
  onClick,
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>
  label: string
  hint: string
  badge?: number
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center gap-2 rounded-lg border border-border bg-white px-2 py-1.5 text-left transition-colors hover:border-border-strong hover:bg-[#FAFAF9]"
    >
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-[#F5F5F4] text-ink">
        <Icon size={12} />
      </span>
      <span className="min-w-0 flex-1 leading-tight">
        <span className="flex items-center gap-1.5">
          <span className="truncate text-[12px] font-semibold text-ink">{label}</span>
          {badge != null && badge > 0 && (
            <span className="rounded-full bg-[#111111] px-1 py-px text-[9px] font-semibold text-white">
              {badge}
            </span>
          )}
        </span>
        <span className="block truncate text-[10px] text-ink-muted">{hint}</span>
      </span>
      <ChevronRight size={12} className="shrink-0 text-ink-muted" aria-hidden />
    </button>
  )
}
