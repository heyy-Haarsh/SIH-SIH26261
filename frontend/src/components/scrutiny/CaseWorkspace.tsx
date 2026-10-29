import { useMemo, useState } from 'react'
import { Crosshair, FileText } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'
import { useRefreshable } from '@/hooks/useRefreshable'
import { api } from '@/services/api'
import type { DocumentReport, ExtractedField, ScrutinyIssue, ScrutinyReview } from '@/types'
import { DocumentPreview } from './DocumentPreview'
import { FindingLifecycleControls, LIFECYCLE_LABEL } from './FindingLifecycle'
import { HandbookBadge } from './HandbookBadge'
import { ResolveControl } from './ResolveControl'
import { SEVERITY_LABEL, SEVERITY_TONE, type Resolution } from './scrutinyUi'

/** "Page 3", "p. 3", "page: 3" → 3. Returns null when no page is cited. */
export function parsePage(reference?: string | null): number | null {
  const match = /(?:page|pg|p)\.?\s*[:#]?\s*(\d{1,4})/i.exec(reference ?? '')
  if (!match) return null
  const page = Number(match[1])
  return page > 0 ? page : null
}

const humanize = (value?: string | null) =>
  value ? value.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase()) : 'Not run'

interface Props {
  review: ScrutinyReview
  applicationId: string
  role: string
  onChanged: () => Promise<unknown> | void
}

/**
 * Three-panel case workspace: documents + findings on the left, the document itself in the
 * centre, and the selected finding's evidence and lifecycle actions on the right.
 *
 * Selecting a finding opens its document at the page the finding cites. A region is highlighted
 * only when the user picks an extracted field that has real coordinates — a finding never
 * invents a location it does not have.
 */
export function CaseWorkspace({ review, applicationId, role, onChanged }: Props) {
  const canAct = role === 'officer' || role === 'regional_officer'
  const issues = useMemo(() => review.issueGroups.flatMap((g) => g.issues), [review.issueGroups])
  const [showClosed, setShowClosed] = useState(false)
  const [issueKey, setIssueKey] = useState<string | null>(null)
  const [docId, setDocId] = useState<string | null>(review.documents[0]?.id ?? null)
  const [page, setPage] = useState<number | null>(null)
  const [fieldId, setFieldId] = useState<string | null>(null)
  const [resolving, setResolving] = useState(false)

  const shown = issues.filter((i) => showClosed || i.status === 'open')
  const issue = issues.find((i) => i.key === issueKey) ?? null
  const doc = review.documents.find((d) => d.id === docId) ?? null

  const loadReport = useMemo(
    () => (docId ? () => api.getDocumentReport(role, applicationId, docId) : null),
    [role, applicationId, docId],
  )
  const report = useRefreshable<DocumentReport>(loadReport, `ws:${applicationId}:${docId}:${doc?.version}`)
  const fields: ExtractedField[] = report.data?.extractedFields ?? []
  const focused = fields.find((f) => f.id === fieldId) ?? null

  function selectIssue(next: ScrutinyIssue) {
    setIssueKey(next.key)
    setFieldId(null)
    setResolving(false)
    if (next.documentId) setDocId(next.documentId)
    const cited = next.evidence.map((e) => parsePage(e.pageReference)).find((p) => p !== null) ?? null
    setPage(cited)
  }

  function selectDoc(id: string) {
    setDocId(id)
    setIssueKey(null)
    setFieldId(null)
    setPage(null)
  }

  async function resolve(status: Resolution, reason: string) {
    if (!issue) return
    for (const id of issue.findingIds) await api.resolveFinding(role, id, { status, reason })
    for (const id of issue.checkIds) await api.resolveDocVerificationCheck(role, id, { status, reason })
    await onChanged()
    setResolving(false)
  }

  const highlightPage = focused?.bbox ? (focused.pageNumber ?? null) : null
  const viewerPage = focused?.pageNumber ?? page

  return (
    <div
      className="grid gap-3 lg:grid-cols-[260px_minmax(0,1fr)_340px]"
      data-testid="case-workspace"
    >
      {/* ── Left: documents + findings ───────────────────────────────── */}
      <nav
        aria-label="Documents and findings"
        className="space-y-4 rounded-[var(--radius-md)] border border-border bg-white p-3 lg:max-h-[78vh] lg:overflow-y-auto"
      >
        <section>
          <h3 className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
            Documents ({review.documents.length})
          </h3>
          <ul className="mt-1.5 space-y-1">
            {review.documents.map((d) => (
              <li key={d.id}>
                <button
                  type="button"
                  aria-current={d.id === docId}
                  onClick={() => selectDoc(d.id)}
                  className={`flex w-full items-center justify-between gap-2 rounded px-2 py-1.5 text-left text-xs hover:bg-surface-muted ${
                    d.id === docId ? 'bg-brand-soft font-medium text-brand' : 'text-ink-secondary'
                  }`}
                >
                  <span className="min-w-0 truncate">{d.name}</span>
                  {d.openIssueCount > 0 && <Badge tone="failed">{d.openIssueCount}</Badge>}
                </button>
              </li>
            ))}
            {review.missingDocuments.map((m) => (
              <li key={m.code} className="px-2 py-1 text-[11px] text-status-warning">
                Not uploaded: {m.name}
                {m.mandatory ? '' : ' (optional)'}
              </li>
            ))}
          </ul>
        </section>

        <section>
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
              Findings ({review.openIssueCount} open)
            </h3>
            <label className="flex items-center gap-1 text-[11px] text-ink-muted">
              <input
                type="checkbox"
                checked={showClosed}
                onChange={(e) => setShowClosed(e.target.checked)}
              />
              Show closed
            </label>
          </div>
          <ul className="mt-1.5 space-y-1">
            {shown.length === 0 && <li className="px-2 py-1 text-xs text-ink-muted">No open findings.</li>}
            {shown.map((i) => (
              <li key={i.key}>
                <button
                  type="button"
                  aria-current={i.key === issueKey}
                  onClick={() => selectIssue(i)}
                  className={`w-full rounded border-l-4 px-2 py-1.5 text-left text-xs hover:bg-surface-muted ${
                    i.key === issueKey ? 'bg-brand-soft' : ''
                  } ${i.status === 'open' ? 'border-status-failed' : 'border-border opacity-70'}`}
                >
                  <span className="block font-medium text-ink">{i.title}</span>
                  <span className="block text-[10px] text-ink-muted">
                    {i.documentName ?? 'Application-wide'} ·{' '}
                    {LIFECYCLE_LABEL[i.lifecycleStatus ?? 'open'] ?? i.lifecycleStatus}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      </nav>

      {/* ── Centre: the document ─────────────────────────────────────── */}
      <section
        aria-label="Document viewer"
        className="min-w-0 rounded-[var(--radius-md)] border border-border bg-white p-3 lg:max-h-[78vh] lg:overflow-y-auto"
      >
        {!doc ? (
          <EmptyState
            icon={FileText}
            title="Select a document"
            description="Choose a document, or a finding, to open the file here."
          />
        ) : (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="min-w-0">
                <h3 className="truncate text-sm font-semibold text-ink">{doc.name}</h3>
                <p className="text-[11px] text-ink-muted">
                  {doc.fileName} · version {doc.version}
                </p>
              </div>
              {issue && (
                <span className="text-[11px] text-ink-muted" role="status">
                  {page
                    ? `Showing page ${page}, cited by “${issue.title}”.`
                    : `“${issue.title}” does not cite a page.`}
                </span>
              )}
            </div>

            {doc.canPreview ? (
              <DocumentPreview
                role={role}
                documentId={doc.id}
                mimeType={doc.mimeType}
                fileName={doc.fileName}
                version={doc.version}
                highlightPage={viewerPage}
                highlightBBox={highlightPage ? (focused?.bbox ?? null) : null}
                highlightLabel={focused?.fieldName ?? null}
              />
            ) : (
              <p className="rounded border border-dashed border-border p-4 text-center text-xs text-ink-muted">
                This file cannot be previewed in the browser.
              </p>
            )}

            <details className="rounded border border-border bg-surface px-3 py-2">
              <summary className="cursor-pointer text-xs font-medium text-ink">
                Fields read from this document ({fields.length})
              </summary>
              <ul className="mt-2 space-y-1 text-xs">
                {report.loading && <li className="text-ink-muted">Loading fields…</li>}
                {!report.loading && fields.length === 0 && (
                  <li className="text-ink-muted">No fields were read from this document.</li>
                )}
                {fields.map((f) => (
                  <li key={f.id}>
                    <button
                      type="button"
                      onClick={() => {
                        setFieldId(f.id)
                        if (f.pageNumber) setPage(f.pageNumber)
                      }}
                      className={`flex w-full items-center justify-between gap-2 rounded px-2 py-1 text-left hover:bg-white ${
                        f.id === fieldId ? 'bg-brand-soft' : ''
                      }`}
                    >
                      <span>
                        <span className="font-medium text-ink">{f.fieldName}</span>: {f.value}
                      </span>
                      {f.bbox ? (
                        <span className="inline-flex items-center gap-1 text-[10px] text-brand">
                          <Crosshair size={11} /> region
                        </span>
                      ) : (
                        <span className="text-[10px] text-ink-muted">no region</span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-[10px] text-ink-muted">
                A region is only outlined for fields that have recorded coordinates. Findings cite a page,
                not a region.
              </p>
            </details>
          </div>
        )}
      </section>

      {/* ── Right: evidence + actions ────────────────────────────────── */}
      <aside
        aria-label="Evidence and actions"
        className="space-y-3 rounded-[var(--radius-md)] border border-border bg-white p-3 lg:max-h-[78vh] lg:overflow-y-auto"
      >
        {doc && <VerificationDimensions doc={doc} />}

        {!issue ? (
          <p className="text-xs text-ink-muted">
            Select a finding on the left to see its evidence and record what you decide.
          </p>
        ) : (
          <div className="space-y-3">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={SEVERITY_TONE[issue.severity]}>{SEVERITY_LABEL[issue.severity]}</Badge>
                <Badge tone="neutral">
                  {LIFECYCLE_LABEL[issue.lifecycleStatus ?? 'open'] ?? issue.lifecycleStatus}
                </Badge>
              </div>
              <h3 className="mt-1.5 text-sm font-semibold text-ink">{issue.title}</h3>
              {issue.explanation && (
                <p className="mt-1 text-xs text-ink-secondary">{issue.explanation}</p>
              )}
              <div className="mt-1.5">
                <HandbookBadge reference={issue.handbook} />
              </div>
            </div>

            <div>
              <h4 className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Evidence</h4>
              {issue.evidence.length === 0 ? (
                <p className="mt-1 text-xs text-ink-muted">No separate evidence was recorded for this finding.</p>
              ) : (
                <ul className="mt-1 space-y-1.5 text-xs text-ink-secondary">
                  {issue.evidence.map((e, idx) => {
                    const cited = parsePage(e.pageReference)
                    return (
                      <li key={`${e.text}-${idx}`}>
                        {e.text}
                        {e.documentName && <span className="text-ink-muted"> — {e.documentName}</span>}
                        {cited && (
                          <button
                            type="button"
                            className="ml-1 text-brand underline"
                            onClick={() => {
                              if (e.documentId) setDocId(e.documentId)
                              setFieldId(null)
                              setPage(cited)
                            }}
                          >
                            page {cited}
                          </button>
                        )}
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>

            {issue.applicantAction && (
              <div>
                <h4 className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                  What the applicant would need to do
                </h4>
                <p className="mt-1 text-xs text-ink-secondary">{issue.applicantAction}</p>
              </div>
            )}

            {canAct && issue.status === 'open' && (issue.findingIds.length > 0 || issue.checkIds.length > 0) && (
              <div>
                {!resolving ? (
                  <button
                    type="button"
                    className="text-xs font-medium text-accent underline-offset-2 hover:underline"
                    onClick={() => setResolving(true)}
                  >
                    Resolve, waive or accept…
                  </button>
                ) : (
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

            <FindingLifecycleControls issue={issue} role={role} canAct={canAct} onChanged={onChanged} />
          </div>
        )}
      </aside>
    </div>
  )
}

/**
 * Verification is reported along separate dimensions on purpose: a clean result in one says
 * nothing about the others, and none of them is an authenticity verdict.
 */
function VerificationDimensions({ doc }: { doc: ScrutinyReview['documents'][number] }) {
  const rows: Array<[string, string, string]> = [
    [
      'Readability & type',
      doc.documentCheck
        ? `${humanize(doc.documentCheck.clarity)} · type ${humanize(doc.documentCheck.typeMatch)}`
        : 'Not checked',
      'Automatic pre-check of the file. Not an authenticity result.',
    ],
    ['Rule validation', humanize(doc.ruleValidationStatus), 'Configured rules applied to extracted fields.'],
    [
      'External verification',
      humanize(doc.externalVerificationStatus),
      'Issuer confirmation. Local demo issuers are simulated — not an official authority.',
    ],
    ['Human review', humanize(doc.reviewStatus), 'Your own review of this document.'],
  ]
  return (
    <section aria-label="Verification dimensions">
      <h4 className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
        Verification dimensions
      </h4>
      <dl className="mt-1 space-y-1.5">
        {rows.map(([label, value, note]) => (
          <div key={label} title={note}>
            <dt className="text-[10px] text-ink-muted">{label}</dt>
            <dd className="text-xs font-medium text-ink">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-1 text-[10px] text-ink-muted">
        Cross-document matching and technical-integrity indicators are on their own tabs.
      </p>
    </section>
  )
}
