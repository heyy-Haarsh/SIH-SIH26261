import type { ConfigRule, ConfigState } from '@/types'

type Tone = 'neutral' | 'pass' | 'warning' | 'failed' | 'pending' | 'manual' | 'info' | 'brand'

export const CONFIG_STATE: Record<ConfigState, { label: string; tone: Tone; hint: string }> = {
  published: { label: 'Published', tone: 'pass', hint: 'The working copy matches the published configuration.' },
  unpublished_changes: {
    label: 'Unpublished changes',
    tone: 'warning',
    hint: 'Edits exist that applicants will not see until you publish.',
  },
  unpublished: { label: 'Not published', tone: 'neutral', hint: 'No configuration has been published yet.' },
}

export const RULE_STATUS: Record<ConfigRule['status'], { label: string; tone: Tone }> = {
  active: { label: 'Active', tone: 'pass' },
  draft: { label: 'Draft', tone: 'neutral' },
  inactive: { label: 'Inactive', tone: 'pending' },
  superseded: { label: 'Superseded', tone: 'pending' },
}

export const VERSION_STATUS: Record<string, { label: string; tone: Tone }> = {
  published: { label: 'Active', tone: 'pass' },
  draft: { label: 'Draft', tone: 'neutral' },
  retired: { label: 'Retired', tone: 'pending' },
}

export const RULE_TYPE_LABEL: Record<string, string> = {
  field_present: 'Field present',
  field_format: 'Field format',
  field_in: 'Allowed values',
  field_compare: 'Field comparison',
  date_not_expired: 'Not expired',
  date_not_future: 'Not in the future',
  date_age_max_days: 'Date age limit',
  date_order: 'Date order',
  field_equals_field: 'Cross-document match',
  file_extension_in: 'File type',
  file_size_max: 'File size',
  unstructured: 'No structured check yet',
}

export const SEVERITY_LABEL: Record<string, string> = {
  failed: 'Recorded as a failed check',
  warning: 'Recorded as a warning',
  manual_review: 'Flagged for manual review',
}

export const CHECK_STATE_LABEL: Record<string, string> = {
  passed: 'Passed',
  failed: 'Failed',
  manual_review: 'Manual review required',
  unable_to_evaluate: 'Unable to evaluate',
  pending: 'Pending processing',
  source_unavailable: 'External source unavailable',
}

export const FIELD_TYPE_LABEL: Record<string, string> = {
  text: 'Short text',
  textarea: 'Long text',
  number: 'Number',
  date: 'Date',
  select: 'Choice list',
  email: 'Email address',
  boolean: 'Yes / no confirmation',
}

export function ruleTypeLabel(t: string): string {
  return RULE_TYPE_LABEL[t] ?? t.replace(/_/g, ' ')
}
