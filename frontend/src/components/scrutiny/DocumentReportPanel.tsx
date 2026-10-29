import { useEffect, useMemo, useState } from 'react'
import { ChevronDown, ChevronRight, X } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { confidenceLabel, formatBytes, formatDateTime } from '@/lib/format'
import { api } from '@/services/api'
import { useRefreshable } from '@/hooks/useRefreshable'
import type { PipelineCheck, PipelineStage } from '@/types'
import { DocumentPreview } from './DocumentPreview'
import { HandbookBadge } from './HandbookBadge'
import { ResolveControl } from './ResolveControl'
import {
  MODE_LABEL,
  SEVERITY_BAR,
  SEVERITY_LABEL,
  SEVERITY_TONE,
  STAGE_LABEL,
  STAGE_TONE,
  STATUS_LABEL,
  type Resolution,
} from './scrutinyUi'

interface Props {
  role: string
  applicationId: string
  documentId: string
  onClose: () => void
  /** Called after an officer resolution so the parent can refresh the review. */
  onChanged: () => Promise<unknown> | void
}

/** Side panel: file preview + the complete five-stage verification report for one document. */
export function DocumentReportPanel({ role, applicationId, documentId, onClose, onChanged }: Props) {
  const { data, loading, error, reload } = useRefreshable(
    () => api.getDocumentReport(role, applicationId, documentId),
    `${applicationId}:${documentId}`,
  )
  const [showFields, setShowFields] = useState(false)
  const [focusFieldId, setFocusFieldId] = useState<string | null>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const doc = data?.document
  const afterResolve = async () => {
    await Promise.all([reload(), onChanged()])
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={onClose}>
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={doc ? `${doc.name} report` : 'Document report'}
        className="flex h-full w-full max-w-6xl flex-col bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start justify-between gap-3 border-b border-border px-4 py-2.5">
          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold text-ink">{doc?.name ?? 'Document'}</h2>
            {doc && (
              <p className="truncate text-[11px] text-ink-muted">
                {doc.fileName} · v{doc.version} · {formatBytes(doc.sizeBytes)} · uploaded{' '}
                {formatDateTime(doc.uploadedAt)}
              </p>
            )}
          </div>
          <Button size="sm" variant="outline" leftIcon={<X size={14} />} onClick={onClose}>
            Close
          </Button>
        </header>

        <div className="flex-1 overflow-y-auto p-4">
          {loading && <p className="text-sm text-ink-muted">Loading report…</p>}
          {error && !data && (
            <p className="text-sm text-status-failed" role="alert">
              {error}
            </p>
          )}
          {data && doc && (
            <div className="grid gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
              <div className="space-y-4">
                <section>
                  <h3 className="mb-2 text-sm font-semibold text-ink">Document preview</h3>
                  <p className="mb-2 text-[11px] text-ink-muted">
                    Select a field below to jump to its page. A blue box appears only when extraction
                    stored a bounding region — coordinates are never invented.
                  </p>
                  <DocumentPreview
                    role={role}
                    documentId={doc.id}
                    mimeType={doc.mimeType}
                    fileName={doc.fileName}
                    version={doc.version}
                    highlightPage={
                      data.extractedFields.find((f) => f.id === focusFieldId)?.pageNumber ?? null
                    }
                    highlightBBox={
                      data.extractedFields.find((f) => f.id === focusFieldId)?.bbox ?? null
                    }
                    highlightLabel={
                      data.extractedFields.find((f) => f.id === focusFieldId)?.fieldName ?? null
                    }
                  />
                </section>

                <section>
                  <h3 className="mb-2 text-sm font-semibold text-ink">Versions</h3>
                  <ul className="space-y-1 text-xs">
                    {data.versions.map((v) => (
                      <li
                        key={v.version}
                        className="flex flex-wrap items-center justify-between gap-2 rounded border border-border px-2 py-1.5"
                      >
                        <span>
                          v{v.version} · {v.fileName} · {formatBytes(v.sizeBytes)}
                        </span>
                        <span className="text-ink-muted">
                          {formatDateTime(v.uploadedAt)} · {v.sha256.slice(0, 10)}…
                        </span>
                        {v.isCurrent ? <Badge tone="brand">current</Badge> : <Badge>earlier</Badge>}
                      </li>
                    ))}
                  </ul>
                  <p className="mt-1 text-[11px] text-ink-muted">
                    Earlier versions are kept as history; every result on this page describes the
                    current version only.
                  </p>
                </section>

                <section>
                  <button
                    type="button"
                    className="flex items-center gap-1 text-sm font-semibold text-ink"
                    onClick={() => setShowFields((v) => !v)}
                  >
                    {showFields ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    Fields read from this document ({data.extractedFields.length})
                  </button>
                  {showFields && (
                    <div className="mt-2 overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead>
                          <tr className="border-b border-border uppercase text-ink-muted">
                            <th className="py-1 pr-2">Field</th>
                            <th className="py-1 pr-2">Value</th>
                            <th className="py-1 pr-2">Page</th>
                            <th className="py-1">Confidence</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.extractedFields.length === 0 && (
                            <tr>
                              <td colSpan={4} className="py-3 text-center text-ink-muted">
                                No fields were read from this document.
                              </td>
                            </tr>
                          )}
                          {data.extractedFields.map((f) => (
                            <tr
                              key={f.id}
                              className={`cursor-pointer border-b border-border hover:bg-surface-muted ${
                                focusFieldId === f.id ? 'bg-brand-soft' : ''
                              }`}
                              onClick={() => setFocusFieldId(f.id)}
                            >
                              <td className="py-1 pr-2 font-medium text-ink">
                                {f.fieldName.replace(/_/g, ' ')}
                                {f.isConflict && (
                                  <Badge tone="warning" className="ml-1">
                                    conflict
                                  </Badge>
                                )}
                                {f.bbox && (
                                  <Badge tone="info" className="ml-1">
                                    region
                                  </Badge>
                                )}
                              </td>
                              <td className="py-1 pr-2">{f.value}</td>
                              <td className="py-1 pr-2 text-ink-muted">{f.pageReference ?? '—'}</td>
                              <td className="py-1 text-ink-muted">
                                {confidenceLabel(f.confidence)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>
              </div>

              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-ink">Verification pipeline</h3>
                {data.stages.map((s) => (
                  <StageCard
                    key={s.key}
                    stage={s}
                    role={role}
                    onChanged={afterResolve}
                  />
                ))}
                <p className="rounded border border-border bg-surface px-3 py-2 text-[11px] text-ink-muted">
                  {data.disclaimer}
                </p>
              </div>
            </div>
          )}
        </div>
      </aside>
    </div>
  )
}

function StageCard({
  stage,
  role,
  onChanged,
}: {
  stage: PipelineStage
  role: string
  onChanged: () => Promise<unknown>
}) {
  const noisy = stage.status === 'pass' || stage.status === 'not_run'
  const [open, setOpen] = useState(!noisy)
  const concerning = useMemo(
    () => stage.checks.filter((c) => c.status === 'open' && c.severity !== 'info').length,
    [stage.checks],
  )
  return (
    <section className="rounded-[var(--radius-md)] border border-border">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="flex items-center gap-2 text-sm font-medium text-ink">
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          {stage.title}
        </span>
        <span className="flex items-center gap-2">
          {concerning > 0 && <span className="text-[11px] text-ink-muted">{concerning} open</span>}
          <Badge tone={STAGE_TONE[stage.status]}>{STAGE_LABEL[stage.status]}</Badge>
        </span>
      </button>
      <p className="px-3 pb-1.5 text-[11px] text-ink-muted">{stage.summary}</p>
      {open && (
        <div className="space-y-2 border-t border-border px-3 py-2.5">
          {stage.details.length > 0 && (
            <dl className="grid gap-x-3 gap-y-0.5 text-xs sm:grid-cols-2">
              {stage.details.map((d) => (
                <div key={d.label} className="flex gap-2">
                  <dt className="shrink-0 text-ink-muted">{d.label}:</dt>
                  <dd className="min-w-0 break-words text-ink">{d.value}</dd>
                </div>
              ))}
            </dl>
          )}
          {stage.checks.length === 0 && (
            <p className="text-xs text-ink-muted">No checks recorded at this stage.</p>
          )}
          <ul className="space-y-1.5">
            {stage.checks.map((c) => (
              <CheckRow
                key={c.id}
                check={c}
                role={role}
                onChanged={onChanged}
              />
            ))}
          </ul>
          {stage.limitations.length > 0 && (
            <ul className="list-disc pl-4 text-[11px] text-ink-muted">
              {stage.limitations.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  )
}

function CheckRow({
  check,
  role,
  onChanged,
}: {
  check: PipelineCheck
  role: string
  onChanged: () => Promise<unknown>
}) {
  const passed = check.status === 'passed'
  const canResolve = check.resolvable && (role === 'officer' || role === 'regional_officer')
  const [showResolve, setShowResolve] = useState(false)

  async function resolve(status: Resolution, reason: string) {
    const body = { status, reason }
    if (check.resolveKind === 'finding') await api.resolveFinding(role, check.id, body)
    else if (check.resolveKind === 'reconciliation')
      await api.resolveReconciliationItem(role, check.id, body)
    else if (check.resolveKind === 'forensics')
      await api.resolveForensicsIndicator(role, check.id, body)
    else await api.resolveDocVerificationCheck(role, check.id, body)
    await onChanged()
    setShowResolve(false)
  }

  return (
    <li
      className={`rounded border border-border border-l-4 px-3 py-2 text-xs ${
        passed ? 'border-l-[#8fa597]' : SEVERITY_BAR[check.severity]
      }`}
    >
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="font-medium text-ink">{check.title}</span>
        {passed ? (
          <Badge tone="pass">Passed</Badge>
        ) : (
          <Badge tone={SEVERITY_TONE[check.severity]}>{SEVERITY_LABEL[check.severity]}</Badge>
        )}
        {!passed && check.status !== 'open' && <Badge>{STATUS_LABEL[check.status] ?? check.status}</Badge>}
        {check.mode && <Badge tone={check.mode === 'real' ? 'pass' : 'neutral'}>{MODE_LABEL[check.mode]}</Badge>}
        {check.source && <span className="text-[10px] text-ink-muted">{check.source}</span>}
      </div>
      {check.detail && <p className="mt-0.5 text-ink-secondary">{check.detail}</p>}
      {(check.resolutionReason || check.limitations.length > 0 || (check.handbook && !passed)) && (
        <div className="mt-1 space-y-0.5">
          {check.resolutionReason && (
            <p className="text-[11px] text-ink-muted">Officer note: {check.resolutionReason}</p>
          )}
          {check.limitations.length > 0 && (
            <p className="text-[11px] text-ink-muted">Limitation: {check.limitations.join(' · ')}</p>
          )}
          {check.handbook && !passed && (
            <div>
              <HandbookBadge reference={check.handbook} />
            </div>
          )}
        </div>
      )}
      {canResolve && !showResolve && (
        <button
          type="button"
          className="mt-1.5 text-[11px] font-medium text-accent underline-offset-2 hover:underline"
          onClick={() => setShowResolve(true)}
        >
          Resolve…
        </button>
      )}
      {canResolve && showResolve && (
        <ResolveControl role={role} onResolve={resolve} />
      )}
    </li>
  )
}

