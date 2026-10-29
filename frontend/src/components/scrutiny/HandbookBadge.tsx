import { BookOpen } from 'lucide-react'
import type { HandbookReference } from '@/types'

/**
 * Shows a verified AICTE Handbook citation (edition · section · page), or says plainly that no
 * verified reference is on record. It never renders a guessed or placeholder clause.
 */
export function HandbookBadge({ reference }: { reference?: HandbookReference | null }) {
  if (
    !reference ||
    reference.status !== 'verified' ||
    (!reference.edition && !reference.section && !reference.page) ||
    reference.note?.toUpperCase().includes('TODO')
  ) {
    return null
  }
  return (
    <span
      className="inline-flex items-center gap-1 rounded-md border border-[#cfdad2] bg-status-pass-bg px-2 py-0.5 text-[11px] font-medium text-status-pass"
      title={reference.title ?? undefined}
    >
      <BookOpen size={12} />
      {reference.edition} · §{reference.section} · p. {reference.page}
    </span>
  )
}
