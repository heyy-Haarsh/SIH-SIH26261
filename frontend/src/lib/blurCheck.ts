/**
 * Client-side sharpness check for JPEG/PNG rasters and PDF pages.
 * Uses Laplacian variance on a downscaled grayscale canvas — higher = sharper.
 */

import * as pdfjs from 'pdfjs-dist'
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorker

/** Tuned for ~800px-wide document scans; below this → treat as blurry. */
export const BLUR_VARIANCE_THRESHOLD = 90
/** Skip blur verdict when the page has almost no ink (blank / nearly blank). */
const MIN_CONTENT_STD = 8
const ANALYZE_MAX_WIDTH = 800
const PDF_PAGES_TO_CHECK = 3
const PDF_RENDER_SCALE = 1.25

export type BlurCheckResult = {
  /** Whether this file type supports blur analysis (jpeg/png/pdf). */
  applicable: boolean
  blurry: boolean
  score: number | null
  threshold: number
  pagesChecked: number
  /** Pages with almost no ink. */
  blankPages: number
  /** PDF /Rotate or JPEG EXIF orientation, in degrees. Null when this file type has none. */
  rotation: number | null
  /** PDF asked for a password. */
  locked: boolean
  /** The file could not be opened. */
  corrupt: boolean
  message: string
}

type PageScore = {
  variance: number
  contentStd: number
  blank: boolean
  rotation: number
}

function emptyScan(over: Partial<BlurCheckResult> & Pick<BlurCheckResult, 'applicable' | 'message'>): BlurCheckResult {
  return {
    blurry: false,
    score: null,
    threshold: BLUR_VARIANCE_THRESHOLD,
    pagesChecked: 0,
    blankPages: 0,
    rotation: null,
    locked: false,
    corrupt: false,
    ...over,
  }
}

function extOf(file: File): string {
  const name = file.name.toLowerCase()
  const dot = name.lastIndexOf('.')
  return dot >= 0 ? name.slice(dot + 1) : ''
}

export function isBlurCheckable(file: File): boolean {
  const ext = extOf(file)
  const mime = (file.type || '').toLowerCase()
  if (ext === 'pdf' || mime === 'application/pdf') return true
  if (['jpg', 'jpeg', 'png'].includes(ext)) return true
  if (mime === 'image/jpeg' || mime === 'image/png' || mime === 'image/jpg') return true
  return false
}

function isPdf(file: File): boolean {
  return extOf(file) === 'pdf' || (file.type || '').toLowerCase() === 'application/pdf'
}

/** Laplacian variance over grayscale pixels (3×3 kernel, borders skipped). */
export function laplacianVariance(imageData: ImageData): PageScore {
  const { data, width, height } = imageData
  const gray = new Float32Array(width * height)
  let sum = 0
  for (let i = 0, p = 0; i < data.length; i += 4, p++) {
    const g = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2]
    gray[p] = g
    sum += g
  }
  const mean = sum / gray.length
  let contentVar = 0
  for (let i = 0; i < gray.length; i++) {
    const d = gray[i] - mean
    contentVar += d * d
  }
  const contentStd = Math.sqrt(contentVar / gray.length)

  if (contentStd < MIN_CONTENT_STD) {
    return { variance: 0, contentStd, blank: true, rotation: 0 }
  }

  let lapSum = 0
  let lapSq = 0
  let n = 0
  for (let y = 1; y < height - 1; y++) {
    for (let x = 1; x < width - 1; x++) {
      const i = y * width + x
      const lap =
        -gray[i - width] - gray[i - 1] + 4 * gray[i] - gray[i + 1] - gray[i + width]
      lapSum += lap
      lapSq += lap * lap
      n++
    }
  }
  if (n === 0) return { variance: 0, contentStd, blank: true, rotation: 0 }
  const lapMean = lapSum / n
  const variance = lapSq / n - lapMean * lapMean
  return { variance, contentStd, blank: false, rotation: 0 }
}

function drawToAnalyzeCanvas(
  source: CanvasImageSource,
  srcW: number,
  srcH: number,
): ImageData {
  const scale = Math.min(1, ANALYZE_MAX_WIDTH / Math.max(srcW, 1))
  const w = Math.max(1, Math.round(srcW * scale))
  const h = Math.max(1, Math.round(srcH * scale))
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  if (!ctx) throw new Error('Canvas 2D context unavailable')
  ctx.drawImage(source, 0, 0, w, h)
  return ctx.getImageData(0, 0, w, h)
}

async function scoreRasterFile(file: File): Promise<PageScore> {
  const bitmap = await createImageBitmap(file)
  try {
    const imageData = drawToAnalyzeCanvas(bitmap, bitmap.width, bitmap.height)
    return laplacianVariance(imageData)
  } finally {
    bitmap.close()
  }
}

async function scorePdfFile(file: File): Promise<PageScore[]> {
  const data = new Uint8Array(await file.arrayBuffer())
  const loadingTask = pdfjs.getDocument({ data })
  const doc = await loadingTask.promise
  const pageCount = Math.min(doc.numPages, PDF_PAGES_TO_CHECK)
  const scores: PageScore[] = []

  try {
    for (let pageNum = 1; pageNum <= pageCount; pageNum++) {
      const page = await doc.getPage(pageNum)
      const viewport = page.getViewport({ scale: PDF_RENDER_SCALE })
      const canvas = document.createElement('canvas')
      canvas.width = Math.ceil(viewport.width)
      canvas.height = Math.ceil(viewport.height)
      const ctx = canvas.getContext('2d', { willReadFrequently: true })
      if (!ctx) throw new Error('Canvas 2D context unavailable')
      await page.render({ canvasContext: ctx, viewport, canvas }).promise
      const imageData = drawToAnalyzeCanvas(canvas, canvas.width, canvas.height)
      const rotation = ((page.rotate % 360) + 360) % 360
      scores.push({ ...laplacianVariance(imageData), rotation })
    }
  } finally {
    await loadingTask.destroy()
  }
  return scores
}

function verdictFromScores(scores: PageScore[], kind: 'image' | 'pdf'): BlurCheckResult {
  const threshold = BLUR_VARIANCE_THRESHOLD
  const blankPages = scores.filter((s) => s.blank).length
  const rotation = scores.find((s) => s.rotation && s.rotation !== 0)?.rotation ?? 0
  const usable = scores.filter((s) => !s.blank)
  if (usable.length === 0) {
    return emptyScan({
      applicable: true,
      pagesChecked: scores.length,
      blankPages,
      rotation,
      message:
        kind === 'pdf'
          ? 'PDF pages look mostly blank — sharpness not scored. Upload will proceed.'
          : 'Image looks mostly blank — sharpness not scored. Upload will proceed.',
    })
  }

  const minScore = Math.min(...usable.map((s) => s.variance))
  const blurry = minScore < threshold
  const pageNote =
    kind === 'pdf' && scores.length > 1
      ? ` (checked ${scores.length} page${scores.length === 1 ? '' : 's'})`
      : ''

  if (blurry) {
    return emptyScan({
      applicable: true,
      blurry: true,
      score: Math.round(minScore),
      pagesChecked: scores.length,
      blankPages,
      rotation,
      message: `This ${kind === 'pdf' ? 'PDF' : 'image'} looks too blurry for reliable extraction (sharpness ${Math.round(minScore)} < ${threshold})${pageNote}. Retake or rescan a clearer copy.`,
    })
  }

  return emptyScan({
    applicable: true,
    score: Math.round(minScore),
    pagesChecked: scores.length,
    blankPages,
    rotation,
    message: `Sharpness OK (${Math.round(minScore)} ≥ ${threshold})${pageNote}.`,
  })
}

/**
 * Analyze JPEG/PNG/PDF for blur before upload.
 * Non-applicable types (txt, docx, …) return applicable: false.
 */
export async function checkFileBlur(file: File): Promise<BlurCheckResult> {
  if (!isBlurCheckable(file)) {
    return emptyScan({ applicable: false, message: 'Blur check skipped for this file type.' })
  }

  try {
    if (isPdf(file)) {
      const scores = await scorePdfFile(file)
      return verdictFromScores(scores, 'pdf')
    }
    const score = await scoreRasterFile(file)
    const rotation = await readJpegOrientation(file)
    return verdictFromScores([{ ...score, rotation: rotation ?? 0 }], 'image')
  } catch (err) {
    const detail = err instanceof Error ? err.message : 'unknown error'
    const name = err && typeof err === 'object' && 'name' in err ? String((err as { name: string }).name) : ''
    const locked = /password/i.test(`${name} ${detail}`)
    return emptyScan({
      applicable: true,
      locked,
      corrupt: !locked,
      message: locked
        ? 'This file is password-protected.'
        : `Could not open this file (${detail}).`,
    })
  }
}

/** JPEG EXIF orientation as degrees (0, 90, 180, 270), or null if there is no tag. */
async function readJpegOrientation(file: File): Promise<number | null> {
  if (!['jpg', 'jpeg'].includes(extOf(file)) && !file.type.toLowerCase().includes('jpeg')) return null
  const bytes = new Uint8Array(await file.slice(0, 128 * 1024).arrayBuffer())
  for (let i = 0; i < bytes.length - 10; i++) {
    if (bytes[i] !== 0xff || bytes[i + 1] !== 0xe1) continue
    if (String.fromCharCode(...bytes.slice(i + 4, i + 10)) !== 'Exif\0\0') continue
    const view = new DataView(bytes.buffer, bytes.byteOffset + i + 10)
    const le = view.getUint16(0) === 0x4949
    const count = view.getUint16(8, le)
    for (let t = 0; t < count; t++) {
      const off = 10 + t * 12
      if (off + 12 > view.byteLength) break
      if (view.getUint16(off, le) === 0x0112) {
        const value = view.getUint16(off + 8, le)
        if (value === 3) return 180
        if (value === 6 || value === 7) return 90
        if (value === 8 || value === 5) return 270
        return 0
      }
    }
    return 0
  }
  return null
}
