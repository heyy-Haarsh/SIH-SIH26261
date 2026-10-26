import type { ApplicationStatus, Priority, ValidationOutcome, VerificationStatus } from '@/types'
import { Badge } from './Badge'

const statusMap: Record<ApplicationStatus, { label: string; tone: Parameters<typeof Badge>[0]['tone'] }> = {
  draft: { label: 'Draft', tone: 'neutral' },
  submitted: { label: 'Submitted', tone: 'info' },
  awaiting_review: { label: 'Awaiting Review', tone: 'pending' },
  under_review: { label: 'Under Review', tone: 'brand' },
  deficiency: { label: 'Deficiency', tone: 'warning' },
  manual_review: { label: 'Manual Review', tone: 'manual' },
  approved: { label: 'Approved', tone: 'pass' },
  rejected: { label: 'Rejected', tone: 'failed' },
  resubmitted: { label: 'Resubmitted', tone: 'info' },
}

const outcomeMap: Record<ValidationOutcome, { label: string; tone: Parameters<typeof Badge>[0]['tone'] }> = {
  pass: { label: 'Pass', tone: 'pass' },
  warning: { label: 'Warning', tone: 'warning' },
  failed: { label: 'Failed', tone: 'failed' },
  pending: { label: 'Pending', tone: 'pending' },
  manual_review: { label: 'Manual Review', tone: 'manual' },
  verification_unavailable: { label: 'Verification Unavailable', tone: 'neutral' },
}

const priorityMap: Record<Priority, { label: string; tone: Parameters<typeof Badge>[0]['tone'] }> = {
  low: { label: 'Low', tone: 'neutral' },
  medium: { label: 'Medium', tone: 'info' },
  high: { label: 'High', tone: 'warning' },
  critical: { label: 'Critical', tone: 'failed' },
}

const verificationMap: Record<
  VerificationStatus,
  { label: string; tone: Parameters<typeof Badge>[0]['tone'] }
> = {
  verified_by_source: { label: 'Verified by source', tone: 'pass' },
  mismatch_detected: { label: 'Mismatch detected', tone: 'failed' },
  expired: { label: 'Expired', tone: 'warning' },
  verification_pending: { label: 'Verification pending', tone: 'pending' },
  source_unavailable: { label: 'Source unavailable', tone: 'neutral' },
  manual_review_required: { label: 'Manual review required', tone: 'manual' },
  simulated_result: { label: 'Simulated result', tone: 'info' },
}

export function ApplicationStatusBadge({ status }: { status: ApplicationStatus }) {
  const cfg = statusMap[status]
  return <Badge tone={cfg.tone}>{cfg.label}</Badge>
}

export function OutcomeBadge({ outcome }: { outcome: ValidationOutcome }) {
  const cfg = outcomeMap[outcome]
  return <Badge tone={cfg.tone}>{cfg.label}</Badge>
}

export function PriorityBadge({ priority }: { priority: Priority }) {
  const cfg = priorityMap[priority]
  return <Badge tone={cfg.tone}>{cfg.label}</Badge>
}

export function VerificationBadge({ status }: { status: VerificationStatus }) {
  const cfg = verificationMap[status]
  return <Badge tone={cfg.tone}>{cfg.label}</Badge>
}
