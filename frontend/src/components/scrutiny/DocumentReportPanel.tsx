import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Clock,
  Download,
  ExternalLink,
  FileText,
  History,
  Settings2,
  X,
} from 'lucide-react'
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

/** Full-screen document viewer: preview + versions | verification summary stepper. */
export function DocumentReportPanel({ role, applicationId, documentId, onClose, onChanged }: Props) {
  const { data, loading, error, reload } = useRefreshable(
    () => api.getDocumentReport(role, applicationId, documentId),
    `${applicationId}:${documentId}`,
  )
  const [showFields, setShowFields] = useState(false)
  const [focusFieldId, setFocusFieldId] = useState<string | null>(null)
  const [expandAll, setExpandAll] = useState(false)
  const [downloadBusy, setDownloadBusy] = useState(false)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const doc = data?.document
  const afterResolve = async () => {
    await Promise.all([reload(), onChanged()])
  }

  const focused = data?.extractedFields.find((f) => f.id === focusFieldId)

  async function downloadOriginal() {
    if (!doc) return
    setDownloadBusy(true)
    try {
      const { blob, fileName } = await api.fetchDocumentFile(role, doc.id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = fileName ?? doc.fileName
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } finally {
      setDownloadBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-stretch justify-center bg-black/45 p-0 sm:p-4" onClick={onClose}>
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={doc ? `${doc.name} report` : 'Document report'}
        className="flex h-full w-full max-w-6xl flex-col overflow-hidden bg-white shadow-xl sm:rounded-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <header className="flex shrink-0 items-start justify-between gap-3 border-b border-border px-4 py-3 sm:px-5">
          <div className="flex min-w-0 items-start gap-2.5">
            <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#EFF6FF] text-[#1D4ED8]">
              <FileText size={16} />
            </span>
            <div className="min-w-0">
              <h2 className="truncate text-base font-semibold text-ink">{doc?.name ?? 'Document'}</h2>
              {doc && (
                <p className="mt-0.5 truncate text-[11px] text-ink-muted">
                  {doc.fileName} · v{doc.version} · {formatBytes(doc.sizeBytes)} · uploaded{' '}
                  {formatDateTime(doc.uploadedAt)}
                </p>
              )}
            </div>
          </div>
          <Button size="sm" variant="outline" leftIcon={<X size={14} />} onClick={onClose}>
            Close
          </Button>
        </header>

        {/* Body */}
        <div className="min-h-0 flex-1 overflow-y-auto">
          {loading && <p className="p-6 text-sm text-ink-muted">Loading report…</p>}
          {error && !data && (
            <p className="p-6 text-sm text-status-failed" role="alert">
              {error}
            </p>
          )}
          {data && doc && (
            <div className="grid gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:gap-5 lg:p-5">
              {/* Left — preview + versions */}
              <div className="space-y-4">
                <section className="overflow-hidden rounded-xl border border-border bg-white">
                  <div className="border-b border-border px-4 py-3">
                    <h3 className="text-sm font-semibold text-ink">Document preview</h3>
                    <p className="mt-0.5 text-[11px] text-ink-muted">
                      Select a field in the verification pipeline to view highlights (if available).
                    </p>
                  </div>
                  <div className="p-3 sm:p-4">
                    <DocumentPreview
                      role={role}
                      documentId={doc.id}
                      mimeType={doc.mimeType}
                      fileName={doc.fileName}
                      version={doc.version}
                      highlightPage={focused?.pageNumber ?? null}
                      highlightBBox={focused?.bbox ?? null}
                      highlightLabel={focused?.fieldName ?? null}
                      hideDownload
                    />
                  </div>
                </section>

                <section className="overflow-hidden rounded-xl border border-border bg-white">
                  <div className="flex items-center gap-2 border-b border-border px-4 py-2.5">
                    <History size={14} className="text-ink-muted" />
                    <h3 className="text-sm font-semibold text-ink">Versions</h3>
                  </div>
                  <ul className="divide-y divide-border">
                    {data.versions.map((v) => (
                      <li
                        key={v.version}
                        className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2.5 text-xs"
                      >
                        <span className="font-semibold text-ink">v{v.version}</span>
                        <span className="min-w-0 truncate text-ink-secondary">{v.fileName}</span>
                        <span className="text-ink-muted">{formatBytes(v.sizeBytes)}</span>
                        <span className="text-ink-muted">{formatDateTime(v.uploadedAt)}</span>
                        <span className="font-mono text-[10px] text-ink-muted">{v.sha256.slice(0, 10)}…</span>
                        {v.isCurrent ? (
                          <Badge tone="brand" className="ml-auto">
                            Current
                          </Badge>
                        ) : (
                          <Badge className="ml-auto">earlier</Badge>
                        )}
                      </li>
                    ))}
                  </ul>
                </section>

                <section className="overflow-hidden rounded-xl border border-border bg-white">
                  <button
                    type="button"
                    className="flex w-full items-center gap-1.5 px-4 py-2.5 text-left text-sm font-semibold text-ink"
                    onClick={() => setShowFields((v) => !v)}
                  >
                    {showFields ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    Fields read from this document ({data.extractedFields.length})
                  </button>
                  {showFields && (
                    <div className="overflow-x-auto border-t border-border px-4 pb-3">
                      <table className="w-full text-left text-xs">
                        <thead>
                          <tr className="border-b border-border uppercase text-ink-muted">
                            <th className="py-1.5 pr-2">Field</th>
                            <th className="py-1.5 pr-2">Value</th>
                            <th className="py-1.5 pr-2">Page</th>
                            <th className="py-1.5">Confidence</th>
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
                              <td className="py-1.5 pr-2 font-medium text-ink">
                                {f.fieldName.replace(/_/g, ' ')}
                                {f.isConflict && (
                                  <Badge tone="warning" className="ml-1">
                                    conflict
                                  </Badge>
                                )}
                              </td>
                              <td className="py-1.5 pr-2">{f.value}</td>
                              <td className="py-1.5 pr-2 text-ink-muted">{f.pageReference ?? '—'}</td>
                              <td className="py-1.5 text-ink-muted">{confidenceLabel(f.confidence)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>
              </div>

              {/* Right — verification summary stepper */}
              <div className="space-y-3">
                <div className="rounded-xl border border-border bg-white px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Settings2 size={14} className="text-ink-muted" />
                    <h3 className="text-sm font-semibold text-ink">Verification summary</h3>
                  </div>
                  <p className="mt-0.5 text-[11px] text-ink-muted">
                    Automated checks and extraction results for this document.
                  </p>
                </div>

                <ol className="relative space-y-3 pl-2">
                  {data.stages.map((s, idx) => (
                    <StageStepperItem
                      key={s.key}
                      index={idx + 1}
                      stage={s}
                      role={role}
                      forceOpen={expandAll || s.status === 'failed' || s.status === 'manual_review' || s.status === 'warning'}
                      onChanged={afterResolve}
                      isLast={idx === data.stages.length - 1}
                    />
                  ))}
                </ol>

                <p className="rounded-lg border border-border bg-surface px-3 py-2 text-[11px] text-ink-muted">
                  {data.disclaimer}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Footer actions */}
        {doc && (
          <footer className="flex shrink-0 flex-wrap items-center justify-end gap-2 border-t border-border bg-[#FAFAFA] px-4 py-3 sm:px-5">
            <Button
              size="sm"
              leftIcon={<ExternalLink size={14} />}
              onClick={() => {
                setExpandAll(true)
                setShowFields(true)
              }}
            >
              Open full verification report
            </Button>
            <Button
              size="sm"
              variant="outline"
              leftIcon={<Download size={14} />}
              disabled={downloadBusy}
              onClick={() => void downloadOriginal()}
            >
              Download original
            </Button>
          </footer>
        )}
      </aside>
    </div>
  )
}

function StageStepperItem({
  index,
  stage,
  role,
  forceOpen,
  onChanged,
  isLast,
}: {
  index: number
  stage: PipelineStage
  role: string
  forceOpen: boolean
  onChanged: () => Promise<unknown>
  isLast: boolean
}) {
  const noisy = stage.status === 'pass' || stage.status === 'not_run'
  const [open, setOpen] = useState(!noisy || forceOpen)
  useEffect(() => {
    if (forceOpen) setOpen(true)
  }, [forceOpen])

  const concerning = useMemo(
    () => stage.checks.filter((c) => c.status === 'open' && c.severity !== 'info'),
    [stage.checks],
  )
  const openFailed = concerning.filter((c) => c.severity === 'failed')
  const openReview = concerning.filter((c) => c.severity === 'manual_review' || c.severity === 'warning')

  return (
    <li className="relative flex gap-3">
      {!isLast && (
        <span
          className="absolute left-[11px] top-7 bottom-[-12px] w-px bg-border"
          aria-hidden
        />
      )}
      <span
        className="relative z-[1] flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border bg-white text-[11px] font-semibold text-ink"
      >
        {index}
      </span>
      <section className="min-w-0 flex-1 overflow-hidden rounded-xl border border-border bg-white">
        <button
          type="button"
          className="flex w-full items-center justify-between gap-2 px-3.5 py-2.5 text-left"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
        >
          <span className="flex min-w-0 items-center gap-2 text-sm font-semibold text-ink">
            {open ? <ChevronDown size={14} className="shrink-0 text-ink-muted" /> : <ChevronRight size={14} className="shrink-0 text-ink-muted" />}
            <span className="truncate">{stage.title}</span>
          </span>
          <Badge tone={STAGE_TONE[stage.status]}>{STAGE_LABEL[stage.status]}</Badge>
        </button>

        {open && (
          <div className="space-y-2.5 border-t border-border px-3.5 py-3">
            {stage.summary && (
              <p className="rounded-lg border border-[#BFDBFE] bg-[#EFF6FF] px-3 py-2 text-xs text-[#1E3A5F]">
                {stage.summary}
              </p>
            )}

            {stage.details.length > 0 && (
              <dl className="grid gap-x-3 gap-y-1 rounded-lg border border-[#BFDBFE] bg-[#EFF6FF] px-3 py-2 text-xs sm:grid-cols-2">
                {stage.details.map((d) => (
                  <div key={d.label} className="flex gap-2">
                    <dt className="shrink-0 text-[#64748B]">{d.label}:</dt>
                    <dd className="min-w-0 break-all font-medium text-ink">{d.value}</dd>
                  </div>
                ))}
              </dl>
            )}

            {/* Status chips for classification-style stages */}
            {stage.key === 'classification' && stage.checks.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {stage.checks.slice(0, 4).map((c) => (
                  <span
                    key={c.id}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-[#BFDBFE] bg-[#EFF6FF] px-2.5 py-1.5 text-[11px] font-medium text-[#1D4ED8]"
                  >
                    <Settings2 size={11} />
                    {c.title}: {c.outcome || (c.status === 'passed' ? 'Completed' : STATUS_LABEL[c.status] ?? c.status)}
                  </span>
                ))}
              </div>
            )}

            {openFailed.map((c) => (
              <AlertBox key={c.id} tone="failed" title={c.title} detail={c.detail} />
            ))}
            {openReview.map((c) => (
              <AlertBox key={c.id} tone="warning" title={c.title} detail={c.detail} />
            ))}

            {stage.limitations.length > 0 && (
              <div className="space-y-1.5">
                {stage.limitations.map((l) => (
                  <AlertBox key={l} tone="warning" title="Limitation" detail={l} />
                ))}
              </div>
            )}

            {stage.checks.length > 0 && (
              <ul className="space-y-1.5">
                {stage.checks.map((c) => (
                  <CheckRow key={c.id} check={c} role={role} onChanged={onChanged} />
                ))}
              </ul>
            )}

            {stage.checks.length === 0 && concerning.length === 0 && !stage.summary && (
              <p className="rounded-lg border border-[#BFDBFE] bg-[#EFF6FF] px-3 py-2 text-xs text-[#64748B]">
                Available results and evidence appear here after processing.
              </p>
            )}
          </div>
        )}
      </section>
    </li>
  )
}

function AlertBox({
  tone,
  title,
  detail,
}: {
  tone: 'failed' | 'warning'
  title: string
  detail?: string | null
}) {
  const failed = tone === 'failed'
  return (
    <div
      className={`flex items-start gap-2 rounded-lg border px-3 py-2.5 text-xs ${
        failed
          ? 'border-[#FECACA] bg-[#FEF2F2] text-[#991B1B]'
          : 'border-[#FDE68A] bg-[#FFFBEB] text-[#92400E]'
      }`}
    >
      {failed ? (
        <AlertTriangle size={14} className="mt-0.5 shrink-0" />
      ) : (
        <Clock size={14} className="mt-0.5 shrink-0" />
      )}
      <div className="min-w-0">
        <p className="font-semibold">{title}</p>
        {detail && <p className="mt-0.5 leading-relaxed opacity-90">{detail}</p>}
      </div>
    </div>
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

  // Failed/review already surfaced as AlertBox — keep row compact for the rest / resolve.
  if (!passed && check.status === 'open' && (check.severity === 'failed' || check.severity === 'manual_review' || check.severity === 'warning')) {
    return canResolve ? (
      <li className="flex justify-end">
        {!showResolve ? (
          <button
            type="button"
            className="text-[11px] font-medium text-accent hover:underline"
            onClick={() => setShowResolve(true)}
          >
            Resolve →
          </button>
        ) : (
          <div className="w-full">
            <ResolveControl role={role} onResolve={resolve} />
          </div>
        )}
      </li>
    ) : null
  }

  return (
    <li
      className={`rounded-lg border border-border border-l-4 px-3 py-2 text-xs ${
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
        {check.mode && (
          <Badge tone={check.mode === 'real' ? 'pass' : 'neutral'}>{MODE_LABEL[check.mode]}</Badge>
        )}
      </div>
      {check.detail && <p className="mt-0.5 text-ink-secondary">{check.detail}</p>}
      {check.handbook && !passed && (
        <div className="mt-1">
          <HandbookBadge reference={check.handbook} />
        </div>
      )}
      {canResolve && !showResolve && (
        <button
          type="button"
          className="mt-1.5 text-[11px] font-medium text-accent hover:underline"
          onClick={() => setShowResolve(true)}
        >
          Resolve →
        </button>
      )}
      {canResolve && showResolve && <ResolveControl role={role} onResolve={resolve} />}
    </li>
  )
}
