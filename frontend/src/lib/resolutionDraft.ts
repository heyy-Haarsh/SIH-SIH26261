import type { Resolution } from '@/components/scrutiny/scrutinyUi'

export interface ResolutionDraftContext {
  title: string
  explanation?: string | null
  applicantAction?: string | null
  documentName?: string | null
}

/** Local draft assist — not a remote model and not an official determination. */
export function draftOfficerReason(ctx: ResolutionDraftContext, action: Resolution): string {
  const doc = ctx.documentName ? ` for ${ctx.documentName}` : ''
  const why = (ctx.explanation || '').replace(/\s+/g, ' ').trim()
  const next = (ctx.applicantAction || '').replace(/\s+/g, ' ').trim()
  const seen = why ? ` Finding: ${why}` : ''
  const follow = next ? ` Applicant follow-up on file: ${next}` : ''

  if (action === 'waived') {
    return (
      `Waived after officer review${doc}. ${ctx.title} remains on the record but is not blocking this stage.` +
      seen
    ).slice(0, 800)
  }
  if (action === 'accepted') {
    return (
      `Accepted after officer review${doc}. ${ctx.title} is accepted as recorded; the original finding is kept.` +
      seen
    ).slice(0, 800)
  }
  return (
    `Reviewed the original${doc}. ${ctx.title} is no longer outstanding after officer check.` +
    seen +
    follow
  ).slice(0, 800)
}
