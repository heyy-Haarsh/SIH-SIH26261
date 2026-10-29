import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'

interface SlideOverProps {
  open: boolean
  onClose: () => void
  title: string
  /** Optional subtitle rendered below the title */
  subtitle?: string
  /** Width class — defaults to a sensible 520px-ish value */
  width?: string
  /** Body content */
  children: React.ReactNode
  /**
   * If true, clicking the backdrop or pressing Escape calls onClose.
   * Pass false when the form has unsaved state to prevent accidental loss.
   */
  allowEasyClose?: boolean
}

/**
 * Slide-over drawer that overlays the workspace from the right.
 * Only one drawer should be open at a time — the parent must enforce this.
 */
export function SlideOver({
  open,
  onClose,
  title,
  subtitle,
  width = 'max-w-[560px]',
  children,
  allowEasyClose = true,
}: SlideOverProps) {
  const panelRef = useRef<HTMLDivElement>(null)

  // Escape key
  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape' && allowEasyClose) onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose, allowEasyClose])

  // Focus trap — move focus into panel when it opens
  useEffect(() => {
    if (open) {
      requestAnimationFrame(() => panelRef.current?.focus())
    }
  }, [open])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      aria-modal="true"
      role="dialog"
      aria-label={title}
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0"
        style={{ background: 'rgba(0,0,0,0.25)' }}
        onClick={() => { if (allowEasyClose) onClose() }}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        ref={panelRef}
        tabIndex={-1}
        className={`relative flex flex-col h-full w-full ${width} outline-none`}
        style={{
          background: '#FFFFFF',
          borderLeft: '1px solid #E0E0E0',
          animation: 'slideOverIn 180ms cubic-bezier(0.4,0,0.2,1)',
        }}
      >
        {/* Header */}
        <div
          className="flex shrink-0 items-start justify-between gap-3 px-5 py-4"
          style={{ borderBottom: '1px solid #F0F0F0' }}
        >
          <div className="min-w-0">
            <h2 className="text-sm font-semibold" style={{ color: '#111111' }}>
              {title}
            </h2>
            {subtitle && (
              <p className="mt-0.5 text-[11px]" style={{ color: '#888888' }}>
                {subtitle}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 rounded-md p-1 transition-colors hover:bg-gray-100"
            aria-label="Close panel"
          >
            <X size={16} style={{ color: '#888888' }} />
          </button>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {children}
        </div>
      </div>

      {/* Slide-in animation */}
      <style>{`
        @keyframes slideOverIn {
          from { transform: translateX(100%); }
          to   { transform: translateX(0); }
        }
      `}</style>
    </div>
  )
}
