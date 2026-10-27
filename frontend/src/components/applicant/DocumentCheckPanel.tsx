import { AlertTriangle, CheckCircle2, CircleHelp, XCircle } from 'lucide-react'
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
  if (tone === 'pass') return <CheckCircle2 size={13} className="text-status-pass" />
  if (tone === 'failed') return <XCircle size={13} className="text-status-failed" />
  if (tone === 'warning') return <AlertTriangle size={13} className="text-status-warning" />
  return <CircleHelp size={13} className="text-ink-muted" />
}

/**
 * Type-match and clarity chips. Full sentences appear only when the applicant must act.
 * Never claims the document is authentic.
 */
export function DocumentCheckPanel({
  check,
  compact = false,
}: {
  check: DocumentCheck
  compact?: boolean
}) {
  const typeTone = typeMatchTone(check.typeMatch)
  const clarTone = clarityTone(check.clarity)
  const typeNeedsWork = check.typeMatch === 'mismatch' || check.typeMatch === 'unclear'
  const clarityNeedsWork = check.clarity === 'unclear' || check.clarity === 'unreadable'

  return (
    <div className="space-y-2" data-testid="document-check">
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1.5">
          <ToneIcon tone={typeTone} />
          <Badge tone={typeTone}>{TYPE_MATCH_LABEL[check.typeMatch]}</Badge>
        </span>
        <span className="inline-flex items-center gap-1.5">
          <ToneIcon tone={clarTone} />
          <Badge tone={clarTone}>{CLARITY_LABEL[check.clarity]}</Badge>
        </span>
      </div>
      {!compact && (
        <>
          {typeNeedsWork && (
            <p className="text-xs text-ink-secondary">{check.typeMatchMessage}</p>
          )}
          {clarityNeedsWork && (
            <p className="text-xs text-ink-secondary">{check.clarityMessage}</p>
          )}
        </>
      )}
      {compact && (typeNeedsWork || clarityNeedsWork) && (
        <p className="text-xs text-ink-secondary">
          {typeNeedsWork ? check.typeMatchMessage : check.clarityMessage}
        </p>
      )}
    </div>
  )
}
