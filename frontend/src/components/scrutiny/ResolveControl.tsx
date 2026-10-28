import { useEffect, useRef, useState } from 'react'
import { Mic, MicOff, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Textarea } from '@/components/ui/Input'
import { draftOfficerReason, type ResolutionDraftContext } from '@/lib/resolutionDraft'
import { startLiveDictation } from '@/lib/speechToText'
import { RESOLUTIONS, errorText, type Resolution } from './scrutinyUi'

interface Props {
  /** Apply the officer's resolution. Should throw on failure. */
  onResolve: (status: Resolution, reason: string) => Promise<void>
  role: string
  label?: string
  placeholder?: string
  draftContext?: ResolutionDraftContext
}

/** Reason + Resolved / Waived / Accepted. The original finding is preserved server-side. */
export function ResolveControl({
  onResolve,
  role,
  label = 'Officer note',
  placeholder = 'Explain why this is resolved, waived or accepted…',
  draftContext,
}: Props) {
  const [reason, setReason] = useState('')
  const [livePartial, setLivePartial] = useState('')
  const [busy, setBusy] = useState(false)
  const [listening, setListening] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hint, setHint] = useState<string | null>(null)
  const committed = useRef('')
  const session = useRef<{ stop: () => Promise<void> } | null>(null)

  useEffect(() => {
    return () => {
      void session.current?.stop()
    }
  }, [])

  function fillDraft(action: Resolution) {
    if (!draftContext) return
    setReason(draftOfficerReason(draftContext, action))
    committed.current = ''
    setLivePartial('')
    setHint('Draft assist filled the note. Edit it before you mark the issue.')
    setError(null)
  }

  async function toggleMic() {
    if (listening && session.current) {
      setBusy(true)
      try {
        await session.current.stop()
      } finally {
        session.current = null
        setListening(false)
        setLivePartial('')
        setBusy(false)
        setHint('Stopped. Edit the note, then mark the issue.')
      }
      return
    }

    try {
      committed.current = reason.trim()
      setLivePartial('')
      setError(null)
      session.current = await startLiveDictation(role, {
        onPartial: (text) => {
          setLivePartial(text)
          const base = committed.current
          setReason([base, text].filter(Boolean).join(' '))
        },
        onFinal: (text) => {
          const spoken = text.trim()
          if (!spoken) return
          committed.current = [committed.current, spoken].filter(Boolean).join(' ')
          setLivePartial('')
          setReason(committed.current)
        },
        onError: (message) => {
          setError(message)
          setHint(null)
        },
        onStatus: (message) => setHint(message),
      })
      setListening(true)
    } catch (err) {
      setError(errorText(err, 'Microphone / speech session could not start.'))
      session.current = null
      setListening(false)
      setLivePartial('')
    }
  }

  async function apply(status: Resolution) {
    if (reason.trim().length < 5) {
      setError('Enter a reason of at least 5 characters.')
      return
    }
    if (session.current) {
      await session.current.stop()
      session.current = null
      setListening(false)
      setLivePartial('')
    }
    setBusy(true)
    setError(null)
    try {
      await onResolve(status, reason.trim())
      setReason('')
      committed.current = ''
      setHint(null)
    } catch (err) {
      setError(errorText(err, 'Could not record the resolution'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-2 space-y-2 border-t border-border pt-2">
      <div className="flex flex-wrap items-center justify-between gap-1.5">
        <label className="text-xs font-semibold text-ink">{label}</label>
        <div className="flex flex-wrap items-center gap-1.5">
          {draftContext && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              leftIcon={<Sparkles size={13} />}
              disabled={busy || listening}
              onClick={() => fillDraft('resolved')}
            >
              Draft note
            </Button>
          )}
          <Button
            type="button"
            size="sm"
            variant={listening ? 'secondary' : 'outline'}
            leftIcon={listening ? <MicOff size={13} /> : <Mic size={13} />}
            disabled={busy && !listening}
            aria-pressed={listening}
            onClick={() => void toggleMic()}
          >
            {listening ? 'Stop' : 'Speak'}
          </Button>
        </div>
      </div>
      <Textarea
        rows={2}
        className="w-full text-sm"
        value={reason}
        placeholder={placeholder}
        aria-label={label}
        onChange={(e) => {
          setReason(e.target.value)
          if (!listening) committed.current = e.target.value.trim()
        }}
      />
      {listening && livePartial && (
        <p className="mt-1 text-[11px] text-brand">Live: {livePartial}</p>
      )}
      {hint && <p className="mt-1 text-[11px] text-ink-muted">{hint}</p>}
      {error && <p className="mt-1 text-[11px] text-status-failed">{error}</p>}
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {RESOLUTIONS.map((st) => (
          <Button
            key={st}
            size="sm"
            variant={st === 'resolved' ? 'primary' : 'outline'}
            disabled={busy || listening}
            onClick={() => void apply(st)}
          >
            Mark {st}
          </Button>
        ))}
      </div>
      <p className="text-[10px] leading-tight text-ink-muted">
        Dictation streams to Sarvam (Indic → English). Edit before marking. Not an official determination.
      </p>
    </div>
  )
}
