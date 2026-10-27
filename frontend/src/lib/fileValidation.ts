/**
 * Client-side file validation run before upload. The server enforces the same limits again;
 * this exists so applicants get an immediate, specific message instead of a failed upload.
 */

export interface FilePolicy {
  maxUploadBytes: number
  maxUploadMb: number
  allowedExtensions: string[]
}

/** Used only if /applications/upload-policy cannot be loaded. Mirrors backend defaults. */
export const FALLBACK_POLICY: FilePolicy = {
  maxUploadMb: 25,
  maxUploadBytes: 25 * 1024 * 1024,
  allowedExtensions: ['docx', 'jpeg', 'jpg', 'pdf', 'png', 'txt'],
}

export interface FileValidationResult {
  ok: boolean
  errors: string[]
  warnings: string[]
}

export type DetectedKind = 'pdf' | 'png' | 'jpeg' | 'docx' | 'zip' | 'text' | 'unknown'

const MIME_BY_EXT: Record<string, string[]> = {
  pdf: ['application/pdf'],
  png: ['image/png'],
  jpg: ['image/jpeg', 'image/jpg', 'image/pjpeg'],
  jpeg: ['image/jpeg', 'image/jpg', 'image/pjpeg'],
  docx: ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
  txt: ['text/plain'],
}

const KIND_BY_EXT: Record<string, DetectedKind> = {
  pdf: 'pdf',
  png: 'png',
  jpg: 'jpeg',
  jpeg: 'jpeg',
  docx: 'docx',
  txt: 'text',
}

const GENERIC_MIME = new Set(['', 'application/octet-stream', 'binary/octet-stream'])

export function extensionOf(name: string): string {
  const base = name.replace(/\\/g, '/').split('/').pop() ?? ''
  const dot = base.lastIndexOf('.')
  return dot > 0 ? base.slice(dot + 1).toLowerCase() : ''
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/** Metadata-only checks (sync): empty file, name, extension, size, declared MIME. */
export function validateFileMeta(
  file: { name: string; size: number; type?: string },
  policy: FilePolicy = FALLBACK_POLICY,
): FileValidationResult {
  const errors: string[] = []
  const warnings: string[] = []
  const ext = extensionOf(file.name)

  if (!file.name.trim()) errors.push('The file has no name.')
  if (file.size === 0) errors.push('The file is empty. Choose a file that has content.')
  if (file.size > policy.maxUploadBytes) {
    errors.push(
      `The file is ${formatBytes(file.size)}; the limit is ${policy.maxUploadMb} MB. ` +
        'Compress or rescan it at a lower resolution.',
    )
  }
  if (!ext) {
    errors.push(
      `The file has no extension. Allowed types: ${policy.allowedExtensions.join(', ')}.`,
    )
  } else if (!policy.allowedExtensions.includes(ext)) {
    errors.push(
      `“.${ext}” files are not accepted. Allowed types: ${policy.allowedExtensions.join(', ')}.`,
    )
  } else {
    const mime = (file.type || '').toLowerCase()
    const expected = MIME_BY_EXT[ext]
    if (expected && !GENERIC_MIME.has(mime) && !expected.includes(mime)) {
      errors.push(
        `The file is named “.${ext}” but your browser reports it as “${mime}”. ` +
          'Rename or re-export it in the correct format.',
      )
    }
  }
  return { ok: errors.length === 0, errors, warnings }
}

/** Detect the real content type from the first bytes (magic numbers). */
export function sniffKind(bytes: Uint8Array): DetectedKind {
  const startsWith = (sig: number[]) => sig.every((b, i) => bytes[i] === b)
  if (bytes.length >= 5 && startsWith([0x25, 0x50, 0x44, 0x46, 0x2d])) return 'pdf'
  if (bytes.length >= 8 && startsWith([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])) return 'png'
  if (bytes.length >= 3 && startsWith([0xff, 0xd8, 0xff])) return 'jpeg'
  if (bytes.length >= 4 && startsWith([0x50, 0x4b, 0x03, 0x04])) return 'zip' // docx is a zip
  if (bytes.length === 0) return 'unknown'
  // Plain text: no NUL bytes in the sample
  for (let i = 0; i < Math.min(bytes.length, 8192); i++) {
    if (bytes[i] === 0) return 'unknown'
  }
  return 'text'
}

/** Whether detected content is consistent with the claimed extension. */
export function contentMatchesExtension(ext: string, kind: DetectedKind): boolean {
  const expected = KIND_BY_EXT[ext]
  if (!expected) return true
  if (expected === 'docx') return kind === 'zip' || kind === 'docx'
  return kind === expected
}

/** Full validation: metadata plus a magic-byte check of the file's actual content. */
export async function validateFile(
  file: File,
  policy: FilePolicy = FALLBACK_POLICY,
): Promise<FileValidationResult> {
  const meta = validateFileMeta(file, policy)
  if (!meta.ok || file.size === 0) return meta
  const ext = extensionOf(file.name)
  try {
    const head = new Uint8Array(await file.slice(0, 8192).arrayBuffer())
    const kind = sniffKind(head)
    if (!contentMatchesExtension(ext, kind)) {
      meta.errors.push(
        `The contents do not look like a real .${ext} file. ` +
          'It may be renamed or corrupted — export it again from the original.',
      )
    }
  } catch {
    meta.warnings.push('Could not inspect the file contents in the browser; the server will check it.')
  }
  return { ...meta, ok: meta.errors.length === 0 }
}
