import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Textarea } from '@/components/ui/Input'
import { RESOLUTIONS, errorText, type Resolution } from './scrutinyUi'

interface Props {
  /** Apply the officer's resolution. Should throw on failure. */
  onResolve: (status: Resolution, reason: string) => Promise<void>
  label?: string
  placeholder?: string
}

/** Reason + Resolved / Waived / Accepted. The original finding is preserved server-side. */
export function ResolveControl({
  onResolve,
  label = 'Officer resolution (the original finding is preserved)',
  placeholder = 'Explain why this is resolved, waived or accepted…',
}: Props) {
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function apply(status: Resolution) {
    if (reason.trim().length < 5) {
      setError('Enter a reason of at least 5 characters.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await onResolve(status, reason.trim())
      setReason('')
    } catch (err) {
      setError(errorText(err, 'Could not record the resolution'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-3 space-y-2 border-t border-border pt-3">
      <label className="block text-[11px] font-medium text-ink-secondary">{label}</label>
      <Textarea
        rows={2}
        value={reason}
        placeholder={placeholder}
        onChange={(e) => setReason(e.target.value)}
      />
      {error && <p className="text-[11px] text-status-failed">{error}</p>}
      <div className="flex flex-wrap gap-2">
        {RESOLUTIONS.map((st) => (
          <Button
            key={st}
            size="sm"
            variant={st === 'resolved' ? 'primary' : 'outline'}
            disabled={busy}
            onClick={() => void apply(st)}
          >
            Mark {st}
          </Button>
        ))}
      </div>
    </div>
  )
}
