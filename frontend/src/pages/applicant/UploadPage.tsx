import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Upload } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input, Label, Select } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import { checkFileBlur, type BlurCheckResult } from '@/lib/blurCheck'
import type { ApplicationSummary } from '@/types'

export function UploadPage() {
  const { role } = useRole()
  const [apps, setApps] = useState<ApplicationSummary[]>([])
  const [appsError, setAppsError] = useState<string | null>(null)
  const [applicationId, setApplicationId] = useState('')
  const [requirement, setRequirement] = useState('AFFIDAVIT')
  const [file, setFile] = useState<File | null>(null)
  const [blur, setBlur] = useState<BlurCheckResult | null>(null)
  const [blurChecking, setBlurChecking] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const [resultDocId, setResultDocId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (role !== 'applicant' && role !== 'admin') {
      setApps([])
      setAppsError('Switch the demo role to Applicant to upload documents.')
      return
    }
    setAppsError(null)
    api
      .listApplications(role)
      .then((list) => {
        setApps(list)
        if (list.length && !applicationId) {
          setApplicationId(list[0].id)
        }
      })
      .catch((err) => {
        setAppsError(
          err instanceof ApiError
            ? `Could not load applications (${err.status}): ${err.message}`
            : 'Backend unreachable — start the API on port 8000.',
        )
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only reload when role changes
  }, [role])

  async function onFileChange(selected: File | null) {
    setFile(selected)
    setBlur(null)
    setError(null)
    setResult(null)
    setResultDocId(null)
    if (!selected) return
    setBlurChecking(true)
    try {
      const outcome = await checkFileBlur(selected)
      setBlur(outcome)
    } finally {
      setBlurChecking(false)
    }
  }

  async function onUpload(e: React.FormEvent) {
    e.preventDefault()
    if (!file || !applicationId) return
    if (role !== 'applicant' && role !== 'admin') {
      setError('Switch demo role to Applicant before uploading.')
      return
    }
    if (blurChecking) {
      setError('Wait for the blur check to finish.')
      return
    }
    if (blur?.blurry) {
      setError(blur.message)
      return
    }
    setBusy(true)
    setError(null)
    setResult(null)
    setResultDocId(null)
    try {
      const res = await api.uploadDocument(role, applicationId, file, requirement)
      const findingsCount = Array.isArray(res.findings) ? res.findings.length : 0
      setResultDocId(res.documentId)
      setResult(
        [
          `Upload accepted.`,
          `Document: ${res.documentId}`,
          res.extractionRunId
            ? `Extraction: ${res.extractionStatus ?? 'done'} (${res.extractionRunId})`
            : 'Extraction: not run',
          res.validationRunId
            ? `Validation: ${res.validationRunId}`
            : 'Validation: not run',
          `Findings: ${findingsCount}`,
        ].join(' '),
      )
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Upload failed (${err.status}): ${err.message}`)
      } else {
        setError('Backend unreachable. Start the FastAPI server (port 8000).')
      }
    } finally {
      setBusy(false)
    }
  }

  const blockedByBlur = Boolean(blur?.blurry)

  return (
    <AppShell title="Document Uploads" breadcrumbs={['Applicant', 'Uploads']}>
      <DemoBanner>
        Use role <strong>Applicant</strong>. JPEG/PNG and PDF uploads are checked for blur in the
        browser before upload. Prefer a sharp scan or photo so extraction can read the text.
      </DemoBanner>

      <Card className="max-w-xl">
        <CardHeader
          title="Upload a document"
          description="blur check → upload → file checks → extraction → validation"
          action={<Badge tone="info">API-backed</Badge>}
        />
        {appsError && (
          <div className="mb-4 rounded-[var(--radius-md)] border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
            {appsError}{' '}
            <Link className="underline" to="/applicant/applications/new">
              Create application
            </Link>
          </div>
        )}
        <form className="space-y-4" onSubmit={onUpload}>
          <div>
            <Label htmlFor="appId">Application</Label>
            {apps.length > 0 ? (
              <Select
                id="appId"
                value={applicationId}
                onChange={(e) => setApplicationId(e.target.value)}
                required
              >
                {apps.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.applicationNumber} — {a.category} ({a.status})
                  </option>
                ))}
              </Select>
            ) : (
              <Input
                id="appId"
                placeholder="Paste application id if list failed to load"
                value={applicationId}
                onChange={(e) => setApplicationId(e.target.value)}
                required
              />
            )}
            {applicationId && (
              <p className="mt-1 text-[11px] text-ink-muted break-all">ID: {applicationId}</p>
            )}
          </div>
          <div>
            <Label htmlFor="req">Requirement code</Label>
            <Select id="req" value={requirement} onChange={(e) => setRequirement(e.target.value)}>
              <option value="AFFIDAVIT">AFFIDAVIT</option>
              <option value="LAND_OWNERSHIP">LAND_OWNERSHIP</option>
              <option value="AFFILIATION">AFFILIATION</option>
              <option value="BUILDING_PLAN">BUILDING_PLAN</option>
              <option value="FIRE_NOC">FIRE_NOC (Fire Safety)</option>
              <option value="AICTE_PAYMENT_RECEIPT">AICTE_PAYMENT_RECEIPT</option>
              <option value="OCCUPANCY_CERTIFICATE">OCCUPANCY_CERTIFICATE</option>
              <option value="STRUCTURAL_STABILITY">STRUCTURAL_STABILITY</option>
              <option value="SATELLITE_MAP">SATELLITE_MAP</option>
              <option value="AUDITED_ACCOUNTS">AUDITED_ACCOUNTS</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="file">File (pdf, jpg, jpeg, png, txt, docx — max 25MB)</Label>
            <Input
              id="file"
              type="file"
              accept=".pdf,.txt,.png,.jpg,.jpeg,.docx,application/pdf,image/jpeg,image/png,text/plain"
              onChange={(e) => void onFileChange(e.target.files?.[0] ?? null)}
              required
            />
            <p className="mt-1 text-[11px] text-ink-muted">
              JPEG/PNG and PDF are sharpness-checked client-side. Soft/blurry scans are blocked.
            </p>
          </div>
          {blurChecking && (
            <div className="rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2 text-xs text-ink-secondary">
              Checking image/PDF sharpness…
            </div>
          )}
          {!blurChecking && blur?.applicable && !blur.blurry && (
            <div className="rounded-[var(--radius-md)] border border-emerald-200 bg-status-pass-bg px-3 py-2 text-xs text-status-pass">
              {blur.message}
            </div>
          )}
          {!blurChecking && blur?.blurry && (
            <div className="rounded-[var(--radius-md)] border border-red-200 bg-status-failed-bg px-3 py-2 text-xs text-status-failed">
              {blur.message}
            </div>
          )}
          {error && (
            <div className="rounded-[var(--radius-md)] border border-red-200 bg-status-failed-bg px-3 py-2 text-xs text-status-failed">
              {error}
            </div>
          )}
          {result && (
            <div className="rounded-[var(--radius-md)] border border-emerald-200 bg-status-pass-bg px-3 py-2 text-xs text-status-pass">
              <p>{result}</p>
              {applicationId && (
                <Link
                  className="mt-2 inline-block underline"
                  to={`/applicant/applications/${applicationId}`}
                >
                  Open application details → Extracted fields
                </Link>
              )}
              {resultDocId && (
                <p className="mt-1 text-[10px] opacity-80">Document id: {resultDocId}</p>
              )}
            </div>
          )}
          <Button
            type="submit"
            disabled={busy || blurChecking || blockedByBlur || !file || !applicationId}
            leftIcon={<Upload size={16} />}
          >
            {busy ? 'Uploading…' : blurChecking ? 'Checking sharpness…' : 'Upload & run checks'}
          </Button>
        </form>
      </Card>
    </AppShell>
  )
}
