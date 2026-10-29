import { checkFileBlur } from '@/lib/blurCheck'
import { validateFile, type FilePolicy } from '@/lib/fileValidation'
import type { DocumentCheck } from '@/types'

export type CheckKey = 'type' | 'blur' | 'blank' | 'integrity' | 'orientation' | 'content'

export type CheckLine = {
  key: CheckKey
  label: string
  status: 'pass' | 'fail' | 'pending'
  /** One action sentence when the file is not acceptable. */
  action: string | null
}

const LABELS: Record<CheckKey, string> = {
  type: 'Correct document type',
  blur: 'Blurred / unreadable pages',
  blank: 'Missing or blank pages',
  integrity: 'File integrity',
  orientation: 'Document orientation',
  content: 'Basic content presence',
}

function line(key: CheckKey, status: CheckLine['status'], action: string | null): CheckLine {
  return { key, label: LABELS[key], status, action }
}

const ACTIONS = {
  type: 'Replace this file with the document this slot asks for.',
  blur: 'Rescan a sharper, higher-resolution copy.',
  blank: 'Upload the complete document without blank pages.',
  integrity: 'Upload a file that opens, is not password-protected, and is a supported type.',
  orientation: 'Rotate the pages upright and upload again.',
  content: 'Upload a file that contains this document, not a blank page or an unrelated image.',
} as const

/** Local checks run as soon as a file is chosen. Type match waits for the server. */
export async function inspectUpload(file: File, policy: FilePolicy): Promise<CheckLine[]> {
  const integrity = await validateFile(file, policy)
  const scan = integrity.ok ? await checkFileBlur(file) : null

  const integrityFail =
    !integrity.ok || Boolean(scan?.locked) || Boolean(scan?.corrupt)
  const lines: CheckLine[] = [
    line(
      'integrity',
      integrityFail ? 'fail' : 'pass',
      integrityFail ? ACTIONS.integrity : null,
    ),
  ]

  if (!scan || !scan.applicable) {
    lines.push(
      line('blur', 'pass', null),
      line('blank', 'pass', null),
      line('orientation', 'pass', null),
      line('content', integrityFail ? 'fail' : 'pass', integrityFail ? ACTIONS.content : null),
      line('type', 'pending', null),
    )
    return lines
  }

  const allBlank = scan.pagesChecked > 0 && scan.blankPages >= scan.pagesChecked
  const someBlank = scan.blankPages > 0 && !allBlank
  const turned = scan.rotation === 90 || scan.rotation === 180 || scan.rotation === 270

  lines.push(
    line('blur', scan.blurry ? 'fail' : 'pass', scan.blurry ? ACTIONS.blur : null),
    line('blank', allBlank || someBlank ? 'fail' : 'pass', allBlank || someBlank ? ACTIONS.blank : null),
    line('orientation', turned ? 'fail' : 'pass', turned ? ACTIONS.orientation : null),
    line(
      'content',
      allBlank || integrityFail ? 'fail' : 'pass',
      allBlank || integrityFail ? ACTIONS.content : null,
    ),
    line('type', 'pending', null),
  )
  return lines
}

export function blocksUpload(lines: CheckLine[]): boolean {
  return lines.some((l) => l.key !== 'type' && l.status === 'fail')
}

/** Fold the server's type/readability result into the lines captured at upload. */
export function withServerCheck(lines: CheckLine[], check?: DocumentCheck | null): CheckLine[] {
  const base = lines.length ? lines : defaultLines()
  return base.map((row) => {
    if (!check) return row
    if (row.key === 'type') {
      if (check.typeMatch === 'mismatch') return line('type', 'fail', ACTIONS.type)
      if (check.typeMatch === 'matched') return line('type', 'pass', null)
      if (check.typeMatch === 'unclear') {
        return line('type', 'pending', 'Replace this file if it is not the document this slot asks for.')
      }
      return line('type', 'pending', null)
    }
    if (row.key === 'blur' && row.status !== 'fail') {
      if (check.clarity === 'unreadable' || check.clarity === 'unclear') {
        const ocrLimit = /text recognition is not available/i.test(check.clarityMessage)
        if (ocrLimit) return row
        return line('blur', 'fail', ACTIONS.blur)
      }
      if (check.clarity === 'clear') return line('blur', 'pass', null)
    }
    if (row.key === 'content' && row.status !== 'fail' && check.typeMatch === 'mismatch') {
      return line('content', 'fail', ACTIONS.content)
    }
    if (row.key === 'integrity' && row.status === 'pending') return line('integrity', 'pass', null)
    if ((row.key === 'blank' || row.key === 'orientation') && row.status === 'pending' && check.clarity === 'clear') {
      return line(row.key, 'pass', null)
    }
    return row
  })
}

function defaultLines(): CheckLine[] {
  return (Object.keys(LABELS) as CheckKey[]).map((key) => line(key, 'pending', null))
}

export function failingActions(lines: CheckLine[]): string[] {
  return lines.filter((l) => l.status === 'fail' && l.action).map((l) => l.action as string)
}
