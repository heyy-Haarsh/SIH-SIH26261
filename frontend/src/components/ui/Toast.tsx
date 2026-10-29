/**
 * Toast system — centralized mutation feedback.
 * Usage:
 *   const { toast } = useToast()
 *   toast({ message: 'Saved!', tone: 'success' })
 *
 * Place <ToastContainer /> once inside App or AppShell.
 */
import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from 'react'
import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from 'lucide-react'

type ToastTone = 'success' | 'error' | 'warning' | 'info'

interface ToastItem {
  id: string
  message: string
  tone: ToastTone
}

interface ToastCtx {
  toast: (opts: { message: string; tone?: ToastTone }) => void
}

const Ctx = createContext<ToastCtx | null>(null)

const TONE_STYLES: Record<
  ToastTone,
  { bg: string; border: string; text: string; Icon: typeof CheckCircle2 }
> = {
  success: {
    bg: '#F0FDF4',
    border: '#BBF7D0',
    text: '#166534',
    Icon: CheckCircle2,
  },
  error: {
    bg: '#FEF2F2',
    border: '#FECACA',
    text: '#991B1B',
    Icon: AlertCircle,
  },
  warning: {
    bg: '#FFFBEB',
    border: '#FDE68A',
    text: '#92400E',
    Icon: AlertTriangle,
  },
  info: {
    bg: '#EFF6FF',
    border: '#BFDBFE',
    text: '#1E40AF',
    Icon: Info,
  },
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const toast = useCallback(
    ({ message, tone = 'info' }: { message: string; tone?: ToastTone }) => {
      const id = `${Date.now()}-${Math.random()}`
      setToasts((prev) => [...prev, { id, message, tone }])
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id))
      }, 4000)
    },
    [],
  )

  function dismiss(id: string) {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }

  return (
    <Ctx.Provider value={{ toast }}>
      {children}
      {/* Toast container — bottom right */}
      <div
        className="fixed bottom-6 right-6 z-[9999] flex flex-col gap-2"
        style={{ minWidth: '320px', maxWidth: '420px' }}
        aria-live="polite"
        aria-atomic="false"
      >
        {toasts.map((t) => {
          const s = TONE_STYLES[t.tone]
          const { Icon } = s
          return (
            <div
              key={t.id}
              role="status"
              className="flex items-start gap-3 rounded-xl px-4 py-3.5 shadow-lg transition-all"
              style={{
                background: s.bg,
                border: `1px solid ${s.border}`,
                color: s.text,
                animation: 'slideInRight 0.2s ease-out',
              }}
            >
              <Icon size={16} strokeWidth={2} className="mt-0.5 shrink-0" />
              <span className="flex-1 text-sm font-medium">{t.message}</span>
              <button
                type="button"
                aria-label="Dismiss notification"
                onClick={() => dismiss(t.id)}
                className="shrink-0 opacity-60 hover:opacity-100 transition-opacity"
              >
                <X size={14} />
              </button>
            </div>
          )
        })}
      </div>
    </Ctx.Provider>
  )
}

export function useToast(): ToastCtx {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useToast must be used inside ToastProvider')
  return ctx
}
