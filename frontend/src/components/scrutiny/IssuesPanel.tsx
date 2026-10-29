import { useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  FileText,
  CircleAlert,
} from 'lucide-react'
import { EmptyState } from '@/components/ui/EmptyState'
import { api } from '@/services/api'
import type { DocumentIssueGroup, ScrutinyIssue, ScrutinyReview } from '@/types'
import { HandbookBadge } from './HandbookBadge'
import { FindingLifecycleControls } from './FindingLifecycle'
import { ResolveControl } from './ResolveControl'
import {
  LAYER_LABEL,
  SEVERITY_LABEL,
  type Resolution,
} from './scrutinyUi'

interface Props {
  review: ScrutinyReview
  role: string
  onOpenDocument: (documentId: string) => void
  /** Opens the officer clarification composer with these issue keys pre-selected. */
  onAskClarification?: (issueKeys: string[]) => void
  onChanged: () => Promise<unknown> | void
}

export function IssuesPanel({ review, role, onOpenDocument, onAskClarification, onChanged }: Props) {
  const [showResolved, setShowResolved] = useState(false)
  const canResolve = role === 'officer' || role === 'regional_officer'

  const groups = review.issueGroups
    .map((g) => ({
      ...g,
      issues: g.issues.filter((i) => showResolved || i.status === 'open'),
    }))
    .filter((g) => g.issues.length > 0)

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <p className="text-ink-secondary">
          <span className="font-semibold text-ink">{review.openIssueCount} open issues</span>
          {review.resolvedIssueCount > 0 && ` · ${review.resolvedIssueCount} resolved`}
        </p>
        <div className="flex flex-wrap items-center gap-3">
          {canResolve && onAskClarification && review.openIssueCount > 0 && (
            <button
              type="button"
              className="font-semibold text-[#1D4ED8] hover:underline"
              onClick={() =>
                onAskClarification(
                  groups.flatMap((g) =>
                    g.issues
                      .filter((i) => i.status === 'open' && i.findingIds.length > 0 && i.severity !== 'info')
                      .map((i) => i.key),
                  ),
                )
              }
            >
              Request clarification →
            </button>
          )}
          <label className="flex cursor-pointer items-center gap-1.5 text-ink-secondary">
            <input
              type="checkbox"
              checked={showResolved}
              onChange={(e) => setShowResolved(e.target.checked)}
              className="accent-brand"
            />
            Show resolved
          </label>
        </div>
      </div>

      {review.missingDocuments.length > 0 && (
        <div className="rounded-lg border border-[#e3d8bd] bg-status-warning-bg px-3 py-2 text-xs text-status-warning">
          <span className="font-semibold">Not uploaded yet: </span>
          {review.missingDocuments
            .map((m) => `${m.name}${m.mandatory ? '' : ' (optional)'}`)
            .join(', ')}
        </div>
      )}

      {groups.length === 0 && (
        <EmptyState
          icon={CheckCircle2}
          title={review.validationRunId ? 'No open issues' : 'Validation has not run yet'}
          description={
            review.validationRunId
              ? 'The latest validation run recorded no open issues. This is not proof that the documents are authentic — review the Authenticity tab and the originals.'
              : 'Upload a document or run validation to see issues.'
          }
        />
      )}

      {groups.map((g) => (
        <GroupSection
          key={`${g.scope}-${g.documentId ?? g.documentName}`}
          group={g}
          canResolve={canResolve}
          role={role}
          onOpenDocument={onOpenDocument}
          onAskClarification={onAskClarification}
          onChanged={onChanged}
        />
      ))}

      {review.historicalFindingCount > 0 && (
        <p className="text-[11px] text-ink-muted">
          {review.historicalFindingCount} finding(s) from earlier validation runs are kept as
          history and are not counted here.
        </p>
      )}
    </div>
  )
}

function GroupSection({
  group,
  canResolve,
  role,
  onOpenDocument,
  onAskClarification,
  onChanged,
}: {
  group: DocumentIssueGroup
  canResolve: boolean
  role: string
  onOpenDocument: (id: string) => void
  onAskClarification?: (issueKeys: string[]) => void
  onChanged: () => Promise<unknown> | void
}) {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <section className="overflow-hidden rounded-xl border border-border bg-white">
      <button
        type="button"
        className="flex w-full items-center gap-2.5 px-4 py-3 text-left hover:bg-[#FAFAFA]"
        onClick={() => setCollapsed((v) => !v)}
        aria-expanded={!collapsed}
      >
        <FileText size={15} className="shrink-0 text-ink-muted" />
        <h3 className="min-w-0 flex-1 truncate text-sm font-semibold text-ink">
          {group.documentName}
        </h3>
        {group.openCount > 0 && (
          <span className="shrink-0 rounded-md bg-[#FEF2F2] px-2 py-0.5 text-[11px] font-semibold text-[#991B1B]">
            {group.openCount} open issue{group.openCount === 1 ? '' : 's'}
          </span>
        )}
        {collapsed ? (
          <ChevronRight size={14} className="shrink-0 text-ink-muted" />
        ) : (
          <ChevronDown size={14} className="shrink-0 text-ink-muted" />
        )}
      </button>

      {!collapsed && (
        <ol className="border-t border-border divide-y divide-border">
          {group.issues.map((issue, idx) => (
            <IssueRow
              key={issue.key}
              index={idx + 1}
              issue={issue}
              canResolve={canResolve}
              role={role}
              onOpenDocument={onOpenDocument}
              onAskClarification={onAskClarification}
              onChanged={onChanged}
            />
          ))}
        </ol>
      )}
    </section>
  )
}

function StatusPill({ severity, status }: { severity: ScrutinyIssue['severity']; status: string }) {
  const isOpen = status === 'open'
  if (!isOpen) {
    return (
      <span className="inline-flex items-center gap-1 rounded-md border border-border bg-[#F5F5F5] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-muted">
        {status.replace(/_/g, ' ')}
      </span>
    )
  }
  if (severity === 'failed') {
    return (
      <span className="inline-flex items-center gap-1 rounded-md bg-[#FEF2F2] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[#991B1B]">
        <CircleAlert size={11} />
        {SEVERITY_LABEL.failed}
      </span>
    )
  }
  if (severity === 'manual_review' || severity === 'warning') {
    return (
      <span className="inline-flex items-center gap-1 rounded-md bg-[#FFFBEB] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[#B45309]">
        <Clock size={11} />
        {severity === 'warning' ? SEVERITY_LABEL.warning : SEVERITY_LABEL.manual_review}
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-md bg-[#EFF6FF] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[#1D4ED8]">
      {SEVERITY_LABEL[severity]}
    </span>
  )
}

function IssueRow({
  index,
  issue,
  canResolve,
  role,
  onOpenDocument,
  onAskClarification,
  onChanged,
}: {
  index: number
  issue: ScrutinyIssue
  canResolve: boolean
  role: string
  onOpenDocument: (id: string) => void
  onAskClarification?: (issueKeys: string[]) => void
  onChanged: () => Promise<unknown> | void
}) {
  const [expanded, setExpanded] = useState(false)
  const [showResolve, setShowResolve] = useState(false)
  const isOpen = issue.status === 'open'

  const resolvable =
    canResolve &&
    isOpen &&
    issue.severity !== 'info' &&
    (issue.findingIds.length > 0 || issue.checkIds.length > 0)

  const hasDetails =
    Boolean(issue.explanation) ||
    Boolean(issue.applicantAction) ||
    issue.relatedDocuments.length > 0 ||
    issue.evidence.length > 0 ||
    resolvable ||
    (canResolve && issue.findingIds.length > 0) ||
    issue.handbook.status === 'verified'

  async function resolve(status: Resolution, reason: string) {
    for (const id of issue.findingIds) await api.resolveFinding(role, id, { status, reason })
    for (const id of issue.checkIds) await api.resolveDocVerificationCheck(role, id, { status, reason })
    await onChanged()
    setShowResolve(false)
  }

  return (
    <li className={isOpen ? '' : 'opacity-70'}>
      <button
        type="button"
        aria-expanded={expanded}
        disabled={!hasDetails}
        onClick={() => hasDetails && setExpanded((v) => !v)}
        className={`flex w-full items-center gap-2.5 px-4 py-2.5 text-left ${
          hasDetails ? 'hover:bg-[#FAFAFA]' : ''
        }`}
      >
        <span className="shrink-0 text-ink-muted">
          {hasDetails ? (
            expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />
          ) : (
            <span className="inline-block h-[13px] w-[13px]" />
          )}
        </span>

        <span className="w-5 shrink-0 text-[12px] font-semibold tabular-nums text-ink-muted">
          {index}.
        </span>

        <StatusPill severity={issue.severity} status={issue.status} />

        <span className="min-w-0 flex-1 truncate text-[13px] font-medium text-ink">
          {issue.title}
        </span>

        <span className="hidden shrink-0 rounded-full bg-[#F3F4F6] px-2 py-0.5 text-[10px] font-medium text-ink-muted sm:inline">
          {LAYER_LABEL[issue.layer] ?? issue.layer}
        </span>
      </button>

      {expanded && hasDetails && (
        <div className="space-y-2.5 border-t border-border bg-[#FAFAFA] px-4 py-3 pl-14">
          {issue.explanation && (
            <p className="text-[13px] leading-relaxed text-ink-secondary">{issue.explanation}</p>
          )}

          {issue.applicantAction && (
            <p className="flex items-start gap-1.5 text-[13px] leading-relaxed text-[#92400E]">
              <AlertTriangle size={14} className="mt-0.5 shrink-0 text-[#B45309]" />
              <span>{issue.applicantAction}</span>
            </p>
          )}

          {issue.handbook.status === 'verified' && (
            <HandbookBadge reference={issue.handbook} />
          )}

          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-3">
              {issue.evidence.length > 0 && (
                <details className="text-xs">
                  <summary className="inline-flex cursor-pointer items-center gap-1 font-medium text-[#1D4ED8]">
                    <FileText size={12} />
                    Evidence ({issue.evidence.length})
                    <ChevronDown size={11} />
                  </summary>
                  <ul className="mt-1.5 space-y-0.5 text-ink-muted">
                    {issue.evidence.map((e, i) => (
                      <li key={`${e.text}-${i}`}>
                        {e.text}
                        {e.documentName ? ` · ${e.documentName}` : ''}
                        {e.pageReference ? ` (${e.pageReference})` : ''}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
              {issue.documentId && (
                <button
                  type="button"
                  className="inline-flex items-center gap-1 text-xs font-medium text-[#1D4ED8] hover:underline"
                  onClick={() => onOpenDocument(issue.documentId!)}
                >
                  View document →
                </button>
              )}
              {issue.relatedDocuments.map((d) => (
                <button
                  key={d.id}
                  type="button"
                  className="text-xs font-medium text-[#1D4ED8] hover:underline"
                  onClick={() => onOpenDocument(d.id)}
                >
                  {d.name}
                </button>
              ))}
            </div>

            <div className="flex flex-wrap items-center gap-3">
              {canResolve &&
                isOpen &&
                onAskClarification &&
                issue.findingIds.length > 0 &&
                issue.severity !== 'info' && (
                  <button
                    type="button"
                    className="text-[12px] font-semibold text-[#1D4ED8] hover:underline"
                    onClick={() => onAskClarification([issue.key])}
                  >
                    Ask applicant →
                  </button>
                )}
              {resolvable && !showResolve && (
                <button
                  type="button"
                  className="text-[12px] font-semibold text-[#C2410C] hover:underline"
                  onClick={() => setShowResolve(true)}
                >
                  Resolve →
                </button>
              )}
            </div>
          </div>

          {resolvable && showResolve && (
            <ResolveControl
              role={role}
              onResolve={resolve}
              draftContext={{
                title: issue.title,
                explanation: issue.explanation,
                applicantAction: issue.applicantAction,
                documentName: issue.documentName,
              }}
            />
          )}

          <FindingLifecycleControls
            issue={issue}
            role={role}
            canAct={canResolve}
            onChanged={onChanged}
          />
        </div>
      )}
    </li>
  )
}
