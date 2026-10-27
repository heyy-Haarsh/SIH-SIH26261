import { useEffect, useState } from 'react'
import { Download } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { api } from '@/services/api'

interface Props {
  role: string
  documentId: string
  mimeType: string
  fileName: string
  /** Changes when a new version is uploaded so the preview reloads. */
  version: number
}

type State =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'pdf' | 'image'; url: string }
  | { kind: 'text'; text: string; url: string }
  | { kind: 'other'; url: string }

/** In-page preview. The file endpoint needs auth headers, so the bytes are fetched as a Blob. */
export function DocumentPreview({ role, documentId, mimeType, fileName, version }: Props) {
  const [state, setState] = useState<State>({ kind: 'loading' })

  useEffect(() => {
    let cancelled = false
    let objectUrl: string | null = null
    setState({ kind: 'loading' })
    api
      .fetchDocumentFile(role, documentId)
      .then(async ({ blob }) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        if (mimeType === 'application/pdf') setState({ kind: 'pdf', url: objectUrl })
        else if (mimeType.startsWith('image/')) setState({ kind: 'image', url: objectUrl })
        else if (mimeType.startsWith('text/')) {
          const text = (await blob.text()).slice(0, 20000)
          if (!cancelled) setState({ kind: 'text', text, url: objectUrl })
        } else setState({ kind: 'other', url: objectUrl })
      })
      .catch((err: unknown) => {
        if (!cancelled)
          setState({
            kind: 'error',
            message: err instanceof Error ? err.message : 'Could not load the file',
          })
      })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [role, documentId, mimeType, version])

  if (state.kind === 'loading') {
    return <div className="p-6 text-center text-xs text-ink-muted">Loading preview…</div>
  }
  if (state.kind === 'error') {
    return (
      <div className="p-6 text-center text-xs text-status-failed" role="alert">
        {state.message}
      </div>
    )
  }
  return (
    <div className="space-y-2">
      {state.kind === 'pdf' && (
        <iframe
          title={`Preview of ${fileName}`}
          src={state.url}
          className="h-[480px] w-full rounded border border-border bg-white"
        />
      )}
      {state.kind === 'image' && (
        <img
          src={state.url}
          alt={`Preview of ${fileName}`}
          className="max-h-[480px] w-full rounded border border-border bg-white object-contain"
        />
      )}
      {state.kind === 'text' && (
        <pre className="max-h-[480px] overflow-auto whitespace-pre-wrap rounded border border-border bg-white p-3 text-[11px] text-ink">
          {state.text}
        </pre>
      )}
      {state.kind === 'other' && (
        <p className="rounded border border-dashed border-border p-4 text-center text-xs text-ink-muted">
          This file type cannot be previewed in the browser.
        </p>
      )}
      <a href={state.url} download={fileName}>
        <Button size="sm" variant="outline" leftIcon={<Download size={14} />}>
          Download {fileName}
        </Button>
      </a>
    </div>
  )
}
