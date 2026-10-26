import { useState } from 'react'
import { Upload } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input, Label, Select } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'

export function UploadPage() {
  const { role } = useRole()
  const [applicationId, setApplicationId] = useState('')
  const [requirement, setRequirement] = useState('AFFIDAVIT')
  const [file, setFile] = useState<File | null>(null)
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onUpload(e: React.FormEvent) {
    e.preventDefault()
    if (!file || !applicationId) return
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.uploadDocument(role, applicationId, file, requirement)
      setResult(
        `Upload accepted. Document ${res.document_id}. Validation run ${res.validation_run_id}. Findings: ${Array.isArray(res.findings) ? res.findings.length : 0}.`,
      )
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Upload failed (${err.status}): ${err.message}`)
      } else {
        setError('Backend unreachable. Start the API to exercise the live upload → validation flow.')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <AppShell title="Document Uploads" breadcrumbs={['Applicant', 'Uploads']}>
      <DemoBanner>
        Uploads are validated on the backend (type, size, checksum) and trigger a basic validation
        run. AI OCR/extraction is labeled unavailable until configured.
      </DemoBanner>

      <Card className="max-w-xl">
        <CardHeader
          title="Upload a document"
          description="First working flow: upload → file checks → validation run → findings"
          action={<Badge tone="info">API-backed</Badge>}
        />
        <form className="space-y-4" onSubmit={onUpload}>
          <div>
            <Label htmlFor="appId">Application ID (from API create)</Label>
            <Input
              id="appId"
              placeholder="e.g. uuid from create response"
              value={applicationId}
              onChange={(e) => setApplicationId(e.target.value)}
              required
            />
          </div>
          <div>
            <Label htmlFor="req">Requirement code</Label>
            <Select id="req" value={requirement} onChange={(e) => setRequirement(e.target.value)}>
              <option value="AFFIDAVIT">AFFIDAVIT</option>
              <option value="LAND_OWNERSHIP">LAND_OWNERSHIP</option>
              <option value="AFFILIATION">AFFILIATION</option>
              <option value="BUILDING_PLAN">BUILDING_PLAN</option>
              <option value="FIRE_NOC">FIRE_NOC</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="file">File (pdf, png, jpg, jpeg, docx — max 25MB)</Label>
            <Input
              id="file"
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.docx"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              required
            />
          </div>
          {error && (
            <div className="rounded-[var(--radius-md)] border border-red-200 bg-status-failed-bg px-3 py-2 text-xs text-status-failed">
              {error}
            </div>
          )}
          {result && (
            <div className="rounded-[var(--radius-md)] border border-emerald-200 bg-status-pass-bg px-3 py-2 text-xs text-status-pass">
              {result}
            </div>
          )}
          <Button type="submit" disabled={busy || !file} leftIcon={<Upload size={16} />}>
            {busy ? 'Uploading…' : 'Upload & run checks'}
          </Button>
        </form>
      </Card>
    </AppShell>
  )
}
