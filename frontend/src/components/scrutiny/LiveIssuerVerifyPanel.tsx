import { useEffect, useMemo, useState } from 'react'
import { Loader2, Plug, ShieldCheck, ShieldX } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { api, ApiError } from '@/services/api'
import type {
  ApplicationDetail,
  IssuerRegistryRecord,
  IssuerVerifyResult,
} from '@/types'
import { errorText } from './scrutinyUi'

const ENDPOINT = 'POST /api/v1/issuer-registry/verify'

interface Props {
  detail: ApplicationDetail
  role: string
}

/**
 * Demo-facing live authenticity check: OCR/extracted fields → issuer registry hit.
 * Intentionally shows request + response JSON so a Network-tab demo is obvious.
 */
export function LiveIssuerVerifyPanel({ detail, role }: Props) {
  const verifiable = useMemo(
    () =>
      detail.documents.filter((d) => {
        const code = (d.requirementCode || '').toUpperCase()
        return (
          code.includes('FIRE') ||
          code.includes('AFFIDAVIT') ||
          code.includes('LAND') ||
          code.includes('AFFILIATION') ||
          code.includes('BUILDING') ||
          code.includes('OCCUPANCY')
        )
      }),
    [detail.documents],
  )

  const [docId, setDocId] = useState(verifiable[0]?.id ?? '')
  const [cert, setCert] = useState('FIRE-VERIFIED-001')
  const [holder, setHolder] = useState(detail.institutionName || 'Demo Institute of Technology')
  const [docType, setDocType] = useState('FIRE_NOC')
  const [records, setRecords] = useState<IssuerRegistryRecord[]>([])
  const [busy, setBusy] = useState(false)
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [requestPreview, setRequestPreview] = useState<object | null>(null)
  const [result, setResult] = useState<IssuerVerifyResult | null>(null)
  const [msg, setMsg] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const r = await api.listIssuerRegistryRecords(role)
        if (!cancelled) setRecords(r.records)
      } catch {
        /* panel still usable with manual entry */
      }
    })()
    return () => {
      cancelled = true
    }
  }, [role])

  useEffect(() => {
    if (!docId) return
    let cancelled = false
    setLoadingPreview(true)
    void (async () => {
      try {
        const p = await api.getIssuerVerifyPayload(role, docId)
        if (cancelled) return
        if (p.certificateNumber) setCert(p.certificateNumber)
        if (p.holderName) setHolder(p.holderName)
        if (p.docType) setDocType(p.docType)
        setRequestPreview({
          method: 'POST',
          endpoint: '/api/v1/issuer-registry/verify',
          body: {
            docType: p.docType,
            certificateNumber: p.certificateNumber,
            holderName: p.holderName,
            applicationId: p.applicationId,
            documentId: p.documentId,
          },
        })
        setMsg(
          p.certificateNumber
            ? 'Payload built from OCR / extracted fields on this document.'
            : 'No certificate number in extracted fields — pick a registry number or type one.',
        )
      } catch (err) {
        if (!cancelled) setMsg(errorText(err, 'Could not build verify payload'))
      } finally {
        if (!cancelled) setLoadingPreview(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [docId, role])

  async function runVerify(fromDocument: boolean) {
    setBusy(true)
    setMsg(null)
    setResult(null)
    try {
      let res: IssuerVerifyResult
      if (fromDocument && docId) {
        res = await api.verifyDocumentAgainstIssuerRegistry(role, docId)
      } else {
        const body = {
          docType,
          certificateNumber: cert.trim(),
          holderName: holder.trim(),
          applicationId: detail.id,
          documentId: docId || undefined,
        }
        setRequestPreview({
          method: 'POST',
          endpoint: '/api/v1/issuer-registry/verify',
          body,
        })
        res = await api.verifyIssuerRegistry(role, body)
      }
      setResult(res)
      setRequestPreview(res.request)
      setMsg(res.message)
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : errorText(err, 'Issuer registry verify failed'))
    } finally {
      setBusy(false)
    }
  }

  function fillFromRecord(r: IssuerRegistryRecord) {
    setCert(r.certificateNumber)
    setDocType(r.docType)
    setHolder(r.holderName)
    setRequestPreview({
      method: 'POST',
      endpoint: '/api/v1/issuer-registry/verify',
      body: {
        docType: r.docType,
        certificateNumber: r.certificateNumber,
        holderName: r.holderName,
        applicationId: detail.id,
        documentId: docId || undefined,
      },
    })
    setResult(null)
    setMsg(`Filled from registry: ${r.certificateNumber} (${r.status})`)
  }

  return (
    <section className="space-y-3 rounded-[var(--radius-md)] border border-emerald-200 bg-emerald-50/40 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-2xl">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
            <Plug size={16} className="text-emerald-700" />
            Live issuer registry verify
          </h3>
          <p className="mt-1 text-xs text-ink-muted">
            After OCR/extraction, we hit our own issuer registry (DigiLocker-shaped). Open DevTools →
            Network and click verify — you will see{' '}
            <code className="rounded bg-white px-1 text-[11px] text-emerald-900">{ENDPOINT}</code>.
          </p>
        </div>
        <Badge tone="pass">demo endpoint</Badge>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <label className="block text-xs">
          <span className="font-medium text-ink-secondary">Document (from this application)</span>
          <select
            className="mt-1 w-full rounded border border-border bg-white px-2 py-1.5 text-sm"
            value={docId}
            onChange={(e) => setDocId(e.target.value)}
          >
            <option value="">— manual certificate only —</option>
            {(verifiable.length ? verifiable : detail.documents).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.requirementCode})
              </option>
            ))}
          </select>
        </label>
        <label className="block text-xs">
          <span className="font-medium text-ink-secondary">Doc type</span>
          <input
            className="mt-1 w-full rounded border border-border bg-white px-2 py-1.5 text-sm"
            value={docType}
            onChange={(e) => setDocType(e.target.value)}
          />
        </label>
        <label className="block text-xs">
          <span className="font-medium text-ink-secondary">Certificate number (from OCR)</span>
          <input
            className="mt-1 w-full rounded border border-border bg-white px-2 py-1.5 font-mono text-sm"
            value={cert}
            onChange={(e) => setCert(e.target.value)}
          />
        </label>
        <label className="block text-xs">
          <span className="font-medium text-ink-secondary">Holder / institution</span>
          <input
            className="mt-1 w-full rounded border border-border bg-white px-2 py-1.5 text-sm"
            value={holder}
            onChange={(e) => setHolder(e.target.value)}
          />
        </label>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          disabled={busy || !cert.trim()}
          leftIcon={busy ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />}
          onClick={() => void runVerify(false)}
        >
          {busy ? 'Calling registry…' : 'POST /issuer-registry/verify'}
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={busy || !docId || loadingPreview}
          onClick={() => void runVerify(true)}
        >
          Verify selected document
        </Button>
      </div>

      {records.length > 0 && (
        <div>
          <h4 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
            Seeded registry (click to fill)
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {records.map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => fillFromRecord(r)}
                className="rounded border border-border bg-white px-2 py-1 text-left text-[11px] hover:border-emerald-400"
                title={r.notes}
              >
                <span className="font-mono text-ink">{r.certificateNumber}</span>
                <span className="ml-1 text-ink-muted">{r.docType}</span>
                {r.status === 'revoked' && (
                  <span className="ml-1 text-status-failed">revoked</span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="grid gap-3 lg:grid-cols-2">
        <div>
          <h4 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
            Request
          </h4>
          <pre className="max-h-48 overflow-auto rounded border border-border bg-slate-950 p-2 text-[11px] leading-relaxed text-emerald-200">
            {requestPreview
              ? JSON.stringify(requestPreview, null, 2)
              : loadingPreview
                ? 'Building from OCR…'
                : 'Select a document or click verify.'}
          </pre>
        </div>
        <div>
          <h4 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
            Response
          </h4>
          <pre className="max-h-48 overflow-auto rounded border border-border bg-slate-950 p-2 text-[11px] leading-relaxed text-sky-200">
            {result
              ? JSON.stringify(
                  {
                    result: result.result,
                    authentic: result.authentic,
                    message: result.message,
                    checks: result.checks,
                    matchedRecord: result.matchedRecord,
                    latencyMs: result.latencyMs,
                    endpoint: result.endpoint,
                  },
                  null,
                  2,
                )
              : '— waiting for POST —'}
          </pre>
        </div>
      </div>

      {result && (
        <div
          className={`flex flex-wrap items-center gap-2 rounded border px-3 py-2 text-xs ${
            result.authentic
              ? 'border-emerald-300 bg-emerald-50 text-emerald-900'
              : 'border-amber-300 bg-amber-50 text-amber-950'
          }`}
        >
          {result.authentic ? <ShieldCheck size={16} /> : <ShieldX size={16} />}
          <span className="font-semibold uppercase tracking-wide">{result.result}</span>
          <span>{result.message}</span>
          <span className="ml-auto text-ink-muted">{result.latencyMs} ms</span>
        </div>
      )}

      {msg && !result?.message && (
        <p className="text-xs text-ink-secondary" role="status">
          {msg}
        </p>
      )}
      {msg && result && (
        <p className="text-[11px] text-ink-muted">{result.disclaimer}</p>
      )}
    </section>
  )
}
