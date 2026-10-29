/**
 * PDF.js page viewer with optional PDF-space bounding-box highlight.
 * Coordinates use the same convention as extraction: page points, origin top-left.
 * Never invents boxes — highlight is omitted when bbox/page are missing.
 */
import { useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, ZoomIn, ZoomOut } from 'lucide-react'
import * as pdfjs from 'pdfjs-dist'
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { Button } from '@/components/ui/Button'

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorker

export type EvidenceBBox = { x0: number; y0: number; x1: number; y1: number }

export function PdfEvidenceViewer({
  url,
  fileName,
  highlightPage,
  highlightBBox,
  highlightLabel,
}: {
  url: string
  fileName: string
  /** 1-based page index when known. */
  highlightPage?: number | null
  highlightBBox?: EvidenceBBox | null
  highlightLabel?: string | null
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [pdf, setPdf] = useState<pdfjs.PDFDocumentProxy | null>(null)
  const [pageCount, setPageCount] = useState(0)
  const [page, setPage] = useState(1)
  const [scale, setScale] = useState(1.15)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    let docRef: pdfjs.PDFDocumentProxy | null = null
    setLoading(true)
    setError(null)
    const task = pdfjs.getDocument({ url })
    task.promise
      .then((doc) => {
        if (cancelled) {
          void doc.cleanup()
          return
        }
        docRef = doc
        setPdf(doc)
        setPageCount(doc.numPages)
        const target =
          highlightPage && highlightPage >= 1 && highlightPage <= doc.numPages ? highlightPage : 1
        setPage(target)
      })
      .catch((err: unknown) => {
        if (!cancelled)
          setError(err instanceof Error ? err.message : 'Could not open this PDF for evidence view.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
      void task.destroy()
      if (docRef) void docRef.cleanup()
    }
  }, [url, highlightPage])

  useEffect(() => {
    if (highlightPage && highlightPage >= 1 && highlightPage <= pageCount) {
      setPage(highlightPage)
    }
  }, [highlightPage, pageCount])

  useEffect(() => {
    if (!pdf || !canvasRef.current) return
    let cancelled = false
    const canvas = canvasRef.current
    pdf
      .getPage(page)
      .then(async (pdfPage) => {
        if (cancelled) return
        const viewport = pdfPage.getViewport({ scale })
        const ctx = canvas.getContext('2d')
        if (!ctx) return
        canvas.width = viewport.width
        canvas.height = viewport.height
        await pdfPage.render({ canvasContext: ctx, viewport, canvas }).promise
        if (cancelled) return
        const showBox =
          highlightBBox &&
          highlightPage != null &&
          highlightPage === page &&
          Number.isFinite(highlightBBox.x0)
        if (showBox && highlightBBox) {
          // PDF points origin top-left → canvas y matches when scale applied.
          const x = highlightBBox.x0 * scale
          const y = highlightBBox.y0 * scale
          const w = Math.max(2, (highlightBBox.x1 - highlightBBox.x0) * scale)
          const h = Math.max(2, (highlightBBox.y1 - highlightBBox.y0) * scale)
          ctx.save()
          ctx.strokeStyle = '#1b2a41'
          ctx.fillStyle = 'rgba(27, 42, 65, 0.16)'
          ctx.lineWidth = 2
          ctx.fillRect(x, y, w, h)
          ctx.strokeRect(x, y, w, h)
          ctx.restore()
        }
      })
      .catch(() => {
        if (!cancelled) setError('Could not render this PDF page.')
      })
    return () => {
      cancelled = true
    }
  }, [pdf, page, scale, highlightBBox, highlightPage])

  if (loading) {
    return <div className="p-6 text-center text-xs text-ink-muted">Loading PDF evidence view…</div>
  }
  if (error) {
    return (
      <div className="space-y-2">
        <p className="text-xs text-status-failed" role="alert">
          {error}
        </p>
        <iframe title={`Fallback preview of ${fileName}`} src={url} className="h-[420px] w-full rounded border border-border bg-white" />
      </div>
    )
  }

  const hasHighlight = Boolean(highlightBBox && highlightPage)
  const pageOnly = Boolean(highlightPage && !highlightBBox)

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          leftIcon={<ChevronLeft size={14} />}
          disabled={page <= 1}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
        >
          Prev
        </Button>
        <span className="text-xs text-ink-muted">
          Page {page} of {pageCount || '—'}
        </span>
        <Button
          size="sm"
          variant="outline"
          leftIcon={<ChevronRight size={14} />}
          disabled={page >= pageCount}
          onClick={() => setPage((p) => Math.min(pageCount, p + 1))}
        >
          Next
        </Button>
        <Button
          size="sm"
          variant="outline"
          leftIcon={<ZoomOut size={14} />}
          onClick={() => setScale((s) => Math.max(0.6, Number((s - 0.15).toFixed(2))))}
        >
          Zoom out
        </Button>
        <Button
          size="sm"
          variant="outline"
          leftIcon={<ZoomIn size={14} />}
          onClick={() => setScale((s) => Math.min(2.4, Number((s + 0.15).toFixed(2))))}
        >
          Zoom in
        </Button>
      </div>
      {(hasHighlight || pageOnly) && (
        <p className="text-[11px] text-ink-muted">
          {hasHighlight
            ? `Highlighting ${highlightLabel || 'selected evidence'} on page ${highlightPage}.`
            : `Navigated to page ${highlightPage}. Precise region highlighting is unavailable for this item.`}
        </p>
      )}
      <div className="max-h-[520px] overflow-auto rounded border border-border bg-surface-muted">
        <canvas ref={canvasRef} className="mx-auto block bg-white" />
      </div>
    </div>
  )
}
