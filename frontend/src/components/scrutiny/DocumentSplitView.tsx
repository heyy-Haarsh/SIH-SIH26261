/**
 * DocumentSplitView — split-pane document inspection workspace.
 *
 * Layout:
 *   Left panel (240px)  → required document list with status chips
 *   Main panel          → authenticated PDF/image preview (fetched as blob)
 *   Right drawer        → extracted fields, verification checks, findings
 *
 * This component does NOT use <iframe src> because the file endpoints require
 * role-based auth headers. Files are fetched as blobs and rendered with:
 * - PdfEvidenceViewer (pdfjs) for PDFs
 * - <img> tag for images (after blob URL creation)
 *
 * Never invents page references, coordinates, or processing results.
 */
import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, FileSearch, FileText, FileX } from 'lucide-react'
import { PdfEvidenceViewer } from './PdfEvidenceViewer'
import { api } from '@/services/api'
import { useRefreshable } from '@/hooks/useRefreshable'
import { formatBytes, formatDate, formatDateTime, confidenceLabel } from '@/lib/format'
import { Badge } from '@/components/ui/Badge'
import { SEVERITY_TONE, SEVERITY_LABEL } from './scrutinyUi'
import type { ScrutinyReview, DocumentCard, DocumentReport } from '@/types'

interface Props {
  review: ScrutinyReview
  applicationId: string
  role: string
  /** If non-null, opens that document immediately */
  initialDocId?: string | null
  onChanged: () => Promise<unknown> | void
}

const FILE_ICON_COLOR: Record<string, string> = {
  pass: '#2E7D52',
  warning: '#B45309',
  failed: '#B91C1C',
  pending: '#888888',
}

function docStatusColor(doc: DocumentCard): string {
  if (doc.openIssueCount > 0 && doc.highestSeverity) {
    return SEVERITY_LABEL[doc.highestSeverity] ? '#B91C1C' : '#888888'
  }
  return '#2E7D52'
}

export function DocumentSplitView({ review, applicationId, role, initialDocId, onChanged }: Props) {
  const allDocs = review.documents

  // Selected document
  const [selectedId, setSelectedId] = useState<string | null>(
    initialDocId ?? allDocs[0]?.id ?? null,
  )
  const selectedDoc = allDocs.find((d) => d.id === selectedId) ?? allDocs[0] ?? null

  // Select initialDocId if it changes
  useEffect(() => {
    if (initialDocId) setSelectedId(initialDocId)
  }, [initialDocId])

  // Load report for selected doc
  const { data: report, loading: reportLoading, error: reportError } = useRefreshable<DocumentReport>(
    selectedId ? () => api.getDocumentReport(role, applicationId, selectedId) : null,
    `${applicationId}:${selectedId}`,
  )

  // Fetch file blob for preview
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [blobMime, setBlobMime] = useState<string | null>(null)
  const [blobLoading, setBlobLoading] = useState(false)
  const [blobError, setBlobError] = useState<string | null>(null)

  useEffect(() => {
    if (!selectedId) return
    let url: string | null = null
    setBlobLoading(true)
    setBlobUrl(null)
    setBlobMime(null)
    setBlobError(null)
    api
      .fetchDocumentFile(role, selectedId)
      .then(({ blob }) => {
        url = URL.createObjectURL(blob)
        setBlobUrl(url)
        setBlobMime(blob.type)
      })
      .catch((err) => setBlobError(err instanceof Error ? err.message : 'Could not load file.'))
      .finally(() => setBlobLoading(false))
    return () => {
      if (url) URL.revokeObjectURL(url)
    }
  }, [selectedId, role])

  // Right-pane detail section
  const [detailSection, setDetailSection] = useState<'fields' | 'checks'>('fields')

  const doc = report?.document
  const extractedFields = report?.extractedFields ?? []
  const checks = report?.stages?.flatMap((s) => s.checks) ?? []
  const openChecks = checks.filter((c) => c.outcome === 'failed' || c.outcome === 'warning')

  if (allDocs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center" style={{ background: '#FAFAFA', borderRadius: '12px' }}>
        <FileX size={32} className="mb-3" style={{ color: '#E0E0E0' }} />
        <div className="text-sm font-medium" style={{ color: '#333333' }}>
          No documents uploaded yet
        </div>
        <div className="text-[12px] mt-1" style={{ color: '#888888' }}>
          Required document slots:
        </div>
        <ul className="mt-2 text-[11px]" style={{ color: '#AAAAAA' }}>
          {review.missingDocuments.map((m) => (
            <li key={m.code}>{m.name} ({m.mandatory ? 'mandatory' : 'optional'})</li>
          ))}
        </ul>
      </div>
    )
  }

  return (
    <div
      className="flex overflow-hidden rounded-xl"
      style={{
        background: '#FFFFFF',
        border: '1px solid #F0F0F0',
        minHeight: '600px',
        maxHeight: '80vh',
      }}
    >
      {/* Left: document list */}
      <div
        className="overflow-y-auto shrink-0"
        style={{
          width: '220px',
          borderRight: '1px solid #F0F0F0',
          background: '#FAFAFA',
        }}
      >
        <div
          className="px-3 py-2.5 text-[11px] font-semibold uppercase tracking-widest"
          style={{ color: '#AAAAAA', borderBottom: '1px solid #F0F0F0' }}
        >
          Documents ({allDocs.length})
        </div>

        {/* Uploaded docs */}
        <ul>
          {allDocs.map((d) => (
            <li key={d.id}>
              <button
                type="button"
                onClick={() => setSelectedId(d.id)}
                className="w-full px-3 py-2.5 text-left transition-colors"
                style={{
                  background: selectedId === d.id ? '#F0F0F0' : 'transparent',
                  borderBottom: '1px solid #F0F0F0',
                }}
                aria-current={selectedId === d.id ? 'true' : undefined}
                aria-label={`Open ${d.name}`}
              >
                <div className="flex items-start gap-2">
                  <FileText
                    size={14}
                    className="mt-0.5 shrink-0"
                    style={{ color: docStatusColor(d) }}
                  />
                  <div className="min-w-0">
                    <div
                      className="truncate text-[12px] font-medium leading-tight"
                      style={{ color: '#111111' }}
                    >
                      {d.name}
                    </div>
                    <div className="text-[10px] mt-0.5 truncate" style={{ color: '#888888' }}>
                      v{d.version} · {formatBytes(d.sizeBytes)}
                    </div>
                    {d.openIssueCount > 0 && (
                      <div
                        className="mt-1 rounded px-1.5 py-0.5 text-[9px] font-semibold inline-block"
                        style={{ background: '#FEF2F2', color: '#B91C1C' }}
                      >
                        {d.openIssueCount} open issue{d.openIssueCount !== 1 ? 's' : ''}
                      </div>
                    )}
                  </div>
                </div>
              </button>
            </li>
          ))}
        </ul>

        {/* Missing docs */}
        {review.missingDocuments.length > 0 && (
          <>
            <div
              className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-widest"
              style={{ color: '#AAAAAA', borderBottom: '1px solid #F0F0F0' }}
            >
              Missing
            </div>
            {review.missingDocuments.map((m) => (
              <div
                key={m.code}
                className="flex items-start gap-2 px-3 py-2.5"
                style={{ borderBottom: '1px solid #F0F0F0' }}
              >
                <FileX size={14} className="mt-0.5 shrink-0" style={{ color: '#B45309' }} />
                <div className="min-w-0">
                  <div className="text-[11px] font-medium truncate" style={{ color: '#B45309' }}>
                    {m.name}
                  </div>
                  <div className="text-[10px]" style={{ color: '#AAAAAA' }}>
                    {m.mandatory ? 'Mandatory' : 'Optional'} · not uploaded
                  </div>
                </div>
              </div>
            ))}
          </>
        )}
      </div>

      {/* Center: file preview */}
      <div
        className="flex-1 overflow-auto flex flex-col"
        style={{ borderRight: '1px solid #F0F0F0', minWidth: 0 }}
      >
        {/* Preview header */}
        {selectedDoc && (
          <div
            className="flex items-center justify-between px-4 py-2.5 shrink-0"
            style={{ borderBottom: '1px solid #F0F0F0', background: '#FAFAFA' }}
          >
            <div>
              <div className="text-sm font-semibold" style={{ color: '#111111' }}>
                {selectedDoc.name}
              </div>
              <div className="text-[11px]" style={{ color: '#888888' }}>
                {selectedDoc.fileName} · v{selectedDoc.version} · {formatBytes(selectedDoc.sizeBytes)}
                {selectedDoc.uploadedAt && (
                  <> · Uploaded {formatDate(selectedDoc.uploadedAt)}</>
                )}
              </div>
            </div>
            {selectedDoc.highestSeverity && selectedDoc.openIssueCount > 0 && (
              <Badge tone={SEVERITY_TONE[selectedDoc.highestSeverity]}>
                {selectedDoc.openIssueCount} · {SEVERITY_LABEL[selectedDoc.highestSeverity]}
              </Badge>
            )}
          </div>
        )}

        {/* File preview */}
        <div className="flex-1 overflow-auto p-4">
          {blobLoading && (
            <div className="flex items-center justify-center py-12 text-sm" style={{ color: '#888888' }}>
              Loading document preview…
            </div>
          )}
          {blobError && !blobLoading && (
            <div
              className="rounded-xl px-4 py-3 text-sm"
              style={{ background: '#FEF2F2', color: '#991B1B', border: '1px solid #FECACA' }}
            >
              <div className="font-semibold mb-1">Could not load document preview</div>
              <div className="text-[12px]">{blobError}</div>
              <div className="text-[11px] mt-1" style={{ color: '#B91C1C' }}>
                The document was uploaded successfully but cannot be previewed here. The file may
                not be accessible in this environment or the format is unsupported.
              </div>
            </div>
          )}
          {blobUrl && blobMime?.includes('pdf') && (
            <PdfEvidenceViewer
              url={blobUrl}
              fileName={selectedDoc?.fileName ?? ''}
            />
          )}
          {blobUrl && blobMime && !blobMime.includes('pdf') && blobMime.startsWith('image/') && (
            <img
              src={blobUrl}
              alt={selectedDoc?.name ?? 'Document'}
              className="mx-auto max-w-full rounded border border-[#E0E0E0]"
            />
          )}
          {blobUrl && blobMime && !blobMime.includes('pdf') && !blobMime.startsWith('image/') && (
            <div
              className="rounded-xl px-4 py-3 text-sm"
              style={{ background: '#FFFBEB', color: '#92400E', border: '1px solid #FDE68A' }}
            >
              Preview not available for {blobMime} files. The document was uploaded successfully.
            </div>
          )}
          {!blobUrl && !blobLoading && !blobError && (
            <div className="flex items-center justify-center py-12" style={{ color: '#AAAAAA' }}>
              <FileSearch size={24} />
            </div>
          )}
        </div>
      </div>

      {/* Right: extraction details + checks */}
      <div
        className="overflow-y-auto shrink-0"
        style={{ width: '280px', background: '#FFFFFF' }}
      >
        {/* Section toggle */}
        <div
          className="flex items-center"
          style={{ borderBottom: '1px solid #F0F0F0' }}
        >
          {[
            { key: 'fields', label: `Fields (${extractedFields.length})` },
            { key: 'checks', label: `Checks (${openChecks.length} open)` },
          ].map((s) => (
            <button
              key={s.key}
              type="button"
              onClick={() => setDetailSection(s.key as 'fields' | 'checks')}
              className={`flex-1 px-3 py-2.5 text-[11px] font-medium transition-colors ${
                detailSection === s.key ? 'tab-active' : 'tab-inactive'
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>

        {reportLoading && (
          <div className="px-4 py-4 text-[12px] animate-pulse" style={{ color: '#AAAAAA' }}>
            Loading report…
          </div>
        )}
        {reportError && (
          <div className="px-4 py-3 text-[11px]" style={{ color: '#B91C1C' }}>
            Could not load report: {reportError}
          </div>
        )}

        {/* Extracted fields */}
        {detailSection === 'fields' && !reportLoading && (
          <div>
            {extractedFields.length === 0 ? (
              <div className="px-4 py-6 text-center text-[12px]" style={{ color: '#AAAAAA' }}>
                {report
                  ? 'No fields were extracted from this document.'
                  : 'Select a document to see extracted fields.'}
              </div>
            ) : (
              <ul>
                {extractedFields.map((f) => (
                  <li
                    key={f.id}
                    className="px-4 py-3"
                    style={{ borderBottom: '1px solid #F8F8F8' }}
                  >
                    <div className="text-[11px] font-medium" style={{ color: '#888888' }}>
                      {f.fieldName.replace(/_/g, ' ')}
                    </div>
                    <div className="text-[13px] font-semibold mt-0.5" style={{ color: '#111111' }}>
                      {f.value || <span style={{ color: '#AAAAAA' }}>—</span>}
                    </div>
                    <div className="flex flex-wrap gap-2 mt-1 text-[10px]" style={{ color: '#AAAAAA' }}>
                      {f.confidence != null && (
                        <span>Confidence: {confidenceLabel(f.confidence)}</span>
                      )}
                      {f.pageReference && <span>Page: {f.pageReference}</span>}
                      {f.method && <span>{f.method}</span>}
                    </div>
                    {f.isConflict && (
                      <div
                        className="mt-1 rounded px-1.5 py-0.5 text-[10px] font-semibold inline-flex items-center gap-1"
                        style={{ background: '#FEF2F2', color: '#B91C1C' }}
                      >
                        <AlertTriangle size={9} />
                        Conflict across documents
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* Verification checks */}
        {detailSection === 'checks' && !reportLoading && (
          <div>
            {checks.length === 0 ? (
              <div className="px-4 py-6 text-center text-[12px]" style={{ color: '#AAAAAA' }}>
                {report ? 'No verification checks for this document.' : 'Select a document.'}
              </div>
            ) : (
              <ul>
                {checks.map((c) => {
                  const isOpen = c.outcome === 'failed' || c.outcome === 'warning'
                  return (
                    <li
                      key={c.id}
                      className="px-4 py-3"
                      style={{ borderBottom: '1px solid #F8F8F8' }}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-[12px] font-medium truncate" style={{ color: '#111111' }}>
                          {c.title}
                        </div>
                        <span
                          className="shrink-0 rounded-md px-1.5 py-0.5 text-[9px] font-semibold uppercase"
                          style={{
                            background: c.outcome === 'pass' ? '#F0FDF4' : c.outcome === 'failed' ? '#FEF2F2' : '#FFFBEB',
                            color: c.outcome === 'pass' ? '#166534' : c.outcome === 'failed' ? '#991B1B' : '#92400E',
                          }}
                        >
                          {c.outcome}
                        </span>
                      </div>
                      {c.detail && (
                        <div className="text-[11px] mt-0.5 line-clamp-3" style={{ color: '#555555' }}>
                          {c.detail}
                        </div>
                      )}
                      {c.limitations.length > 0 && (
                        <div className="text-[10px] mt-1" style={{ color: '#AAAAAA' }}>
                          Limitations: {c.limitations.join(', ')}
                        </div>
                      )}
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
