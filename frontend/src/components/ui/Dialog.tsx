import { useEffect, useRef, type ReactNode } from 'react'
import { X } from 'lucide-react'
import { clsx } from 'clsx'

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * Accessible modal dialog: labelled, closes on Escape or backdrop click, keeps keyboard focus
 * inside while open and returns it to the trigger on close.
 */
export function Dialog({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
  width = 'max-w-2xl',
  dismissible = true,
}: {
  open: boolean
  onClose: () => void
  title: string
  /** Where this applies (e.g. category and document), shown directly under the title. */
  subtitle?: ReactNode
  children: ReactNode
  footer?: ReactNode
  width?: string
  /** Set false while a save is running so the dialog cannot be dismissed mid-request. */
  dismissible?: boolean
}) {
  const panel = useRef<HTMLDivElement>(null)
  const previous = useRef<HTMLElement | null>(null)
  const titleId = useRef(`dlg-${Math.random().toString(36).slice(2, 9)}`).current

  useEffect(() => {
    if (!open) return
    previous.current = document.activeElement as HTMLElement | null
    const first = panel.current?.querySelector<HTMLElement>(FOCUSABLE)
    first?.focus()
    return () => previous.current?.focus?.()
  }, [open])

  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape' && dismissible) {
        e.stopPropagation()
        onClose()
      }
      if (e.key === 'Tab' && panel.current) {
        const nodes = Array.from(panel.current.querySelectorAll<HTMLElement>(FOCUSABLE))
        if (nodes.length === 0) return
        const first = nodes[0]
        const last = nodes[nodes.length - 1]
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose, dismissible])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 sm:p-8">
      <div
        className="fixed inset-0 bg-[#1c1b19]/40"
        aria-hidden
        onClick={() => dismissible && onClose()}
      />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={clsx(
          'relative z-10 w-full rounded-[var(--radius-lg)] border border-border bg-white shadow-[var(--shadow-card)]',
          width,
        )}
      >
        <header className="flex items-start justify-between gap-4 border-b border-border px-6 py-4">
          <div className="min-w-0">
            <h2 id={titleId} className="text-base font-semibold text-ink">
              {title}
            </h2>
            {subtitle && <div className="mt-1 text-xs text-ink-muted">{subtitle}</div>}
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={!dismissible}
            aria-label="Close dialog"
            className="rounded p-1 text-ink-muted hover:bg-surface-muted disabled:opacity-40"
          >
            <X size={16} strokeWidth={1.5} />
          </button>
        </header>
        <div className="px-6 py-5">{children}</div>
        {footer && (
          <footer className="flex flex-wrap items-center justify-end gap-2 border-t border-border px-6 py-3">
            {footer}
          </footer>
        )}
      </div>
    </div>
  )
}
