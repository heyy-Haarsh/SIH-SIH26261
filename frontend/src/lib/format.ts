/**
 * format.ts — central date/number formatting for PRAMAN.
 * All pages must use these helpers; never inline Intl or toLocaleDateString.
 */

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return new Intl.DateTimeFormat('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    }).format(new Date(iso))
  } catch {
    return iso
  }
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return new Intl.DateTimeFormat('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(iso))
  } catch {
    return iso
  }
}

/**
 * Returns a human-readable relative time string.
 * e.g. "just now", "5m ago", "2h ago", "3d ago", "1mo ago", "2y ago"
 */
export function formatRelative(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    const diffMs = Date.now() - new Date(iso).getTime()
    const diffSec = Math.floor(diffMs / 1000)
    if (diffSec < 60) return 'just now'
    const diffMin = Math.floor(diffSec / 60)
    if (diffMin < 60) return `${diffMin}m ago`
    const diffHr = Math.floor(diffMin / 60)
    if (diffHr < 24) return `${diffHr}h ago`
    const diffDay = Math.floor(diffHr / 24)
    if (diffDay < 30) return `${diffDay}d ago`
    const diffMo = Math.floor(diffDay / 30)
    if (diffMo < 12) return `${diffMo}mo ago`
    return `${Math.floor(diffMo / 12)}y ago`
  } catch {
    return iso ?? '—'
  }
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function confidenceLabel(value: number | null): string {
  if (value === null) return 'N/A — not extracted by AI'
  return `${Math.round(value * 100)}%`
}
