import { useState } from 'react'
import {
  AlertTriangle,
  ArrowUpRight,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
} from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { api } from '@/services/api'
import type { DocumentIssueGroup, ScrutinyIssue, ScrutinyReview } from '@/types'
import { HandbookBadge } from './HandbookBadge'
import { ResolveControl } from './ResolveControl'
import {
  LAYER_LABEL,
  SEVERITY_BAR,
  SEVERITY_LABEL,
  SEVERITY_TONE,
  STATUS_LABEL,
  type Resolution,
} from './scrutinyUi'

interface Props {
  review: ScrutinyReview
  role: string
  onOpenDocument: (documentId: string) => void
  onChanged: () => Promise<unknown> | void
}

export function IssuesPanel({ review, role, onOpenDocument, onChanged }: Props) {
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
      {/* Summary bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <p className="text-ink-secondary">
          <span className="font-semibold text-ink">{review.openIssueCount} open issues</span>
          {review.resolvedIssueCount > 0 &&
            ` · ${review.resolvedIssueCount} resolved`}
        </p>
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

      {/* Missing documents */}
      {review.missingDocuments.length > 0 && (
        <div className="rounded-[var(--radius-md)] border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
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

      {/* Issue groups */}
      {groups.map((g) => (
        <GroupSection
          key={`${g.scope}-${g.documentId ?? g.documentName}`}
          group={g}
          canResolve={canResolve}
          role={role}
          onOpenDocument={onOpenDocument}
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

// ── Group ─────────────────────────────────────────────────────────────────────

function GroupSection({
  group,
  canResolve,
  role,
  onOpenDocument,
  onChanged,
}: {
  group: DocumentIssueGroup
  canResolve: boolean
  role: string
  onOpenDocument: (id: string) => void
  onChanged: () => Promise<unknown> | void
}) {
  return (
    <section className="overflow-hidden rounded-[var(--radius-md)] border border-border bg-white shadow-[var(--shadow-card)]">
      {/* Group header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-surface px-4 py-2">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
          {group.documentName}
          {group.openCount > 0 && (
            <Badge tone={group.highestSeverity ? SEVERITY_TONE[group.highestSeverity] : 'neutral'}>
              {group.openCount} open
            </Badge>
          )}
        </h3>
        {group.documentId && (
          <Button
            size="sm"
            variant="outline"
            leftIcon={<ArrowUpRight size={13} />}
            onClick={() => onOpenDocument(group.documentId as string)}
          >
            Preview &amp; report
          </Button>
        )}
      </div>

      {/* Issues list */}
      <ul className="divide-y divide-border">
        {group.issues.map((issue) => (
          <IssueRow
            key={issue.key}
            issue={issue}
            canResolve={canResolve}
            role={role}
            onOpenDocument={onOpenDocument}
            onChanged={onChanged}
          />
        ))}
      </ul>
    </section>
  )
}

// ── Issue row (accordion) ──────────────────────────────────────────────────────

function IssueRow({
  issue,
  canResolve,
  role,
  onOpenDocument,
  onChanged,
}: {
  issue: ScrutinyIssue
  canResolve: boolean
  role: string
  onOpenDocument: (id: string) => void
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
    issue.explanation ||
    issue.applicantAction ||
    issue.relatedDocuments.length > 0 ||
    issue.evidence.length > 0 ||
    resolvable ||
    issue.handbook.status === 'verified'

  async function resolve(status: Resolution, reason: string) {
    for (const id of issue.findingIds) await api.resolveFinding(role, id, { status, reason })
    for (const id of issue.checkIds) await api.resolveDocVerificationCheck(role, id, { status, reason })
    await onChanged()
    setShowResolve(false)
  }

  return (
    <li className={`${SEVERITY_BAR[issue.severity]} border-l-4 ${isOpen ? '' : 'opacity-70'}`}>
      {/* ── Collapsed summary row – always visible ── */}
      <button
        type="button"
        aria-expanded={expanded}
        disabled={!hasDetails}
        onClick={() => hasDetails && setExpanded((v) => !v)}
        className={`flex w-full items-center gap-2.5 px-4 py-2.5 text-left transition-colors ${
          hasDetails ? 'hover:bg-surface-muted' : ''
        }`}
      >
        {/* Chevron */}
        <span className="shrink-0 text-ink-muted">
          {hasDetails ? (
            expanded ? (
              <ChevronDown size={13} />
            ) : (
              <ChevronRight size={13} />
            )
          ) : (
            <span className="inline-block h-[13px] w-[13px]" />
          )}
        </span>

        {/* Severity + title */}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={SEVERITY_TONE[issue.severity]}>{SEVERITY_LABEL[issue.severity]}</Badge>
            {!isOpen && (
              <Badge tone="neutral">{STATUS_LABEL[issue.status] ?? issue.status}</Badge>
            )}
            <span className="text-sm font-medium text-ink">{issue.title}</span>
            {issue.occurrences > 1 && (
              <span className="text-[11px] text-ink-muted">
                seen by {issue.occurrences} checks
              </span>
            )}
          </div>
        </div>

        {/* Right-side meta */}
        <div className="flex shrink-0 items-center gap-2">
          {issue.handbook.status === 'verified' && (
            <BookOpen size={13} className="text-brand" aria-label="Verified handbook reference" />
          )}
          <span className="rounded border border-border bg-surface px-1.5 py-0.5 text-[10px] text-ink-muted">
            {LAYER_LABEL[issue.layer] ?? issue.layer}
          </span>
        </div>
      </button>

      {/* ── Expanded detail panel ── */}
      {expanded && hasDetails && (
        <div className="space-y-3 border-t border-border bg-surface-muted px-4 py-3">
          {(issue.explanation || issue.relatedDocuments.length > 0 || issue.evidence.length > 0) && (
            <div>
              <h4 className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                What we found
              </h4>
              {issue.explanation && (
                <p className="mt-1 text-sm text-ink-secondary">{issue.explanation}</p>
              )}
              {issue.relatedDocuments.length > 0 && (
                <p className="mt-1.5 text-xs text-ink-muted">
                  <span className="font-medium text-ink-secondary">Involves: </span>
                  {issue.relatedDocuments.map((d, i) => (
                    <span key={d.id}>
                      {i > 0 && ', '}
                      <button
                        type="button"
                        className="text-brand underline hover:text-brand-dark"
                        onClick={() => onOpenDocument(d.id)}
                      >
                        {d.name}
                      </button>
                    </span>
                  ))}
                </p>
              )}
              {issue.evidence.length > 0 && (
                <details className="mt-1.5">
                  <summary className="cursor-pointer text-xs font-medium text-ink-secondary">
                    Evidence ({issue.evidence.length})
                  </summary>
                  <ul className="mt-1 space-y-0.5 text-xs text-ink-muted">
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
            </div>
          )}

          {(issue.applicantAction || issue.handbook.status === 'verified') && (
            <div>
              <h4 className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                For the applicant
              </h4>
              {issue.applicantAction && (
                <p className="mt-1 flex items-start gap-1.5 text-sm text-ink-secondary">
                  <AlertTriangle size={14} className="mt-0.5 shrink-0 text-amber-600" />
                  <span>{issue.applicantAction}</span>
                </p>
              )}
              {issue.handbook.status === 'verified' && (
                <div className="mt-1.5">
                  <HandbookBadge reference={issue.handbook} />
                </div>
              )}
            </div>
          )}

          {resolvable && !showResolve && (
            <button
              type="button"
              className="text-[11px] font-medium text-accent underline-offset-2 hover:underline"
              onClick={() => setShowResolve(true)}
            >
              Resolve…
            </button>
          )}
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
        </div>
      )}
    </li>
  )
}
