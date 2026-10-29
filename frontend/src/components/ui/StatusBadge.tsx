import type { ApplicationStatus, Priority, ValidationOutcome, VerificationStatus } from '@/types'
import { Badge } from './Badge'
import {
  APPLICATION_STATUS,
  PRIORITY,
  VALIDATION_OUTCOME,
  VERIFICATION_STATUS,
  applicationStatusPresentation,
} from '@/lib/statusVocabulary'

export function ApplicationStatusBadge({ status }: { status: ApplicationStatus }) {
  const cfg = applicationStatusPresentation(status)
  return (
    <Badge tone={cfg.tone} title={cfg.meaning}>
      {cfg.label}
    </Badge>
  )
}

export function OutcomeBadge({ outcome }: { outcome: ValidationOutcome }) {
  const cfg = VALIDATION_OUTCOME[outcome] ?? { label: outcome, tone: 'neutral' as const }
  return (
    <Badge tone={cfg.tone} title={cfg.meaning}>
      {cfg.label}
    </Badge>
  )
}

export function PriorityBadge({ priority }: { priority: Priority }) {
  const cfg = PRIORITY[priority] ?? { label: priority, tone: 'neutral' as const }
  return (
    <Badge tone={cfg.tone} title={cfg.meaning}>
      {cfg.label}
    </Badge>
  )
}

export function VerificationBadge({ status }: { status: VerificationStatus }) {
  const cfg = VERIFICATION_STATUS[status] ?? { label: status, tone: 'neutral' as const }
  return (
    <Badge tone={cfg.tone} title={cfg.meaning}>
      {cfg.label}
    </Badge>
  )
}

/** Re-export maps for screens that need labels without rendering a badge. */
export { APPLICATION_STATUS, PRIORITY, VALIDATION_OUTCOME, VERIFICATION_STATUS }
