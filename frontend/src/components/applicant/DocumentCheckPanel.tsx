import { AlertTriangle, CheckCircle2, CircleHelp, XCircle } from 'lucide-react'
import type { ReactNode } from 'react'
import { Badge } from '@/components/ui/Badge'
import {
  CLARITY_LABEL,
  TYPE_MATCH_LABEL,
  clarityTone,
  typeMatchTone,
  type Tone,
} from '@/lib/applicantStatus'
import type { DocumentCheck } from '@/types'

function ToneIcon({ tone }: { tone: Tone }) {
  if (tone === 'pass') return <CheckCircle2 size={14} className="text-status-pass" />
  if (tone === 'failed') return <XCircle size={14} className="text-status-failed" />
  if (tone === 'warning') return <AlertTriangle size={14} className="text-status-warning" />
  return <CircleHelp size={14} className="text-ink-muted" />
}

function Line({ tone, title, children }: { tone: Tone; title: ReactNode; children: ReactNode }) {
  return (
    <div className="flex gap-2">
      <span className="mt-0.5 shrink-0">
        <ToneIcon tone={tone} />
      </span>
      <div className="min-w-0">
        <div className="text-xs font-medium text-ink">{title}</div>
        <p className="text-xs text-ink-secondary">{children}</p>
      </div>
    </div>
  )
}

/**
 * Plain-language upload pre-check: does it look like the requested document, and can it be
 * read? Never says the document is authentic — that is decided later by the officer.
 */
export function DocumentCheckPanel({ check }: { check: DocumentCheck }) {
  const typeTone = typeMatchTone(check.typeMatch)
  const clarTone = clarityTone(check.clarity)
  return (
    <div
      className="space-y-2 rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2.5"
      data-testid="document-check"
    >
      <Line
        tone={typeTone}
        title={
          <span className="inline-flex items-center gap-2">
            Document type <Badge tone={typeTone}>{TYPE_MATCH_LABEL[check.typeMatch]}</Badge>
          </span>
        }
      >
        {check.typeMatchMessage}
      </Line>
      <Line
        tone={clarTone}
        title={
          <span className="inline-flex items-center gap-2">
            Upload clarity <Badge tone={clarTone}>{CLARITY_LABEL[check.clarity]}</Badge>
          </span>
        }
      >
        {check.clarityMessage}
      </Line>
      {check.languageNote && (
        <p className="border-t border-border pt-2 text-[11px] text-ink-muted">{check.languageNote}</p>
      )}
      <p className="text-[10px] text-ink-muted">
        This is an automatic pre-check only. The scrutiny officer makes every final decision.
      </p>
    </div>
  )
}
