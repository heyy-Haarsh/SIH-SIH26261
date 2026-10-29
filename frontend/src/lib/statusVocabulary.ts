/**
 * Central status vocabulary for PRAMAN.
 * Processing complete ≠ rule pass ≠ external confirmation ≠ official approval.
 */

import type {
  ApplicationStage,
  ApplicationStatus,
  Priority,
  ValidationOutcome,
  VerificationStatus,
} from '@/types'
import type { Tone } from '@/lib/applicantStatus'

export type StatusPresentation = { label: string; tone: Tone; meaning?: string }

/** Workflow lifecycle — what stage the application is in. */
export const APPLICATION_STATUS: Record<ApplicationStatus, StatusPresentation> = {
  draft: {
    label: 'Draft',
    tone: 'neutral',
    meaning: 'Not submitted. The applicant can still edit and upload documents.',
  },
  submitted: {
    label: 'Submitted',
    tone: 'info',
    meaning: 'Received and waiting for automatic checks or officer pickup.',
  },
  processing: {
    label: 'Processing',
    tone: 'pending',
    meaning: 'Documents are being checked automatically. Not a compliance verdict.',
  },
  under_scrutiny: {
    label: 'Under scrutiny',
    tone: 'brand',
    meaning: 'A scrutiny officer is reviewing the case.',
  },
  clarification_required: {
    label: 'Action needed',
    tone: 'warning',
    meaning: 'The officer asked for clarification. The applicant must respond.',
  },
  resubmitted: {
    label: 'Resubmitted',
    tone: 'info',
    meaning: 'Applicant responded; waiting for officer review of the new material.',
  },
  recommended: {
    label: 'Recommended',
    tone: 'pass',
    meaning: 'An authorized officer recorded a recommendation. Not an automated approval.',
  },
  rejected: {
    label: 'Rejected',
    tone: 'failed',
    meaning: 'An authorized officer recorded a rejection with a reason.',
  },
  awaiting_review: { label: 'Awaiting review', tone: 'pending' },
  under_review: { label: 'Under review', tone: 'brand' },
  deficiency: { label: 'Action needed', tone: 'warning' },
  manual_review: { label: 'Manual review', tone: 'manual' },
  approved: {
    label: 'Recommended',
    tone: 'pass',
    meaning: 'Legacy label mapped to an officer recommendation.',
  },
}

export const APPLICATION_STAGE: Record<ApplicationStage, StatusPresentation> = {
  draft: { label: 'Draft', tone: 'neutral' },
  awaiting_scrutiny: { label: 'Awaiting scrutiny', tone: 'info' },
  under_scrutiny: { label: 'Under scrutiny', tone: 'brand' },
  awaiting_applicant: { label: 'Awaiting applicant', tone: 'warning' },
  decided: { label: 'Decided', tone: 'pass' },
}

/** Rule / validation outcome — not authenticity. */
export const VALIDATION_OUTCOME: Record<ValidationOutcome, StatusPresentation> = {
  pass: {
    label: 'Rule pass',
    tone: 'pass',
    meaning: 'A configured rule passed. Does not prove the document is genuine.',
  },
  warning: { label: 'Warning', tone: 'warning' },
  failed: { label: 'Rule failed', tone: 'failed' },
  pending: { label: 'Not evaluated', tone: 'pending' },
  manual_review: { label: 'Needs human review', tone: 'manual' },
  verification_unavailable: {
    label: 'Check unavailable',
    tone: 'neutral',
    meaning: 'The check could not run. Not the same as a failed authenticity check.',
  },
}

/** External / Layer-2 style statuses. */
export const VERIFICATION_STATUS: Record<VerificationStatus, StatusPresentation> = {
  verified_by_source: {
    label: 'Confirmed by source',
    tone: 'pass',
    meaning: 'An authorized source returned a supported confirmation for the queried fields.',
  },
  mismatch_detected: { label: 'Mismatch with source', tone: 'failed' },
  expired: { label: 'Expired per source', tone: 'warning' },
  verification_pending: { label: 'Verification pending', tone: 'pending' },
  source_unavailable: {
    label: 'Source unavailable',
    tone: 'neutral',
    meaning: 'No authorized connector answered. Authenticity remains unconfirmed by that source.',
  },
  manual_review_required: { label: 'Manual review required', tone: 'manual' },
  simulated_result: {
    label: 'Simulated result',
    tone: 'info',
    meaning: 'Demo issuer only. Not official verification. official_verification is always false.',
  },
}

export const PRIORITY: Record<Priority, StatusPresentation> = {
  low: { label: 'Low priority', tone: 'neutral', meaning: 'Queue ordering aid only — not a fraud score.' },
  medium: { label: 'Medium priority', tone: 'info', meaning: 'Queue ordering aid only — not a fraud score.' },
  high: { label: 'High priority', tone: 'warning', meaning: 'Queue ordering aid only — not a fraud score.' },
  critical: {
    label: 'Critical priority',
    tone: 'failed',
    meaning: 'Queue ordering aid only — not a fraud score or fraud probability.',
  },
}

export function applicationStatusPresentation(status: ApplicationStatus): StatusPresentation {
  return (
    APPLICATION_STATUS[status] ?? {
      label: String(status).replace(/_/g, ' '),
      tone: 'neutral' as Tone,
    }
  )
}

export function verificationStatusPresentation(status: VerificationStatus): StatusPresentation {
  return VERIFICATION_STATUS[status] ?? { label: String(status), tone: 'neutral' as Tone }
}
