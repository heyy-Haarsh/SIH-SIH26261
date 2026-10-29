import { useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  FileCheck,
  FileText,
  History,
  Maximize2,
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
  onRequestClarificationDrawer?: () => void
}

type TabKey = 'decision' | 'clarify' | 'notes' | 'audit'

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

  // Smart initial tab: if a clarification draft is ready to send and not yet closed, open Clarify tab;
  // otherwise default to Decision tab.
  const [activeTab, setActiveTab] = useState<TabKey>(() => {
    if (decision?.clarificationDraftBody && !decision?.finalDecision && !closed) {
      return 'clarify'
    }
    return 'decision'
  })

  const [note, setNote] = useState('')
  const [title, setTitle] = useState('Clarification required')
  const [body, setBody] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ tone: 'ok' | 'error'; text: string } | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [showPreview, setShowPreview] = useState(false)
  const [showClarifyModal, setShowClarifyModal] = useState(false)
  const [activeHistoryItem, setActiveHistoryItem] = useState<{
    id: string
    title: string
    status: string
    description?: string
    applicantResponse?: string | null
    createdAt?: string
  } | null>(null)

  // Every unresolved issue backed by a finding can be covered by one clarification request.
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

  const tabs: Array<{ id: TabKey; label: string; icon: React.ComponentType<{ size?: number }>; badge?: number }> = [
    { id: 'decision', label: 'Decision', icon: FileCheck },
    { id: 'clarify', label: 'Clarify', icon: AlertTriangle, badge: openClarifs || undefined },
    { id: 'notes', label: 'Notes', icon: FileText, badge: notesCount || undefined },
    { id: 'audit', label: 'Audit', icon: History, badge: auditCount || undefined },
  ]

  // Shared Clarification Form (used inline in Clarify tab and optionally in popup Dialog)
  const renderClarificationComposer = (isModal = false) => (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-semibold text-ink">
          {decision?.clarificationDraftBody ? 'Suggested clarification' : 'New request'}
        </span>
        <div className="flex items-center gap-1.5">
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
          {!isModal && (
            <Button
              size="sm"
              variant="ghost"
              leftIcon={<Maximize2 size={12} />}
              onClick={() => {
                if (onRequestClarificationDrawer) {
                  onRequestClarificationDrawer()
                } else {
                  setShowClarifyModal(true)
                }
              }}
              title="Open full popup composer"
            >
              Popup
            </Button>
          )}
        </div>
      </div>

      {clarifiable.length > 0 && (
        <fieldset className="rounded-[var(--radius-md)] border border-border bg-[#FAFAF9] p-2">
          <legend className="px-1 text-[11px] font-semibold text-ink">
            Findings covered ({chosen.length} of {clarifiable.length})
          </legend>
          <ul className="max-h-32 space-y-1 overflow-y-auto pr-1">
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
          rows={isModal ? 6 : 4}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Tell the applicant exactly what to correct and which document it is in…"
          aria-label="Clarification details"
        />
        <p className="mt-1 text-[10px] text-ink-muted leading-relaxed">
          The applicant sees this text word for word. Plain language ensures quick corrections.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2 pt-1">
        <Button
          size="sm"
          variant="outline"
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
                setShowClarifyModal(false)
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
          <div className="text-[10px] font-semibold uppercase tracking-wider text-ink-muted mb-1">
            Applicant View Preview
          </div>
          <p className="font-semibold text-ink">{title.trim() || 'Clarification required'}</p>
          <p className="mt-1 whitespace-pre-wrap text-ink-secondary">{body.trim()}</p>
          {chosen.length > 0 && (
            <ul className="mt-2 list-disc space-y-0.5 pl-4 text-ink-secondary">
              {chosen.map((i) => (
                <li key={i.key}>
                  {i.documentName ? `${i.documentName}: ` : ''}
                  {i.title}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* ── Top Tabs Bar ── */}
      <div
        className="flex shrink-0 border-b border-border bg-[#FAFAF9] px-2 pt-1 gap-1 overflow-x-auto"
        role="tablist"
      >
        {tabs.map((t) => {
          const Icon = t.icon
          const isActive = activeTab === t.id
          return (
            <button
              key={t.id}
              role="tab"
              aria-selected={isActive}
              onClick={() => setActiveTab(t.id)}
              className={`flex items-center gap-1.5 px-3 py-2 text-xs transition-colors whitespace-nowrap border-b-2 ${
                isActive
                  ? 'border-[#111111] text-[#111111] font-semibold bg-white rounded-t'
                  : 'border-transparent text-ink-muted hover:text-ink hover:bg-white/50'
              }`}
            >
              <Icon size={13} />
              <span>{t.label}</span>
              {t.badge !== undefined && t.badge > 0 && (
                <span
                  className={`rounded-full px-1.5 py-0.2 text-[10px] font-semibold ${
                    isActive ? 'bg-[#111111] text-white' : 'bg-[#EAE8E2] text-ink-secondary'
                  }`}
                >
                  {t.badge}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* ── Notification Banner (if any) ── */}
      {msg && (
        <div
          role={msg.tone === 'error' ? 'alert' : 'status'}
          className={`mx-3 mt-3 rounded-[var(--radius-md)] border px-3 py-2 text-xs ${
            msg.tone === 'error'
              ? 'border-[#e2cbc8] bg-status-failed-bg text-status-failed'
              : 'border-border bg-surface text-ink-secondary'
          }`}
        >
          {msg.text}
        </div>
      )}

      {/* ── Scrollable Tab Content ── */}
      <div className="flex-1 overflow-y-auto p-3.5 space-y-4">
        {/* ══ TAB 1: DECISION / RECOMMENDATION ══ */}
        {activeTab === 'decision' && (
          <div className="space-y-4">
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
                  <p className="mt-2 text-xs text-ink-secondary">
                    {decision.finalDecisionReason.split('\n')[0]}
                  </p>
                )}
              </div>
            )}

            {(() => {
              const rows =
                decision?.mustCorrectRows && decision.mustCorrectRows.length > 0
                  ? decision.mustCorrectRows
                  : decision?.mustCorrect?.length
                    ? rowsFromOfficerText(decision.mustCorrect.join('\n'))
                    : rowsFromOfficerText(decision?.finalDecisionReason)
              if (!rows.length) return null
              return (
                <div className="rounded-[var(--radius-md)] border border-border p-3">
                  <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-ink">
                    <AlertTriangle size={14} className="text-status-warning" /> What the applicant must correct
                  </div>
                  <div className="overflow-x-auto text-xs">
                    <CorrectionTable rows={rows} />
                  </div>
                </div>
              )
            })()}

            {canAct && !closed && (
              <div className="rounded-[var(--radius-md)] border border-border bg-white p-3.5 space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-xs font-semibold text-ink">Final recommendation</div>
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
                <p className="text-[11px] text-ink-muted leading-relaxed">
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
            )}

            {canAct && !closed && (
              <div className="rounded-[var(--radius-md)] border border-dashed border-border p-3 text-xs text-ink-secondary bg-[#FAFAF9]">
                <div className="font-medium text-ink">Need corrections first?</div>
                <p className="mt-1 text-[11px] text-ink-muted">
                  You can send clarification requests to give the applicant an opportunity to correct documents.
                </p>
                <Button
                  className="mt-2"
                  size="sm"
                  variant="outline"
                  leftIcon={<MessageSquare size={13} />}
                  onClick={() => setActiveTab('clarify')}
                >
                  Go to Clarification tab →
                </Button>
              </div>
            )}
          </div>
        )}

        {/* ══ TAB 2: CLARIFICATION ══ */}
        {activeTab === 'clarify' && (
          <div className="space-y-4">
            {canAct && !closed && (
              <div className="rounded-[var(--radius-md)] border border-border bg-white p-3.5">
                <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-muted">
                  Request clarification
                </div>
                {renderClarificationComposer(false)}
              </div>
            )}

            {/* Clarification History */}
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-semibold text-ink">Clarification history</h4>
                <span className="text-[11px] text-ink-muted">
                  {(decision?.clarificationRequests ?? []).length} recorded
                </span>
              </div>

              {(decision?.clarificationRequests ?? []).length === 0 ? (
                <div className="rounded-[var(--radius-md)] border border-border bg-[#FAFAF9] p-4 text-center text-xs text-ink-muted">
                  No clarification has been requested.
                </div>
              ) : (
                <div className="space-y-2.5">
                  {decision?.clarificationRequests.map((c) => (
                    <div
                      key={c.id}
                      className="rounded-[var(--radius-md)] border border-border bg-white p-3 transition-colors hover:border-border-strong text-xs"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="font-semibold text-ink">{c.title}</span>
                        <Badge
                          tone={c.status === 'open' ? 'warning' : c.status === 'responded' ? 'info' : 'neutral'}
                        >
                          {c.status}
                        </Badge>
                      </div>

                      <div className="mt-2 text-ink-secondary">
                        <div className="font-medium text-[11px] text-ink-muted uppercase tracking-wider mb-1">
                          Request Description
                        </div>
                        {rowsFromOfficerText(c.description).length > 0 ? (
                          <div className="overflow-x-auto my-1">
                            <CorrectionTable rows={rowsFromOfficerText(c.description)} empty="" />
                          </div>
                        ) : (
                          <p className="whitespace-pre-wrap text-[11px] text-ink-secondary">{c.description}</p>
                        )}
                      </div>

                      {c.applicantResponse ? (
                        <div className="mt-2.5 rounded bg-[#F7F9F8] border border-[#E3ECE6] p-2">
                          <span className="font-semibold text-[11px] text-[#2E7D52]">Applicant Reply:</span>
                          <p className="mt-0.5 text-xs text-ink">{c.applicantResponse}</p>
                        </div>
                      ) : (
                        <div className="mt-2 text-[11px] text-ink-muted italic">
                          Awaiting applicant response…
                        </div>
                      )}

                      <div className="mt-2 flex justify-end">
                        <button
                          type="button"
                          onClick={() => setActiveHistoryItem(c)}
                          className="text-[11px] text-brand hover:underline font-medium"
                        >
                          View in popup →
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ══ TAB 3: REVIEWER NOTES ══ */}
        {activeTab === 'notes' && (
          <div className="space-y-3.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-ink">
                <MessageSquare size={14} /> Reviewer notes (internal)
              </div>
              <span className="text-[11px] text-ink-muted">{detail.reviewNotes.length} notes</span>
            </div>

            {canAct && !closed && (
              <div className="rounded-[var(--radius-md)] border border-border bg-white p-3 space-y-2">
                <label className="block text-[11px] font-medium text-ink-muted">Add Note</label>
                <Textarea
                  rows={2}
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

            <ul className="space-y-2">
              {detail.reviewNotes.map((n) => (
                <li key={n.id} className="rounded-[var(--radius-md)] border border-border bg-white p-3 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-ink">
                      {n.author} <span className="font-normal text-ink-muted">({n.role})</span>
                    </span>
                    <span className="text-[10px] text-ink-muted">{formatDateTime(n.createdAt)}</span>
                  </div>
                  {rowsFromOfficerText(n.content).length > 1 ? (
                    <div className="mt-2 overflow-x-auto">
                      <CorrectionTable rows={rowsFromOfficerText(n.content)} />
                    </div>
                  ) : (
                    <p className="mt-1.5 whitespace-pre-line text-ink-secondary leading-relaxed">
                      {n.content}
                    </p>
                  )}
                </li>
              ))}
              {detail.reviewNotes.length === 0 && (
                <li className="rounded-[var(--radius-md)] border border-border bg-[#FAFAF9] p-4 text-center text-xs text-ink-muted">
                  No notes recorded yet.
                </li>
              )}
            </ul>
          </div>
        )}

        {/* ══ TAB 4: AUDIT TRAIL ══ */}
        {activeTab === 'audit' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-ink">
                <History size={14} /> Audit history
              </div>
              <span className="text-[11px] text-ink-muted">{detail.auditEvents.length} events</span>
            </div>

            <ul className="space-y-2">
              {detail.auditEvents.map((ev) => (
                <li
                  key={ev.id}
                  className="rounded-[var(--radius-md)] border border-border bg-white p-2.5 text-xs transition-colors"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-medium text-ink font-mono text-[11px]">{ev.action}</span>
                    <span className="text-[10px] text-ink-muted shrink-0">{formatDateTime(ev.timestamp)}</span>
                  </div>
                  <div className="mt-1 text-ink-secondary text-[11px] leading-relaxed break-words">
                    {ev.detail}
                  </div>
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
        )}
      </div>

      {/* ── POPUP MODAL: Clarification Composer (Spacious Dialog) ── */}
      <Dialog
        open={showClarifyModal}
        onClose={() => setShowClarifyModal(false)}
        title="Request Clarification"
        subtitle={`Application ${detail.applicationNumber} · The applicant sees this message word for word.`}
        width="max-w-2xl"
      >
        <div className="p-4 sm:p-6">
          {renderClarificationComposer(true)}
        </div>
      </Dialog>

      {/* ── POPUP MODAL: Clarification History Item Details ── */}
      <Dialog
        open={!!activeHistoryItem}
        onClose={() => setActiveHistoryItem(null)}
        title={activeHistoryItem?.title ?? 'Clarification Details'}
        subtitle={`Status: ${activeHistoryItem?.status ?? ''}`}
        width="max-w-2xl"
      >
        {activeHistoryItem && (
          <div className="p-4 sm:p-6 space-y-4 text-sm">
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-ink-muted mb-1">
                Instructions Sent to Applicant
              </h4>
              {rowsFromOfficerText(activeHistoryItem.description).length > 0 ? (
                <div className="overflow-x-auto my-2">
                  <CorrectionTable rows={rowsFromOfficerText(activeHistoryItem.description)} empty="" />
                </div>
              ) : (
                <p className="whitespace-pre-wrap rounded border border-border bg-[#FAFAF9] p-3 text-xs text-ink">
                  {activeHistoryItem.description}
                </p>
              )}
            </div>

            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-ink-muted mb-1">
                Applicant Reply
              </h4>
              {activeHistoryItem.applicantResponse ? (
                <div className="rounded border border-[#CFDAD2] bg-[#F4F8F5] p-3 text-xs text-ink leading-relaxed">
                  {activeHistoryItem.applicantResponse}
                </div>
              ) : (
                <p className="text-xs text-ink-muted italic">The applicant has not yet replied to this request.</p>
              )}
            </div>
          </div>
        )}
      </Dialog>
    </div>
  )
}
