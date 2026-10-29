import type { IssueSeverity, StageStatus } from '@/types'

export type Tone = 'pass' | 'failed' | 'warning' | 'manual' | 'info' | 'neutral' | 'pending' | 'brand'

export const SEVERITY_LABEL: Record<IssueSeverity, string> = {
  failed: 'Failed',
  manual_review: 'Needs review',
  warning: 'Warning',
  info: 'Note',
}

export const SEVERITY_TONE: Record<IssueSeverity, Tone> = {
  failed: 'failed',
  manual_review: 'manual',
  warning: 'warning',
  info: 'info',
}

/** Left accent colour for issue / indicator cards. */
export const SEVERITY_BAR: Record<IssueSeverity, string> = {
  failed: 'border-l-[#a8665f]',
  manual_review: 'border-l-[#8478a3]',
  warning: 'border-l-[#a98a4f]',
  info: 'border-l-[#7f98b5]',
}

export const STAGE_LABEL: Record<StageStatus, string> = {
  pass: 'Passed',
  warning: 'Warning',
  failed: 'Failed',
  manual_review: 'Needs review',
  unavailable: 'Unavailable',
  not_run: 'Not run',
}

export const STAGE_TONE: Record<StageStatus, Tone> = {
  pass: 'pass',
  warning: 'warning',
  failed: 'failed',
  manual_review: 'manual',
  unavailable: 'neutral',
  not_run: 'pending',
}

export const LAYER_LABEL: Record<string, string> = {
  intake: 'Intake & clarity',
  classification: 'OCR & classification',
  layer1: 'Layer 1 · rules',
  layer2: 'Layer 2 · verification',
  cross_document: 'Layer 2 · cross-document',
  layer3: 'Layer 3 · evidence & review',
}

export const STATUS_LABEL: Record<string, string> = {
  open: 'Open',
  resolved: 'Resolved',
  waived: 'Waived',
  accepted: 'Accepted',
  superseded: 'Superseded',
  passed: 'Passed',
}

export const MODE_LABEL: Record<string, string> = {
  real: 'live source',
  simulated: 'simulated',
  unavailable: 'source unavailable',
  local: 'local check',
}

export const RESOLUTIONS = ['resolved', 'waived', 'accepted'] as const
export type Resolution = (typeof RESOLUTIONS)[number]

export function errorText(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback
}
