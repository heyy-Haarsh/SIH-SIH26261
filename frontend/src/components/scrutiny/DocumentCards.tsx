import { FileText, FileX } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { formatBytes, formatDate } from '@/lib/format'
import type { DocumentCard, ScrutinyReview } from '@/types'
import { SEVERITY_BAR, SEVERITY_LABEL, SEVERITY_TONE } from './scrutinyUi'

interface Props {
  review: ScrutinyReview
  onOpen: (documentId: string) => void
}

function typeTone(m?: string): 'pass' | 'warning' | 'failed' | 'neutral' {
  if (m === 'matched') return 'pass'
  if (m === 'mismatch') return 'failed'
  if (m === 'unclear') return 'warning'
  return 'neutral'
}

function clarityTone(c?: string): 'pass' | 'warning' | 'failed' | 'neutral' {
  if (c === 'clear') return 'pass'
  if (c === 'unclear') return 'warning'
  if (c === 'unreadable') return 'failed'
  return 'neutral'
}

/** One clickable card per uploaded document; opens the preview and its verification report. */
export function DocumentCards({ review, onOpen }: Props) {
  return (
    <div className="space-y-3">
      <p className="text-xs text-ink-muted">
        Select a document to preview the file and read its full verification report (intake →
        OCR &amp; classification → Layer 1 → Layer 2 → Layer 3).
      </p>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {review.documents.map((doc) => (
          <Card key={doc.id} doc={doc} onOpen={onOpen} />
        ))}
        {review.missingDocuments.map((m) => (
          <div
            key={m.code}
            className="flex items-start gap-3 rounded-[var(--radius-md)] border border-dashed border-border bg-surface p-3"
          >
            <FileX size={20} className="mt-0.5 shrink-0 text-status-warning" />
            <div>
              <div className="text-sm font-medium text-status-warning">{m.name}</div>
              <div className="text-[11px] text-ink-muted">
                {m.mandatory ? 'Mandatory' : 'Optional'} · not uploaded
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function Card({ doc, onOpen }: { doc: DocumentCard; onOpen: (id: string) => void }) {
  const check = doc.documentCheck
  const bar = doc.highestSeverity ? SEVERITY_BAR[doc.highestSeverity] : 'border-l-[#8fa597]'
  return (
    <button
      type="button"
      onClick={() => onOpen(doc.id)}
      className={`flex flex-col gap-2 rounded-[var(--radius-md)] border border-border border-l-4 bg-white p-3 text-left transition-all hover:bg-surface-muted hover:shadow-[var(--shadow-card)] focus:outline-none focus-visible:ring-2 focus-visible:ring-brand ${bar}`}
      aria-label={`Open ${doc.name}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-start gap-2">
          <FileText size={18} className="mt-0.5 shrink-0 text-ink-muted" />
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-ink">{doc.name}</div>
            <div className="truncate text-[11px] text-ink-muted">
              {doc.fileName} · v{doc.version} · {formatBytes(doc.sizeBytes)} · {formatDate(doc.uploadedAt)}
            </div>
          </div>
        </div>
        {doc.openIssueCount > 0 && doc.highestSeverity ? (
          <Badge tone={SEVERITY_TONE[doc.highestSeverity]}>
            {doc.openIssueCount} open · {SEVERITY_LABEL[doc.highestSeverity]}
          </Badge>
        ) : (
          <Badge tone="pass">No open issues</Badge>
        )}
      </div>

      {check && (
        <div className="flex flex-wrap gap-1">
          <Badge tone={typeTone(check.typeMatch)}>
            type: {check.typeMatch.replace('_', ' ')}
          </Badge>
          <Badge tone={clarityTone(check.clarity)}>clarity: {check.clarity.replace('_', ' ')}</Badge>
        </div>
      )}

      <div className="mt-2 grid grid-cols-3 gap-1 text-[10px]">
        <span className="flex flex-col items-start gap-0.5 rounded border border-border bg-surface px-1.5 py-1">
          <span className="text-ink-muted">Rules</span>
          <span className="font-medium text-ink">{(doc.ruleValidationStatus ?? 'pending').replace(/_/g, ' ')}</span>
        </span>
        <span className="flex flex-col items-start gap-0.5 rounded border border-border bg-surface px-1.5 py-1">
          <span className="text-ink-muted">Ext. verify</span>
          <span className="font-medium text-ink">{(doc.externalVerificationStatus ?? 'pending').replace(/_/g, ' ')}</span>
        </span>
        <span className="flex flex-col items-start gap-0.5 rounded border border-border bg-surface px-1.5 py-1">
          <span className="text-ink-muted">Review</span>
          <span className="font-medium text-ink">{(doc.reviewStatus ?? 'pending').replace(/_/g, ' ')}</span>
        </span>
      </div>
    </button>
  )
}
