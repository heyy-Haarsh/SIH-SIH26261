import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  FileText,
  AlertTriangle,
  CheckCircle2,
  MessageSquare,
  History,
  Plug,
  GitCompare,
  Shield,
  RefreshCw,
} from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { Card, CardHeader } from '@/components/ui/Card'
import { Tabs } from '@/components/ui/Tabs'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input, Textarea } from '@/components/ui/Input'
import { EmptyState } from '@/components/ui/EmptyState'
import {
  ApplicationStatusBadge,
  OutcomeBadge,
  PriorityBadge,
  VerificationBadge,
} from '@/components/ui/StatusBadge'
import { confidenceLabel, formatBytes, formatDate, formatDateTime } from '@/lib/format'
import { useRole } from '@/app/RoleContext'
import { useApplicationDetail } from '@/hooks/useApplicationDetail'
import { api } from '@/services/api'

function outcomeTone(outcome: string): 'pass' | 'failed' | 'warning' | 'manual' | 'info' | 'neutral' {
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

function riskTone(risk: string): 'pass' | 'failed' | 'warning' | 'manual' | 'info' | 'neutral' {
  switch (risk) {
    case 'informational':
      return 'info'
    case 'check_limitation':
      return 'neutral'
    case 'technical_anomaly':
      return 'warning'
    case 'authenticity_concern':
      return 'failed'
    case 'possible_duplicate':
      return 'manual'
    default:
      return 'neutral'
  }
}

export function ApplicationDetailPage() {
  const { id } = useParams()
  const { role } = useRole()
  const { detail, source, loading, error, reload } = useApplicationDetail(id)
  const [tab, setTab] = useState('overview')
  const [note, setNote] = useState('')
  const [selectedDoc, setSelectedDoc] = useState<string | null>(null)
  const [extractBusy, setExtractBusy] = useState(false)
  const [extractMsg, setExtractMsg] = useState<string | null>(null)
  const [reconBusy, setReconBusy] = useState(false)
  const [resolveBusy, setResolveBusy] = useState<string | null>(null)
  const [resolveReason, setResolveReason] = useState<Record<string, string>>({})
  const [reconMsg, setReconMsg] = useState<string | null>(null)
  const [forensicsBusy, setForensicsBusy] = useState(false)
  const [forensicsMsg, setForensicsMsg] = useState<string | null>(null)
  const [forensicsResolveBusy, setForensicsResolveBusy] = useState<string | null>(null)
  const [forensicsReason, setForensicsReason] = useState<Record<string, string>>({})
  const [workflowBusy, setWorkflowBusy] = useState(false)
  const [workflowMsg, setWorkflowMsg] = useState<string | null>(null)
  const [clarifyTitle, setClarifyTitle] = useState('Clarification required')
  const [clarifyBody, setClarifyBody] = useState('')
  const [decisionReason, setDecisionReason] = useState('')
  const roleLabel =
    role === 'officer' ? 'Scrutiny Officer' : role === 'applicant' ? 'Applicant' : 'Administrator'
  const listPath = role === 'applicant' ? '/applicant/applications' : '/officer/queue'

  if (loading) {
    return (
      <AppShell title="Loading…" breadcrumbs={[roleLabel, 'Applications']}>
        <p className="text-sm text-ink-muted">Loading application…</p>
      </AppShell>
    )
  }

  if (!detail) {
    return (
      <AppShell title="Application not found" breadcrumbs={[roleLabel, 'Applications']}>
        <EmptyState
          icon={FileText}
          title="Application not found"
          description={error ?? 'No matching application in the API or demo dataset.'}
          action={
            <Link to={listPath}>
              <Button variant="outline">Back to list</Button>
            </Link>
          }
        />
      </AppShell>
    )
  }

  const activeDoc = detail.documents.find((d) => d.id === (selectedDoc ?? detail.documents[0]?.id))

  return (
    <AppShell
      title={detail.applicationNumber}
      breadcrumbs={[roleLabel, 'Applications', detail.applicationNumber]}
      actions={
        role === 'officer' || role === 'admin' ? (
          <>
            <Button
              variant="outline"
              size="sm"
              disabled={workflowBusy}
              onClick={async () => {
                setWorkflowBusy(true)
                setWorkflowMsg(null)
                try {
                  await api.startScrutiny(role, detail.id)
                  setWorkflowMsg('Scrutiny started — application under_scrutiny.')
                  await reload()
                } catch (err) {
                  setWorkflowMsg(err instanceof Error ? err.message : 'Start scrutiny failed')
                } finally {
                  setWorkflowBusy(false)
                }
              }}
            >
              Start scrutiny
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={workflowBusy}
              onClick={() => setTab('review')}
            >
              Request clarification
            </Button>
            <Button size="sm" disabled={workflowBusy} onClick={() => setTab('review')}>
              Record decision
            </Button>
          </>
        ) : role === 'applicant' ? (
          <>
            <Link to="/applicant/uploads">
              <Button variant="outline" size="sm">
                Upload / replace document
              </Button>
            </Link>
            <Button
              size="sm"
              disabled={workflowBusy}
              onClick={async () => {
                setWorkflowBusy(true)
                setWorkflowMsg(null)
                try {
                  await api.resubmitApplication(role, detail.id, 'Resubmitted after corrections')
                  setWorkflowMsg('Resubmitted — processing re-run; prior history preserved.')
                  await reload()
                } catch (err) {
                  setWorkflowMsg(err instanceof Error ? err.message : 'Resubmit failed')
                } finally {
                  setWorkflowBusy(false)
                }
              }}
            >
              Resubmit
            </Button>
          </>
        ) : undefined
      }
    >
      <DemoBanner>
        {source === 'api'
          ? 'Live API data. Priority score is an explainable prioritization aid — not fraud proof or auto-rejection. Findings may cite SYN-RULE-* placeholders.'
          : 'Synthetic demo data (mock layer). Switch to an API-created application for the full scrutiny workflow.'}
      </DemoBanner>
      {workflowMsg && (
        <div className="mb-4 rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2 text-xs text-ink-secondary">
          {workflowMsg}
        </div>
      )}

      <div className="mb-5 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-lg font-semibold text-ink">{detail.institutionName}</h2>
                <ApplicationStatusBadge status={detail.status} />
                <PriorityBadge priority={detail.priority} />
              </div>
              <p className="mt-1 text-sm text-ink-secondary">
                {detail.category} · {detail.programName} · AY {detail.academicYear}
              </p>
            </div>
            {typeof detail.priorityScore === 'number' && (
              <div className="rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2 text-right">
                <div className="text-[10px] uppercase tracking-wide text-ink-muted">
                  Priority aid
                </div>
                <div className="text-xl font-semibold text-ink">{detail.priorityScore}</div>
                <div className="max-w-[140px] text-[10px] text-ink-muted">
                  Prioritization only — not proof of fraud or compliance
                </div>
              </div>
            )}
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <Meta label="Application ID" value={detail.applicationNumber} />
            <Meta label="Submitted" value={formatDate(detail.submittedAt)} />
            <Meta label="Assigned officer" value={detail.assignedOfficer ?? 'Unassigned'} />
            <Meta label="Contact" value={detail.contactEmail} />
            <Meta label="Findings" value={String(detail.findingCount)} />
            <Meta label="Deficiencies" value={String(detail.deficiencyCount)} />
          </div>
        </Card>

        <Card>
          <CardHeader title="Scrutiny summary" description="Explainable prioritization" />
          <div className="space-y-2 text-sm">
            <Row label="Workflow status" value={detail.status.replace(/_/g, ' ')} />
            <Row label="Validation" value={detail.validationRunStatus ?? '—'} />
            <Row
              label="Manual review"
              value={detail.requiresManualReview ? 'Required' : 'Not required'}
            />
            <Row
              label="Last transition"
              value={detail.lastTransitionNote ?? '—'}
            />
          </div>
          {(detail.scoreBreakdown?.contributions?.length ?? 0) > 0 && (
            <div className="mt-3 border-t border-border pt-3">
              <div className="mb-1 text-[11px] font-medium text-ink-secondary">Score contributions</div>
              <ul className="max-h-40 space-y-1 overflow-auto text-[11px] text-ink-muted">
                {(detail.scoreBreakdown?.contributions ?? []).slice(0, 8).map((c, i) => (
                  <li key={`${c.weightKey}-${i}`}>
                    +{c.points} · {c.label}{' '}
                    <span className="opacity-70">({c.weightKey})</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      </div>

      <Card padding={false}>
        <div className="px-4 pt-2">
          <Tabs
            active={tab}
            onChange={setTab}
            tabs={[
              { id: 'overview', label: 'Checklist & documents' },
              { id: 'extracted', label: 'Extracted fields', count: detail.extractedFields.length },
              { id: 'findings', label: 'Findings', count: detail.findings.length },
              {
                id: 'compare',
                label: 'Reconciliation',
                count: detail.discrepancies.filter((d) => d.outcome !== 'MATCH').length,
              },
              {
                id: 'forensics',
                label: 'Authenticity & Forensics',
                count: (detail.forensicsIndicators ?? []).filter(
                  (i) =>
                    i.riskClass === 'technical_anomaly' ||
                    i.riskClass === 'authenticity_concern' ||
                    i.riskClass === 'possible_duplicate',
                ).length,
              },
              { id: 'verify', label: 'Verification' },
              { id: 'review', label: 'Review & audit' },
            ]}
          />
        </div>

        <div className="p-4 md:p-5">
          {tab === 'overview' && (
            <div className="grid gap-4 lg:grid-cols-2">
              <div>
                <h3 className="mb-3 text-sm font-semibold text-ink">Required document checklist</h3>
                <ul className="space-y-2">
                  {detail.requirements.map((req) => (
                    <li
                      key={req.id}
                      className="flex items-center justify-between rounded-[var(--radius-md)] border border-border px-3 py-2.5"
                    >
                      <div>
                        <div className="text-sm font-medium text-ink">{req.name}</div>
                        <div className="text-[11px] text-ink-muted">
                          {req.code} · {req.mandatory ? 'Mandatory' : 'Optional'} ·{' '}
                          {req.allowedTypes.join(', ')}
                        </div>
                      </div>
                      <Badge
                        tone={
                          req.status === 'uploaded'
                            ? 'pass'
                            : req.status === 'missing'
                              ? 'failed'
                              : req.status === 'rejected'
                                ? 'warning'
                                : 'neutral'
                        }
                      >
                        {req.status}
                      </Badge>
                    </li>
                  ))}
                </ul>
              </div>

              <div>
                <h3 className="mb-3 text-sm font-semibold text-ink">Uploaded documents</h3>
                <div className="mb-3 space-y-2">
                  {detail.documents.map((doc) => (
                    <button
                      key={doc.id}
                      type="button"
                      onClick={() => setSelectedDoc(doc.id)}
                      className={`flex w-full items-center justify-between rounded-[var(--radius-md)] border px-3 py-2.5 text-left transition-colors ${
                        activeDoc?.id === doc.id
                          ? 'border-brand bg-brand-soft'
                          : 'border-border hover:bg-surface-muted'
                      }`}
                    >
                      <div>
                        <div className="text-sm font-medium text-ink">{doc.name}</div>
                        <div className="text-[11px] text-ink-muted">
                          {doc.fileName} · v{doc.version} · {formatBytes(doc.sizeBytes)} ·{' '}
                          {formatDate(doc.uploadedAt)}
                        </div>
                        {doc.extractionStatus && (
                          <div className="mt-1 flex flex-wrap gap-1">
                            <Badge tone="info">{doc.extractionStatus}</Badge>
                            {doc.contentKind && <Badge tone="neutral">{doc.contentKind}</Badge>}
                            {doc.categoryMismatch && <Badge tone="warning">category mismatch</Badge>}
                          </div>
                        )}
                      </div>
                      <OutcomeBadge outcome={doc.status} />
                    </button>
                  ))}
                </div>

                <div className="rounded-[var(--radius-md)] border border-dashed border-border bg-surface p-6 text-center">
                  <FileText className="mx-auto mb-2 text-ink-muted" size={28} />
                  <div className="text-sm font-medium text-ink">
                    {activeDoc ? activeDoc.fileName : 'No document selected'}
                  </div>
                  <p className="mt-1 text-xs text-ink-muted">
                    Preview placeholder — page references from extraction are listed in Extracted
                    fields. Bounding-box highlight in the viewer is not wired in this build; page
                    numbers are authoritative.
                  </p>
                  {activeDoc?.pageCount && (
                    <p className="mt-2 text-[11px] text-ink-secondary">
                      {activeDoc.pageCount} page(s) · {activeDoc.mimeType}
                    </p>
                  )}
                  {activeDoc && source === 'api' && (
                    <div className="mt-3 flex flex-col items-center gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        leftIcon={<RefreshCw size={14} />}
                        disabled={extractBusy}
                        onClick={async () => {
                          setExtractBusy(true)
                          setExtractMsg(null)
                          try {
                            const run = await api.startExtraction(role, activeDoc.id, true)
                            setExtractMsg(
                              `Extraction ${run.status} · kind=${run.contentKind} · fields=${run.fields?.length ?? 0}`,
                            )
                          } catch (e) {
                            setExtractMsg(e instanceof Error ? e.message : 'Extraction failed')
                          } finally {
                            setExtractBusy(false)
                          }
                        }}
                      >
                        {extractBusy ? 'Extracting…' : 'Re-run extraction'}
                      </Button>
                      {extractMsg && (
                        <p className="text-[11px] text-ink-secondary">{extractMsg}</p>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {tab === 'extracted' && (
            <div className="space-y-4">
              {detail.documents.some((d) => d.categoryMismatch) && (
                <div className="rounded-[var(--radius-md)] border border-amber-200 bg-status-warning-bg px-3 py-2 text-xs text-status-warning">
                  Potential document-type mismatch detected for one or more uploads (selected vs
                  predicted category). This is not labeled as fraud — review required.
                </div>
              )}
              {source === 'mock' && (
                <p className="text-xs text-ink-muted">
                  Showing mock extracted fields. API-backed applications show pipeline results only.
                </p>
              )}
              <div className="overflow-x-auto">
                <table className="w-full min-w-[880px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-border text-xs uppercase text-ink-muted">
                      <th className="px-2 py-2">Field</th>
                      <th className="px-2 py-2">Value</th>
                      <th className="px-2 py-2">Raw</th>
                      <th className="px-2 py-2">Source</th>
                      <th className="px-2 py-2">Page</th>
                      <th className="px-2 py-2">Method</th>
                      <th className="px-2 py-2">Confidence</th>
                      <th className="px-2 py-2">Review</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.extractedFields.length === 0 && (
                      <tr>
                        <td colSpan={8} className="px-2 py-6 text-center text-ink-muted">
                          No extracted fields yet. Upload a document or run extraction.
                        </td>
                      </tr>
                    )}
                    {detail.extractedFields.map((field) => (
                      <tr key={field.id} className="border-b border-border">
                        <td className="px-2 py-2.5 font-medium text-ink">
                          {field.fieldName}
                          {field.isConflict && (
                            <Badge tone="warning" className="ml-1">
                              conflict
                            </Badge>
                          )}
                        </td>
                        <td className="px-2 py-2.5 text-ink-secondary">
                          {field.value}
                          {field.correctedValue && (
                            <div className="text-[10px] text-status-manual">
                              Corrected: {field.correctedValue}
                            </div>
                          )}
                        </td>
                        <td className="px-2 py-2.5 text-ink-muted">{field.rawValue ?? '—'}</td>
                        <td className="px-2 py-2.5 text-ink-muted">{field.sourceDocumentName}</td>
                        <td className="px-2 py-2.5 text-ink-muted">
                          {field.pageReference ?? (field.pageNumber ? `p.${field.pageNumber}` : '—')}
                        </td>
                        <td className="px-2 py-2.5 text-ink-muted">{field.method ?? '—'}</td>
                        <td className="px-2 py-2.5 text-ink-muted">
                          {confidenceLabel(field.confidence)}
                          {field.ocrConfidence != null && (
                            <div className="text-[10px]">
                              OCR: {Math.round(field.ocrConfidence * 100)}%
                            </div>
                          )}
                        </td>
                        <td className="px-2 py-2.5 text-ink-muted">{field.reviewStatus ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {tab === 'findings' && (
            <div className="space-y-3">
              {detail.findings.map((finding) => (
                <div key={finding.id} className="rounded-[var(--radius-md)] border border-border p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <Shield size={16} className="text-brand" />
                    <span className="text-sm font-semibold text-ink">{finding.title}</span>
                    <OutcomeBadge outcome={finding.outcome} />
                    <Badge tone="neutral">{finding.status}</Badge>
                  </div>
                  <p className="mt-2 text-xs text-ink-secondary">{finding.description}</p>
                  <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-ink-muted">
                    {finding.ruleId && (
                      <span>
                        Rule: {finding.ruleId} ({finding.ruleVersion})
                      </span>
                    )}
                    {finding.handbookRef && <span>{finding.handbookRef}</span>}
                  </div>
                  <div className="mt-3 space-y-1.5">
                    <div className="text-[11px] font-medium uppercase tracking-wide text-ink-muted">
                      Evidence
                    </div>
                    {finding.evidence.map((ev) => (
                      <div
                        key={ev.id}
                        className="rounded border border-border bg-surface px-3 py-2 text-xs text-ink-secondary"
                      >
                        {ev.description}
                        {ev.documentName && (
                          <span className="text-ink-muted">
                            {' '}
                            · {ev.documentName}
                            {ev.pageReference ? ` (${ev.pageReference})` : ''}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {tab === 'compare' && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-sm font-semibold text-ink">
                  <GitCompare size={16} /> Cross-document reconciliation
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={reconBusy}
                  leftIcon={<RefreshCw size={14} />}
                  onClick={async () => {
                    setReconBusy(true)
                    setReconMsg(null)
                    try {
                      const run = await api.runReconciliation(role, detail.id)
                      const counts = (run.summary?.counts as Record<string, number>) || {}
                      setReconMsg(
                        `Reconciliation completed — MATCH ${counts.MATCH ?? 0}, MISMATCH ${counts.MISMATCH ?? 0}, MISSING ${counts.MISSING_DATA ?? 0}, DUPLICATE ${counts.POSSIBLE_DUPLICATE ?? 0}. Not a fraud determination.`,
                      )
                      await reload()
                    } catch (err) {
                      setReconMsg(err instanceof Error ? err.message : 'Reconciliation failed')
                    } finally {
                      setReconBusy(false)
                    }
                  }}
                >
                  {reconBusy ? 'Running…' : 'Run reconciliation'}
                </Button>
              </div>
              <p className="text-xs text-ink-muted">
                Compares institution name, registration/reference numbers, addresses, dates,
                survey/plot numbers, and land area. Outcomes are MATCH / MISMATCH / MISSING_DATA /
                POSSIBLE_DUPLICATE / MANUAL_REVIEW — never labeled as fraud.
              </p>
              {reconMsg && (
                <div className="rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2 text-xs text-ink-secondary">
                  {reconMsg}
                </div>
              )}

              {detail.discrepancies.length === 0 && (
                <EmptyState
                  icon={GitCompare}
                  title="No reconciliation items yet"
                  description="Upload documents with overlapping fields, then run reconciliation or validation."
                />
              )}

              {(['MISMATCH', 'MISSING_DATA', 'POSSIBLE_DUPLICATE', 'MANUAL_REVIEW', 'MATCH'] as const).map(
                (bucket) => {
                  const rows = detail.discrepancies.filter((d) => d.outcome === bucket)
                  if (!rows.length) return null
                  return (
                    <div key={bucket} className="space-y-2">
                      <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
                        {bucket.replace(/_/g, ' ')} ({rows.length})
                      </h4>
                      {rows.map((d) => (
                        <div
                          key={d.id}
                          className="rounded-[var(--radius-md)] border border-border p-4"
                        >
                          <div className="mb-2 flex flex-wrap items-center gap-2">
                            <span className="text-sm font-medium text-ink">
                              {d.title || d.fieldName}
                            </span>
                            <Badge tone={outcomeTone(d.outcome)}>{d.outcome}</Badge>
                            {d.matchKind && <Badge tone="info">{d.matchKind}</Badge>}
                            <Badge tone="neutral">{d.status}</Badge>
                          </div>
                          {d.description && (
                            <p className="mb-3 text-xs text-ink-secondary">{d.description}</p>
                          )}
                          <div className="grid gap-2 sm:grid-cols-2">
                            {d.values.map((v) => (
                              <div
                                key={`${v.documentId}-${v.value}`}
                                className="rounded border border-border bg-surface p-3"
                              >
                                <div className="text-[11px] text-ink-muted">
                                  {v.documentName}
                                  {v.page ? ` · ${v.page}` : ''}
                                  {v.pageNumber != null ? ` · page ${v.pageNumber}` : ''}
                                </div>
                                <div className="mt-1 text-sm font-medium text-ink">{v.value}</div>
                                {v.normalizedValue && v.normalizedValue !== v.value && (
                                  <div className="mt-1 text-[11px] text-ink-muted">
                                    Normalized: {v.normalizedValue}
                                  </div>
                                )}
                                {v.extractedFieldId && (
                                  <div className="mt-1 text-[10px] text-ink-muted break-all">
                                    Field evidence: {v.extractedFieldId}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                          {bucket !== 'MATCH' &&
                            d.status === 'open' &&
                            (role === 'officer' || role === 'admin') && (
                              <div className="mt-3 space-y-2 border-t border-border pt-3">
                                <label className="block text-[11px] font-medium text-ink-secondary">
                                  Resolution reason (preserves original finding)
                                </label>
                                <Textarea
                                  rows={2}
                                  value={resolveReason[d.id] ?? ''}
                                  onChange={(e) =>
                                    setResolveReason((prev) => ({
                                      ...prev,
                                      [d.id]: e.target.value,
                                    }))
                                  }
                                  placeholder="Explain why this is accepted, waived, or resolved…"
                                />
                                <div className="flex flex-wrap gap-2">
                                  {(['resolved', 'waived', 'accepted'] as const).map((st) => (
                                    <Button
                                      key={st}
                                      size="sm"
                                      variant={st === 'resolved' ? 'primary' : 'outline'}
                                      disabled={resolveBusy === d.id}
                                      onClick={async () => {
                                        const reason = (resolveReason[d.id] ?? '').trim()
                                        if (reason.length < 5) {
                                          setReconMsg('Enter a resolution reason (min 5 characters).')
                                          return
                                        }
                                        setResolveBusy(d.id)
                                        try {
                                          await api.resolveReconciliationItem(role, d.id, {
                                            status: st,
                                            reason,
                                          })
                                          setReconMsg(
                                            `Recorded ${st} for ${d.fieldName}. Original outcome ${d.originalOutcome ?? d.outcome} preserved.`,
                                          )
                                          await reload()
                                        } catch (err) {
                                          setReconMsg(
                                            err instanceof Error ? err.message : 'Resolve failed',
                                          )
                                        } finally {
                                          setResolveBusy(null)
                                        }
                                      }}
                                    >
                                      Mark {st}
                                    </Button>
                                  ))}
                                </div>
                              </div>
                            )}
                        </div>
                      ))}
                    </div>
                  )
                },
              )}
            </div>
          )}

          {tab === 'forensics' && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-sm font-semibold text-ink">
                  <Shield size={16} /> Authenticity &amp; forensics
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={forensicsBusy}
                  leftIcon={<RefreshCw size={14} />}
                  onClick={async () => {
                    setForensicsBusy(true)
                    setForensicsMsg(null)
                    try {
                      const run = await api.runForensics(role, detail.id)
                      const counts = (run.summary?.countsByRiskClass as Record<string, number>) || {}
                      setForensicsMsg(
                        `Forensics completed — concerns ${counts.authenticity_concern ?? 0}, anomalies ${counts.technical_anomaly ?? 0}, duplicates ${counts.possible_duplicate ?? 0}. Never an automatic fraud label.`,
                      )
                      await reload()
                    } catch (err) {
                      setForensicsMsg(err instanceof Error ? err.message : 'Forensics failed')
                    } finally {
                      setForensicsBusy(false)
                    }
                  }}
                >
                  {forensicsBusy ? 'Analyzing…' : 'Run forensics'}
                </Button>
              </div>
              <p className="text-xs text-ink-muted">
                Local PDF metadata/structure/signature heuristics, hash and near-duplicate checks,
                and labeled external claims. Missing metadata or an unsigned file is a check
                limitation — not automatic tampering. Simulated checks are labeled as such.
              </p>
              {(detail.forensicsLimitations ?? []).length > 0 && (
                <div className="rounded-[var(--radius-md)] border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                  <div className="mb-1 font-medium">Analysis limitations</div>
                  <ul className="list-disc pl-4">
                    {(detail.forensicsLimitations ?? []).map((l) => (
                      <li key={l}>{l}</li>
                    ))}
                  </ul>
                </div>
              )}
              {forensicsMsg && (
                <div className="rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2 text-xs text-ink-secondary">
                  {forensicsMsg}
                </div>
              )}
              {(detail.forensicsIndicators ?? []).length === 0 && (
                <EmptyState
                  icon={Shield}
                  title="No forensics indicators yet"
                  description="Upload documents, then run forensics or validation."
                />
              )}
              {(detail.forensicsIndicators ?? []).map((ind) => (
                <div key={ind.id} className="rounded-[var(--radius-md)] border border-border p-4">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-ink">{ind.title}</span>
                    <Badge tone={riskTone(ind.riskClass)}>{ind.riskClass.replace(/_/g, ' ')}</Badge>
                    <Badge tone="neutral">{ind.code}</Badge>
                    <Badge tone="info">{ind.verificationStatus.replace(/_/g, ' ')}</Badge>
                  </div>
                  <p className="mb-2 text-xs text-ink-secondary">{ind.description}</p>
                  {ind.affectedPages?.length > 0 && (
                    <p className="mb-2 text-[11px] text-ink-muted">
                      Affected pages: {ind.affectedPages.join(', ')}
                    </p>
                  )}
                  <ul className="mb-2 space-y-1">
                    {ind.evidence.map((ev) => (
                      <li key={ev.id} className="text-[11px] text-ink-muted">
                        {ev.description}
                        {ev.documentName ? ` · ${ev.documentName}` : ''}
                        {ev.pageReference ? ` (${ev.pageReference})` : ''}
                      </li>
                    ))}
                  </ul>
                  {ind.status === 'open' &&
                    (ind.riskClass === 'technical_anomaly' ||
                      ind.riskClass === 'authenticity_concern' ||
                      ind.riskClass === 'possible_duplicate') &&
                    (role === 'officer' || role === 'admin') && (
                      <div className="mt-3 space-y-2 border-t border-border pt-3">
                        <label className="block text-[11px] font-medium text-ink-secondary">
                          Officer resolution (preserves original risk class)
                        </label>
                        <Textarea
                          rows={2}
                          value={forensicsReason[ind.id] ?? ''}
                          onChange={(e) =>
                            setForensicsReason((prev) => ({ ...prev, [ind.id]: e.target.value }))
                          }
                          placeholder="Explain acceptance, waiver, or resolution…"
                        />
                        <div className="flex flex-wrap gap-2">
                          {(['resolved', 'waived', 'accepted'] as const).map((st) => (
                            <Button
                              key={st}
                              size="sm"
                              variant={st === 'resolved' ? 'primary' : 'outline'}
                              disabled={forensicsResolveBusy === ind.id}
                              onClick={async () => {
                                const reason = (forensicsReason[ind.id] ?? '').trim()
                                if (reason.length < 5) {
                                  setForensicsMsg('Enter a resolution reason (min 5 characters).')
                                  return
                                }
                                setForensicsResolveBusy(ind.id)
                                try {
                                  await api.resolveForensicsIndicator(role, ind.id, {
                                    status: st,
                                    reason,
                                  })
                                  setForensicsMsg(
                                    `Recorded ${st} for ${ind.code}. Original risk ${ind.originalRiskClass ?? ind.riskClass} preserved.`,
                                  )
                                  await reload()
                                } catch (err) {
                                  setForensicsMsg(
                                    err instanceof Error ? err.message : 'Resolve failed',
                                  )
                                } finally {
                                  setForensicsResolveBusy(null)
                                }
                              }}
                            >
                              Mark {st}
                            </Button>
                          ))}
                        </div>
                      </div>
                    )}
                </div>
              ))}
            </div>
          )}

          {tab === 'verify' && (
            <div className="space-y-3">
              <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink">
                <Plug size={16} /> External verification status
              </div>
              {detail.verifications.map((v) => (
                <div
                  key={v.id}
                  className="flex flex-col gap-2 rounded-[var(--radius-md)] border border-border p-4 sm:flex-row sm:items-start sm:justify-between"
                >
                  <div>
                    <div className="text-sm font-medium text-ink">{v.claim}</div>
                    <p className="mt-1 text-xs text-ink-secondary">{v.detail}</p>
                    <div className="mt-2 text-[11px] text-ink-muted">
                      Source type: {v.source.replace(/_/g, ' ')} · Checked:{' '}
                      {formatDateTime(v.checkedAt)}
                    </div>
                  </div>
                  <VerificationBadge status={v.status} />
                </div>
              ))}
            </div>
          )}

          {tab === 'review' && (
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-4">
                <div>
                  <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
                    <MessageSquare size={16} /> Reviewer notes
                  </div>
                  <ul className="mb-4 space-y-2">
                    {detail.reviewNotes.map((n) => (
                      <li key={n.id} className="rounded-[var(--radius-md)] border border-border p-3">
                        <div className="text-xs font-medium text-ink">
                          {n.author} · {n.role}
                        </div>
                        <p className="mt-1 text-sm text-ink-secondary">{n.content}</p>
                        <div className="mt-1 text-[11px] text-ink-muted">
                          {formatDateTime(n.createdAt)}
                        </div>
                      </li>
                    ))}
                  </ul>
                  {(role === 'officer' || role === 'admin') && (
                    <>
                      <Textarea
                        rows={2}
                        placeholder="Add a review note…"
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                      />
                      <div className="mt-2 flex flex-wrap gap-2">
                        <Button
                          size="sm"
                          disabled={!note.trim() || workflowBusy}
                          onClick={async () => {
                            setWorkflowBusy(true)
                            try {
                              await api.addReviewNote(role, detail.id, note.trim())
                              setNote('')
                              setWorkflowMsg('Note saved.')
                              await reload()
                            } catch (err) {
                              setWorkflowMsg(err instanceof Error ? err.message : 'Note failed')
                            } finally {
                              setWorkflowBusy(false)
                            }
                          }}
                        >
                          Save note
                        </Button>
                      </div>
                    </>
                  )}
                </div>

                {(role === 'officer' || role === 'admin') && (
                  <div className="rounded-[var(--radius-md)] border border-border p-3">
                    <div className="mb-2 text-sm font-semibold text-ink">Request clarification</div>
                    <Input
                      className="mb-2"
                      value={clarifyTitle}
                      onChange={(e) => setClarifyTitle(e.target.value)}
                      placeholder="Title"
                    />
                    <Textarea
                      rows={3}
                      placeholder="Describe what the applicant must correct…"
                      value={clarifyBody}
                      onChange={(e) => setClarifyBody(e.target.value)}
                    />
                    <Button
                      className="mt-2"
                      size="sm"
                      variant="outline"
                      leftIcon={<AlertTriangle size={14} />}
                      disabled={workflowBusy}
                      onClick={async () => {
                        setWorkflowBusy(true)
                        try {
                          await api.requestClarification(role, detail.id, {
                            title: clarifyTitle,
                            description: clarifyBody,
                          })
                          setWorkflowMsg('Clarification requested — status clarification_required.')
                          setClarifyBody('')
                          await reload()
                        } catch (err) {
                          setWorkflowMsg(err instanceof Error ? err.message : 'Clarification failed')
                        } finally {
                          setWorkflowBusy(false)
                        }
                      }}
                    >
                      Issue clarification / deficiency
                    </Button>
                  </div>
                )}

                {(role === 'officer' || role === 'admin') && (
                  <div className="rounded-[var(--radius-md)] border border-border p-3">
                    <div className="mb-2 text-sm font-semibold text-ink">Final recommendation</div>
                    <p className="mb-2 text-[11px] text-ink-muted">
                      Does not auto-reject from score alone. Reason is audited; prior findings kept.
                    </p>
                    <Textarea
                      rows={2}
                      placeholder="Decision reason…"
                      value={decisionReason}
                      onChange={(e) => setDecisionReason(e.target.value)}
                    />
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        leftIcon={<CheckCircle2 size={14} />}
                        disabled={workflowBusy}
                        onClick={async () => {
                          setWorkflowBusy(true)
                          try {
                            await api.recordDecision(role, detail.id, {
                              reason: decisionReason,
                              recommend: true,
                            })
                            setWorkflowMsg('Recorded RECOMMENDED.')
                            await reload()
                          } catch (err) {
                            setWorkflowMsg(err instanceof Error ? err.message : 'Decision failed')
                          } finally {
                            setWorkflowBusy(false)
                          }
                        }}
                      >
                        Recommend
                      </Button>
                      <Button
                        size="sm"
                        variant="danger"
                        disabled={workflowBusy}
                        onClick={async () => {
                          setWorkflowBusy(true)
                          try {
                            await api.recordDecision(role, detail.id, {
                              reason: decisionReason,
                              recommend: false,
                            })
                            setWorkflowMsg('Recorded REJECTED.')
                            await reload()
                          } catch (err) {
                            setWorkflowMsg(err instanceof Error ? err.message : 'Decision failed')
                          } finally {
                            setWorkflowBusy(false)
                          }
                        }}
                      >
                        Reject
                      </Button>
                    </div>
                  </div>
                )}

                {(detail.deficiencies ?? []).length > 0 && (
                  <div>
                    <div className="mb-2 text-sm font-semibold text-ink">Deficiencies</div>
                    <ul className="space-y-2">
                      {(detail.deficiencies ?? []).map((d) => (
                        <li key={d.id} className="rounded border border-border p-2 text-xs">
                          <Badge tone={d.status === 'open' ? 'warning' : 'neutral'}>{d.status}</Badge>{' '}
                          <span className="font-medium">{d.title}</span>
                          <p className="mt-1 text-ink-secondary">{d.description}</p>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
              <div>
                <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
                  <History size={16} /> Audit history
                </div>
                <ul className="space-y-2">
                  {detail.auditEvents.map((ev) => (
                    <li
                      key={ev.id}
                      className="rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2.5"
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
          )}
        </div>
      </Card>
    </AppShell>
  )
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-ink-muted">{label}</div>
      <div className="mt-0.5 truncate text-sm font-medium text-ink">{value}</div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border pb-2 last:border-0">
      <span className="text-ink-muted">{label}</span>
      <span className="font-medium text-ink">{value}</span>
    </div>
  )
}
