import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { Card, CardHeader } from '@/components/ui/Card'
import { Label, Select } from '@/components/ui/Input'
import { DocumentUploadControl } from '@/components/applicant/DocumentUploadControl'
import { useRole } from '@/app/RoleContext'
import { useRefreshable } from '@/hooks/useRefreshable'
import { useUploadPolicy } from '@/hooks/useUploadPolicy'
import { api, ApiError } from '@/services/api'
import type { ApplicantApplication, ApplicantApplicationSummary } from '@/types'

/** Quick upload: pick an application and a document, upload, see the pre-check result. */
export function UploadPage() {
  const { role } = useRole()
  const { filePolicy } = useUploadPolicy()
  const [apps, setApps] = useState<ApplicantApplicationSummary[]>([])
  const [appsError, setAppsError] = useState<string | null>(null)
  const [applicationId, setApplicationId] = useState('')
  const [requirement, setRequirement] = useState('')

  useEffect(() => {
    if (role !== 'applicant') {
      setApps([])
      setAppsError('Switch to the Applicant role to upload documents.')
      return
    }
    setAppsError(null)
    api
      .listMyApplications(role)
      .then((list) => {
        setApps(list)
        setApplicationId((current) => current || list[0]?.id || '')
      })
      .catch((err) =>
        setAppsError(
          err instanceof ApiError
            ? `Could not load your applications (${err.status}): ${err.message}`
            : 'Cannot reach the server. Please try again shortly.',
        ),
      )
  }, [role])

  const load = useCallback(() => api.getMyApplication(applicationId, role), [applicationId, role])
  const { data: app, reload } = useRefreshable<ApplicantApplication>(
    applicationId && role === 'applicant' ? load : null,
    `${applicationId}:${role}`,
  )

  useEffect(() => {
    if (app && !app.requirements.some((r) => r.code === requirement)) {
      setRequirement(app.requirements[0]?.code ?? '')
    }
  }, [app, requirement])

  const selected = app?.requirements.find((r) => r.code === requirement)

  return (
    <AppShell title="Upload Documents" breadcrumbs={['Applicant', 'Uploads']}>
      <Card className="max-w-xl">
        <CardHeader
          title="Upload a document"
          description="Your file is checked in the browser, uploaded, then checked for document type and clarity."
        />
        {appsError && (
          <div className="mb-4 rounded-[var(--radius-md)] border border-[#e3d8bd] bg-status-warning-bg px-3 py-2 text-xs text-status-warning">
            {appsError}{' '}
            <Link className="underline" to="/applicant/applications/new">
              Create an application
            </Link>
          </div>
        )}
        {apps.length === 0 && !appsError ? (
          <p className="text-sm text-ink-muted">
            You have no applications yet.{' '}
            <Link className="underline" to="/applicant/applications/new">
              Create one
            </Link>{' '}
            first.
          </p>
        ) : (
          <div className="space-y-4">
            <div>
              <Label htmlFor="appId">Application</Label>
              <Select id="appId" value={applicationId} onChange={(e) => setApplicationId(e.target.value)}>
                {apps.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.applicationNumber} — {a.institutionName} ({a.statusLabel})
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="req">Document</Label>
              <Select id="req" value={requirement} onChange={(e) => setRequirement(e.target.value)}>
                {(app?.requirements ?? []).map((r) => (
                  <option key={r.code} value={r.code}>
                    {r.name}
                    {r.uploadStatus !== 'not_uploaded' ? ` — ${r.uploadStatusLabel}` : ''}
                  </option>
                ))}
              </Select>
            </div>
            {app && selected && (
              <DocumentUploadControl
                key={`${app.id}:${selected.code}`}
                applicationId={app.id}
                requirementCode={selected.code}
                requirementName={selected.name}
                hasDocument={Boolean(selected.document)}
                policy={filePolicy}
                disabled={!app.canUpload}
                showCheck
                onUploaded={reload}
              />
            )}
            {app && !app.canUpload && (
              <p className="text-xs text-ink-muted">This application has a final decision; documents are locked.</p>
            )}
            {app && (
              <Link className="text-xs text-brand underline" to={`/applicant/applications/${app.id}`}>
                Open application →
              </Link>
            )}
          </div>
        )}
      </Card>
    </AppShell>
  )
}
