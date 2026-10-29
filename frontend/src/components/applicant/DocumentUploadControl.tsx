import { useId, useState } from 'react'
import { RefreshCw, Upload } from 'lucide-react'
import { DocumentCheckPanel } from '@/components/applicant/DocumentCheckPanel'
import { FALLBACK_POLICY, type FilePolicy } from '@/lib/fileValidation'
import { blocksUpload, inspectUpload, type CheckLine } from '@/lib/intakeChecks'
import { api, ApiError, type UploadDocumentResult } from '@/services/api'
import { useRole } from '@/app/RoleContext'

interface Props {
  applicationId: string
  requirementCode: string
  requirementName: string
  hasDocument: boolean
  policy?: FilePolicy
  disabled?: boolean
  /** Show the type-match/clarity result here (when the parent does not render it from data). */
  showCheck?: boolean
  /** Button only — no format line. Use on the application checklist. */
  compact?: boolean
  /** Called when the internal upload phase changes. */
  onPhaseChange?: (phase: Phase) => void
  /** Called after a successful upload so the parent can refresh in the background. */
  onUploaded: (result: UploadDocumentResult) => void | Promise<void>
  /** Local check lines, including when the file is rejected before upload. */
  onChecked?: (lines: CheckLine[]) => void
}

type Phase = 'idle' | 'validating' | 'uploading'

/**
 * Validate (type, size, contents, sharpness) → upload → show the type-match/clarity result.
 * Never navigates or unmounts the page, so scroll position is preserved.
 */
export function DocumentUploadControl({
  applicationId,
  requirementCode,
  requirementName,
  hasDocument,
  policy = FALLBACK_POLICY,
  disabled,
  showCheck = false,
  compact = false,
  onPhaseChange,
  onUploaded,
  onChecked,
}: Props) {
  const { role } = useRole()
  const inputId = useId()
  const [phase, setPhase] = useState<Phase>('idle')
  const [errors, setErrors] = useState<string[]>([])
  const [warnings, setWarnings] = useState<string[]>([])
  const [result, setResult] = useState<UploadDocumentResult | null>(null)

  function changePhase(p: Phase) {
    setPhase(p)
    onPhaseChange?.(p)
  }

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const input = e.target
    const file = input.files?.[0]
    if (!file) return
    setErrors([])
    setWarnings([])
    setResult(null)
    changePhase('validating')
    try {
      const lines = await inspectUpload(file, policy)
      onChecked?.(lines)
      const failed = lines.filter((l) => l.status === 'fail' && l.action).map((l) => l.action as string)
      if (blocksUpload(lines)) {
        setErrors(failed)
        return
      }
      setWarnings(failed)

      changePhase('uploading')
      const res = await api.uploadDocument(role, applicationId, file, requirementCode)
      setResult(res)
      await onUploaded(res)
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors([err.message])
      } else {
        setErrors(['Could not reach the server. Check your connection and try again.'])
      }
    } finally {
      changePhase('idle')
      input.value = '' // allow re-selecting the same file after fixing it
    }
  }

  const busy = phase !== 'idle'
  const accept = policy.allowedExtensions.map((x) => `.${x}`).join(',')

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <input
          id={inputId}
          type="file"
          accept={accept}
          className="sr-only"
          disabled={busy || disabled}
          onChange={(e) => void onPick(e)}
          aria-label={`${hasDocument ? 'Replace' : 'Upload'} ${requirementName}`}
        />
        <label htmlFor={inputId} className={busy || disabled ? 'pointer-events-none' : 'cursor-pointer'}>
          <span
            className={`inline-flex h-8 items-center gap-1.5 rounded-[var(--radius-md)] px-3 text-xs font-medium transition-colors ${
              busy || disabled
                ? 'bg-surface-muted text-ink-muted'
                : hasDocument
                  ? 'border border-border bg-white text-ink hover:bg-surface-muted'
                  : 'bg-brand text-white shadow-sm hover:bg-brand-hover'
            }`}
          >
            {hasDocument ? <RefreshCw size={14} /> : <Upload size={14} />}
            {phase === 'validating'
              ? 'Checking file…'
              : phase === 'uploading'
                ? 'Uploading…'
                : hasDocument
                  ? 'Replace file'
                  : 'Upload file'}
          </span>
        </label>
        {!compact && (
          <span className="text-[11px] text-ink-muted">
            {policy.allowedExtensions.map((x) => x.toUpperCase()).join(', ')} · max {policy.maxUploadMb} MB
          </span>
        )}
      </div>

      {errors.length > 0 && (
        <div
          role="alert"
          className="rounded-[var(--radius-md)] border border-[#e2cbc8] bg-status-failed-bg px-3 py-2 text-xs text-status-failed"
        >
          <p className="font-medium">This file was not uploaded:</p>
          <ul className="mt-1 list-disc pl-4">
            {errors.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </div>
      )}
      {warnings.length > 0 && errors.length === 0 && (
        <p className="text-[11px] text-status-warning">{warnings.join(' ')}</p>
      )}
      {result && (
        <p className="text-xs text-status-pass" role="status">
          {result.replacedPrevious
            ? `Replaced — now version ${result.documentVersion}. The earlier version is kept on record.`
              : 'Uploaded.'}
        </p>
      )}
      {showCheck && result?.documentCheck && <DocumentCheckPanel check={result.documentCheck} />}
    </div>
  )
}
