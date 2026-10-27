import { describe, expect, it } from 'vitest'
import {
  FALLBACK_POLICY,
  contentMatchesExtension,
  extensionOf,
  sniffKind,
  validateFile,
  validateFileMeta,
} from '@/lib/fileValidation'

const bytes = (...n: number[]) => new Uint8Array(n)
const PDF = bytes(0x25, 0x50, 0x44, 0x46, 0x2d, 0x31, 0x2e, 0x34)
const PNG = bytes(0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0)
const JPEG = bytes(0xff, 0xd8, 0xff, 0xe0)

describe('validateFileMeta', () => {
  it('accepts an allowed file with a matching mime type', () => {
    const r = validateFileMeta({ name: 'affidavit.pdf', size: 1000, type: 'application/pdf' })
    expect(r.ok).toBe(true)
  })

  it('rejects empty files', () => {
    const r = validateFileMeta({ name: 'a.pdf', size: 0, type: 'application/pdf' })
    expect(r.ok).toBe(false)
    expect(r.errors.join(' ')).toMatch(/empty/i)
  })

  it('rejects files over the server limit using the server-provided policy', () => {
    const policy = { ...FALLBACK_POLICY, maxUploadMb: 1, maxUploadBytes: 1024 * 1024 }
    const r = validateFileMeta({ name: 'big.pdf', size: 2 * 1024 * 1024, type: 'application/pdf' }, policy)
    expect(r.ok).toBe(false)
    expect(r.errors[0]).toMatch(/1 MB/)
  })

  it('rejects disallowed and missing extensions', () => {
    expect(validateFileMeta({ name: 'virus.exe', size: 10, type: '' }).ok).toBe(false)
    expect(validateFileMeta({ name: 'noextension', size: 10, type: '' }).ok).toBe(false)
    expect(validateFileMeta({ name: '.pdf', size: 10, type: '' }).ok).toBe(false)
  })

  it('rejects an extension that contradicts the declared mime type', () => {
    const r = validateFileMeta({ name: 'plan.pdf', size: 10, type: 'image/png' })
    expect(r.ok).toBe(false)
    expect(r.errors[0]).toMatch(/image\/png/)
  })

  it('tolerates a generic/empty mime type', () => {
    expect(validateFileMeta({ name: 'plan.pdf', size: 10, type: '' }).ok).toBe(true)
    expect(validateFileMeta({ name: 'plan.pdf', size: 10, type: 'application/octet-stream' }).ok).toBe(true)
  })

  it('is case-insensitive on extensions', () => {
    expect(extensionOf('SCAN.JPG')).toBe('jpg')
    expect(validateFileMeta({ name: 'SCAN.JPG', size: 10, type: 'image/jpeg' }).ok).toBe(true)
  })
})

describe('content sniffing', () => {
  it('detects real formats from magic bytes', () => {
    expect(sniffKind(PDF)).toBe('pdf')
    expect(sniffKind(PNG)).toBe('png')
    expect(sniffKind(JPEG)).toBe('jpeg')
    expect(sniffKind(bytes(0x50, 0x4b, 0x03, 0x04))).toBe('zip')
    expect(sniffKind(new TextEncoder().encode('प्रतिज्ञापत्र plain text'))).toBe('text')
    expect(sniffKind(bytes(1, 2, 0, 3))).toBe('unknown')
  })

  it('flags a renamed file whose content does not match its extension', () => {
    expect(contentMatchesExtension('pdf', 'png')).toBe(false)
    expect(contentMatchesExtension('pdf', 'pdf')).toBe(true)
    expect(contentMatchesExtension('docx', 'zip')).toBe(true)
    expect(contentMatchesExtension('jpg', 'jpeg')).toBe(true)
  })
})

describe('validateFile (async, with contents)', () => {
  it('passes a real pdf and rejects a png renamed to .pdf', async () => {
    const good = new File([PDF], 'ok.pdf', { type: 'application/pdf' })
    expect((await validateFile(good)).ok).toBe(true)

    const fake = new File([PNG], 'fake.pdf', { type: 'application/pdf' })
    const r = await validateFile(fake)
    expect(r.ok).toBe(false)
    expect(r.errors.join(' ')).toMatch(/do not look like a real \.pdf/i)
  })

  it('accepts a Marathi (UTF-8 Devanagari) text affidavit', async () => {
    const file = new File(['प्रतिज्ञापत्र\nमी शपथपूर्वक नमूद करतो'], 'shapathpatra.txt', { type: 'text/plain' })
    expect((await validateFile(file)).ok).toBe(true)
  })
})
