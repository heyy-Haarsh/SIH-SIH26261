import type {
  ApplicantApplication,
  ApplicantUploadStatus,
  ApplicationStatus,
  ClarityState,
  TypeMatchState,
} from '@/types'

export type Tone = 'neutral' | 'pass' | 'warning' | 'failed' | 'pending' | 'manual' | 'info' | 'brand'

export function applicationStatusTone(status: ApplicationStatus): Tone {
  switch (status) {
    case 'clarification_required':
    case 'deficiency':
      return 'warning'
    case 'recommended':
    case 'approved':
      return 'pass'
    case 'rejected':
      return 'failed'
    case 'processing':
      return 'pending'
    case 'under_scrutiny':
    case 'under_review':
    case 'awaiting_review':
    case 'manual_review':
      return 'brand'
    default:
      return 'info'
  }
}

export function uploadStatusTone(status: ApplicantUploadStatus): Tone {
  switch (status) {
    case 'uploaded':
    case 'replaced':
      return 'pass'
    case 'needs_attention':
      return 'warning'
    default:
      return 'neutral'
  }
}

export function typeMatchTone(state: TypeMatchState): Tone {
  switch (state) {
    case 'matched':
      return 'pass'
    case 'mismatch':
      return 'failed'
    case 'unclear':
      return 'warning'
    default:
      return 'neutral'
  }
}

export function clarityTone(state: ClarityState): Tone {
  switch (state) {
    case 'clear':
      return 'pass'
    case 'unclear':
      return 'warning'
    case 'unreadable':
      return 'failed'
    default:
      return 'neutral'
  }
}

export const TYPE_MATCH_LABEL: Record<TypeMatchState, string> = {
  matched: 'Looks like the right document',
  mismatch: 'May be the wrong document',
  unclear: 'Could not confirm document type',
  not_checked: 'Type not checked',
}

export const CLARITY_LABEL: Record<ClarityState, string> = {
  clear: 'Clear and readable',
  unclear: 'Hard to read',
  unreadable: 'Could not be read',
  not_checked: 'Readability not checked',
}

/** Mandatory documents still missing (applicant-facing "what do I still have to do"). */
export function missingMandatory(app: Pick<ApplicantApplication, 'requirements'>): string[] {
  return app.requirements
    .filter((r) => r.mandatory && r.uploadStatus === 'not_uploaded')
    .map((r) => r.name)
}

export function documentsNeedingAttention(app: Pick<ApplicantApplication, 'requirements'>): string[] {
  return app.requirements.filter((r) => r.uploadStatus === 'needs_attention').map((r) => r.name)
}
