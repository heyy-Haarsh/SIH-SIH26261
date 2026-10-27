import { useCallback, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, FileText, History as HistoryIcon, ShieldAlert } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'
import { Textarea } from '@/components/ui/Input'
import { DocumentCheckPanel } from '@/components/applicant/DocumentCheckPanel'
import { DocumentUploadControl } from '@/components/applicant/DocumentUploadControl'
import { useRole } from '@/app/RoleContext'
import { useRefreshable } from '@/hooks/useRefreshable'
import { useUploadPolicy } from '@/hooks/useUploadPolicy'
import { api, ApiError } from '@/services/api'
import { applicationStatusTone, uploadStatusTone } from '@/lib/applicantStatus'
import { formatBytes } from '@/lib/fileValidation'
import { formatDate, formatDateTime } from '@/lib/format'
import type { ApplicantApplication, ApplicantDeficiency, ApplicantRequirement } from '@/types'

const MIN_RESPONSE = 5

export function ApplicantDetailPage() {
  const { id } = useParams()
  const { role } = useRole()
  const { policy, filePolicy } = useUploadPolicy()

  const load = useCallback(() => api.getMyApplication(id as string, role), [id, role])
  const { data, loading, refreshing, error, reload } = useRefreshable<ApplicantApplication>(
    id && role === 'applicant' ? load : null,
    `${id}:${role}`,
  )

  const breadcrumbs = ['Applicant', 'My Applications', data?.applicationNumber ?? '…']

  if (role !== 'applicant') {
    return (
      <AppShell title="Application" breadcrumbs={['Applicant', 'Application']}>
        <EmptyState
          icon={ShieldAlert}
          title="Applicant view only"
          description="This page is for the applicant who owns the application. Scrutiny officers open applications from their own queue."
          action={
            id ? (
              <Link to={`/officer/applications/${id}`}>
                <Button variant="outline" size="sm">
                  Open in scrutiny view
                </Button>
              </Link>
            ) : undefined
          }
        />
      </AppShell>
    )
  }

  if (loading && !data) {
    return (
      <AppShell title="Application" breadcrumbs={breadcrumbs}>
        <p className="text-sm text-ink-muted">Loading application…</p>
      </AppShell>
    )
  }

  if (!data) {
    return (
      <AppShell title="Application" breadcrumbs={breadcrumbs}>
        <EmptyState
          icon={AlertTriangle}
          title="Application not available"
          description={error ?? 'We could not find this application.'}
          action={
            <Link to="/applicant/applications">
              <Button variant="outline" size="sm">
                Back to my applications
              </Button>
            </Link>
          }
        />
      </AppShell>
    )
  }

  const openClarifications = data.deficiencies.filter((d) => d.status === 'open')

  return (
    <AppShell title={data.applicationNumber} breadcrumbs={breadcrumbs}>
      <div className="space-y-5">
        {error && (
          <div className="rounded-[var(--radius-md)] border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
            Could not refresh the latest status: {error}
          </div>
        )}

        <Card>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-ink">{data.institutionName}</h2>
              <p className="mt-0.5 text-xs text-ink-muted">
                {data.category} · {data.programName} · {data.academicYear}
                {data.submittedAt ? ` · Submitted ${formatDate(data.submittedAt)}` : ''}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {refreshing && <span className="text-[11px] text-ink-muted">Updating…</span>}
              <Badge tone={applicationStatusTone(data.status)}>{data.statusLabel}</Badge>
            </div>
          </div>
          <p className="mt-3 text-sm text-ink-secondary">{data.statusMessage}</p>
          <p className="mt-2 text-xs text-ink-muted">
            Required documents uploaded: {data.requiredUploaded} of {data.requiredTotal}
          </p>
        </Card>

        {data.deficiencies.length > 0 && (
          <ClarificationSection
            app={data}
            openCount={openClarifications.length}
            onChanged={reload}
          />
        )}

        <Card>
          <CardHeader
            title="Required documents"
            description="Upload each document. Replace a file at any time before a final decision; earlier versions are kept on record."
          />
          {policy && (
            <p className="mb-3 text-[11px] text-ink-muted">
              {policy.marathiSupported
                ? 'Marathi (मराठी) and Hindi text recognition is enabled for scanned documents.'
                : 'Marathi / Hindi text recognition is not installed on this server yet. For Marathi affidavits, upload a text-based PDF; scanned copies will be read by the officer.'}
            </p>
          )}
          <ul className="divide-y divide-border">
            {data.requirements.map((req) => (
              <RequirementRow
                key={req.code}
                req={req}
                applicationId={data.id}
                canUpload={data.canUpload}
                filePolicy={filePolicy}
                onChanged={reload}
              />
            ))}
          </ul>
          {!data.canUpload && (
            <p className="mt-3 text-xs text-ink-muted">
              This application has a final decision, so documents can no longer be changed.
            </p>
          )}
        </Card>

        <Card>
          <CardHeader title="History" description="What has happened on this application" />
          {data.history.length === 0 ? (
            <EmptyState
              icon={HistoryIcon}
              title="No activity yet"
              description="Actions on this application will appear here."
            />
          ) : (
            <ol className="space-y-3">
              {data.history.map((h) => (
                <li key={h.id} className="flex gap-3">
                  <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-brand" />
                  <div>
                    <div className="text-sm text-ink">{h.label}</div>
                    {h.detail && <div className="text-xs text-ink-secondary">{h.detail}</div>}
                    <div className="text-[11px] text-ink-muted">{formatDateTime(h.timestamp)}</div>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>
    </AppShell>
  )
}

function RequirementRow({
  req,
  applicationId,
  canUpload,
  filePolicy,
  onChanged,
}: {
  req: ApplicantRequirement
  applicationId: string
  canUpload: boolean
  filePolicy: Parameters<typeof DocumentUploadControl>[0]['policy']
  onChanged: () => Promise<void> | void
}) {
  const doc = req.document
  return (
    <li className="py-4 first:pt-0 last:pb-0" data-testid={`requirement-${req.code}`}>
      <div className="flex flex-wrap items-center gap-2">
        <FileText size={15} className="text-ink-muted" />
        <span className="text-sm font-medium text-ink">{req.name}</span>
        <Badge tone={req.mandatory ? 'neutral' : 'pending'}>{req.mandatory ? 'Required' : 'Optional'}</Badge>
        <Badge tone={uploadStatusTone(req.uploadStatus)}>{req.uploadStatusLabel}</Badge>
      </div>

      {doc && (
        <div className="mt-2 space-y-2 pl-6">
          <p className="text-xs text-ink-secondary">
            {doc.fileName} · {formatBytes(doc.sizeBytes)} · uploaded {formatDateTime(doc.uploadedAt)}
            {doc.version > 1 ? ` · version ${doc.version}` : ''}
          </p>
          {doc.documentCheck && <DocumentCheckPanel check={doc.documentCheck} />}
          {doc.previousVersions.length > 0 && (
            <details className="text-xs text-ink-muted">
              <summary className="cursor-pointer select-none">
                Earlier versions ({doc.previousVersions.length})
              </summary>
              <ul className="mt-1 space-y-0.5 pl-4">
                {doc.previousVersions.map((v) => (
                  <li key={v.version}>
                    Version {v.version}: {v.fileName} · {formatDateTime(v.uploadedAt)}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      {canUpload && (
        <div className="mt-3 pl-6">
          <DocumentUploadControl
            applicationId={applicationId}
            requirementCode={req.code}
            requirementName={req.name}
            hasDocument={Boolean(doc)}
            policy={filePolicy}
            onUploaded={onChanged}
          />
        </div>
      )}
    </li>
  )
}

function ClarificationSection({
  app,
  openCount,
  onChanged,
}: {
  app: ApplicantApplication
  openCount: number
  onChanged: () => Promise<void> | void
}) {
  const { role } = useRole()
  const [responses, setResponses] = useState<Record<string, string>>({})
  const [busyId, setBusyId] = useState<string | null>(null)
  const [note, setNote] = useState('')
  const [resubmitting, setResubmitting] = useState(false)
  const [message, setMessage] = useState<{ tone: 'ok' | 'err'; text: string } | null>(null)

  async function respond(d: ApplicantDeficiency) {
    const text = (responses[d.id] ?? '').trim()
    if (text.length < MIN_RESPONSE) {
      setMessage({ tone: 'err', text: `Write at least ${MIN_RESPONSE} characters explaining what you corrected.` })
      return
    }
    setBusyId(d.id)
    setMessage(null)
    try {
      await api.respondDeficiency(role, d.id, text)
      setResponses((prev) => ({ ...prev, [d.id]: '' }))
      await onChanged()
      setMessage({ tone: 'ok', text: 'Response saved.' })
    } catch (err) {
      setMessage({ tone: 'err', text: err instanceof ApiError ? err.message : 'Could not save your response.' })
    } finally {
      setBusyId(null)
    }
  }

  async function resubmit() {
    setResubmitting(true)
    setMessage(null)
    try {
      await api.resubmitApplication(role, app.id, note.trim())
      setNote('')
      await onChanged()
      setMessage({ tone: 'ok', text: 'Application resubmitted. The officer will review your changes.' })
    } catch (err) {
      setMessage({ tone: 'err', text: err instanceof ApiError ? err.message : 'Resubmission failed.' })
    } finally {
      setResubmitting(false)
    }
  }

  const awaitingResubmit = app.status === 'clarification_required' || app.status === 'deficiency'

  return (
    <Card className={openCount > 0 || awaitingResubmit ? 'border-amber-300' : undefined}>
      <CardHeader
        title="Clarification requests"
        description={
          openCount > 0
            ? `${openCount} request(s) need your response`
            : 'All requests have been answered'
        }
      />
      <ul className="space-y-3">
        {app.deficiencies.map((d) => (
          <li key={d.id} className="rounded-[var(--radius-md)] border border-border p-3">
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium text-ink">{d.title}</span>
              <Badge tone={d.status === 'open' ? 'warning' : d.status === 'responded' ? 'info' : 'pass'}>
                {d.status === 'open' ? 'Needs your response' : d.status === 'responded' ? 'Responded' : 'Closed'}
              </Badge>
            </div>
            <p className="text-xs text-ink-secondary">{d.description}</p>
            {d.applicantResponse && (
              <p className="mt-2 text-xs text-ink-muted">Your response: {d.applicantResponse}</p>
            )}
            {d.status === 'open' && (
              <div className="mt-3 space-y-2">
                <Textarea
                  rows={2}
                  placeholder="Explain what you corrected (and replace the document below if needed)…"
                  value={responses[d.id] ?? ''}
                  onChange={(e) => setResponses((prev) => ({ ...prev, [d.id]: e.target.value }))}
                />
                <Button size="sm" disabled={busyId === d.id} onClick={() => void respond(d)}>
                  {busyId === d.id ? 'Saving…' : 'Save response'}
                </Button>
              </div>
            )}
          </li>
        ))}
      </ul>

      {awaitingResubmit && (
        <div className="mt-4 space-y-2 border-t border-border pt-4">
          <h3 className="text-sm font-medium text-ink">Resubmit for review</h3>
          {app.resubmitBlockers.length > 0 ? (
            <ul className="list-disc pl-5 text-xs text-amber-900">
              {app.resubmitBlockers.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          ) : (
            <p className="flex items-center gap-1.5 text-xs text-status-pass">
              <CheckCircle2 size={14} /> All requests are answered. Make sure any corrected documents are
              uploaded, then resubmit.
            </p>
          )}
          <Textarea
            rows={2}
            maxLength={2000}
            placeholder="Optional note to the officer"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <Button disabled={!app.canResubmit || resubmitting} onClick={() => void resubmit()}>
            {resubmitting ? 'Resubmitting…' : 'Resubmit application'}
          </Button>
        </div>
      )}

      {message && (
        <p
          role="status"
          className={`mt-3 text-xs ${message.tone === 'ok' ? 'text-status-pass' : 'text-status-failed'}`}
        >
          {message.text}
        </p>
      )}
    </Card>
  )
}
