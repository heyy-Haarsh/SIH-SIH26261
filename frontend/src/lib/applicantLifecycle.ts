/**
 * The single place where backend state becomes institution-facing wording and presentation.
 *
 * The server owns the mapping from persisted status to stage (applicant_lifecycle.py) and sends
 * `stage`, `stageLabel` and `lifecycle`. This file only decides how a stage looks, so no screen
 * invents its own labels, timelines or "approved" wording.
 */
import {
  CircleDashed,
  CircleDot,
  FilePen,
  Hourglass,
  MessageSquareWarning,
  RefreshCw,
  Scale,
  Send,
  type LucideIcon,
} from 'lucide-react'
import type {
  ApplicantApplicationSummary,
  ApplicantStage,
  ClarificationState,
  FindingStatus,
  ProcessingState,
} from '@/types'

export type Tone = 'neutral' | 'pass' | 'warning' | 'failed' | 'pending' | 'manual' | 'info' | 'brand'

export interface StagePresentation {
  label: string
  icon: LucideIcon
  tone: Tone
  /** What this means for the institution, in one sentence. Never claims compliance or approval. */
  meaning: string
}

export const STAGE: Record<ApplicantStage, StagePresentation> = {
  draft: {
    label: 'Draft',
    icon: FilePen,
    tone: 'neutral',
    meaning: 'Saved privately. Nothing has been sent to the scrutiny team.',
  },
  submitted: {
    label: 'Submitted',
    icon: Send,
    tone: 'neutral',
    meaning: 'Received. It is waiting to be picked up.',
  },
  processing: {
    label: 'Processing',
    icon: Hourglass,
    tone: 'pending',
    meaning: 'Documents are being read by automated tools. This is not a compliance check.',
  },
  scrutiny: {
    label: 'Under Scrutiny',
    icon: Scale,
    tone: 'brand',
    meaning: 'An officer is reviewing the application.',
  },
  applicant_action: {
    label: 'Action Required',
    icon: MessageSquareWarning,
    tone: 'warning',
    meaning: 'The officer has asked for something only your institution can provide.',
  },
  resubmitted: {
    label: 'Resubmitted',
    icon: RefreshCw,
    tone: 'info',
    meaning: 'Your response was sent back for review.',
  },
  decision_recorded: {
    label: 'Decision Recorded',
    icon: CircleDot,
    tone: 'pass',
    meaning: 'An officer has recorded a decision. This is a recommendation, not a final approval.',
  },
}

export function stagePresentation(stage: string | undefined | null): StagePresentation {
  return (
    STAGE[(stage ?? 'draft') as ApplicantStage] ?? {
      label: 'In progress',
      icon: CircleDashed,
      tone: 'neutral',
      meaning: '',
    }
  )
}

/** Dashboard card keys. Each maps to exactly one backend count and one table filter. */
export type CardKey = 'active' | 'action_required' | 'under_scrutiny' | 'decision_recorded'

export const CARD_LABEL: Record<CardKey, string> = {
  active: 'Active Applications',
  action_required: 'Action Required',
  under_scrutiny: 'Under Scrutiny',
  decision_recorded: 'Decision Recorded',
}

export const CARD_HINT: Record<CardKey, string> = {
  active: 'Submitted and not yet decided',
  action_required: 'Waiting on your response',
  under_scrutiny: 'With an officer, including resubmissions',
  decision_recorded: 'An officer has recorded a decision',
}

/** Same definitions as the backend counts, so a card number always equals its filtered table. */
export function matchesCard(app: ApplicantApplicationSummary, key: CardKey): boolean {
  switch (key) {
    case 'active':
      return ['submitted', 'processing', 'scrutiny', 'applicant_action', 'resubmitted'].includes(app.stage)
    case 'action_required':
      return app.openClarifications > 0
    case 'under_scrutiny':
      return app.stage === 'scrutiny' || app.stage === 'resubmitted'
    case 'decision_recorded':
      return app.stage === 'decision_recorded'
  }
}

export const CLARIFICATION_STATE: Record<ClarificationState, { label: string; tone: Tone; hint: string }> = {
  action_required: {
    label: 'Action required',
    tone: 'warning',
    hint: 'The officer is waiting for your response.',
  },
  response_saved: {
    label: 'Response saved',
    tone: 'info',
    hint: 'Saved, but not yet sent. Resubmit the application so the officer can see it.',
  },
  awaiting_review: {
    label: 'Awaiting review',
    tone: 'brand',
    hint: 'Sent. The officer has not closed this request yet.',
  },
  resolved: {
    label: 'Resolved',
    tone: 'pass',
    hint: 'The officer has closed this request.',
  },
}

export const FINDING_STATUS_TONE: Record<FindingStatus, Tone> = {
  open: 'neutral',
  response_needed: 'warning',
  response_submitted: 'info',
  resolved: 'pass',
  waived: 'pass',
  accepted: 'pass',
  rechecked: 'info',
}

export const PROCESSING: Record<ProcessingState, { label: string; tone: Tone }> = {
  ready: { label: 'Read successfully', tone: 'neutral' },
  limited: { label: 'Only partly readable', tone: 'warning' },
  failed: { label: 'Could not be read', tone: 'warning' },
  processing: { label: 'Being processed', tone: 'pending' },
  not_run: { label: 'Waiting to be processed', tone: 'pending' },
}

export function processingPresentation(state: string | undefined | null) {
  return PROCESSING[(state ?? 'not_run') as ProcessingState] ?? PROCESSING.not_run
}

/** Plain-language reasons an upload or read can fail. Never blames the institution for a system limit. */
export function uploadErrorMessage(code: string | undefined, fallback: string): string {
  switch (code) {
    case 'file_too_large':
      return 'This file is larger than the upload limit. Compress it or rescan at a lower resolution.'
    case 'unsupported_file_type':
    case 'unsupported_type':
      return 'This file type is not accepted. Use PDF, PNG, JPG, DOCX or TXT.'
    case 'empty_file':
      return 'The file is empty. Choose a file that has content.'
    default:
      return fallback
  }
}

export const DECLARATION_FALLBACK = [
  'The information provided is accurate to the best of my knowledge.',
  'I am authorised to submit this application on behalf of the institution.',
]
