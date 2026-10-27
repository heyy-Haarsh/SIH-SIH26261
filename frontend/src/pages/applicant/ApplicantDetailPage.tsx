import { useCallback, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, History as HistoryIcon, ShieldAlert } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'
import { Textarea } from '@/components/ui/Input'
import { DocumentUploadControl } from '@/components/applicant/DocumentUploadControl'
import { CorrectionTable, rowsFromOfficerText } from '@/components/shared/CorrectionTable'
import { useRole } from '@/app/RoleContext'
import { useRefreshable } from '@/hooks/useRefreshable'
import { useUploadPolicy } from '@/hooks/useUploadPolicy'
import { api, ApiError } from '@/services/api'
import {
  applicationStatusTone,
  CLARITY_SHORT,
  clarityTone,
  TYPE_MATCH_SHORT,
  typeMatchTone,
  uploadStatusTone,
} from '@/lib/applicantStatus'
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

        {(data.officerDecision ||
          (data.corrections && data.corrections.length > 0) ||
          data.deficiencies.length > 0) && (
          <Card padding={false}>
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-3">
              <div>
                <h2 className="text-sm font-semibold text-ink">From the scrutiny officer</h2>
                <p className="text-xs text-ink-muted">
                  {data.officerDecisionReason || data.statusMessage}
                </p>
              </div>
              {data.officerDecision && (
                <Badge tone={data.officerDecision === 'rejected' ? 'failed' : 'pass'}>
                  {data.officerDecision}
                </Badge>
              )}
            </div>
            <div className="p-5">
              <CorrectionTable
                rows={data.corrections ?? []}
                empty="No outstanding corrections from the officer."
              />
            </div>
          </Card>
        )}

        {data.deficiencies.length > 0 && (
          <ClarificationSection
            app={data}
            openCount={openClarifications.length}
            onChanged={reload}
          />
        )}

        <Card padding={false}>
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-5 py-4">
            <div>
              <h2 className="text-sm font-semibold text-ink">Required documents</h2>
              <p className="mt-0.5 text-xs text-ink-muted">
                {data.requiredUploaded} of {data.requiredTotal} uploaded. Replacing a file keeps the
                earlier version.
              </p>
            </div>
            <Badge tone={data.requiredUploaded >= data.requiredTotal ? 'pass' : 'pending'}>
              {data.requiredUploaded}/{data.requiredTotal}
            </Badge>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr className="border-b border-border bg-surface text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                  <th className="px-4 py-2">Document</th>
                  <th className="px-4 py-2">File</th>
                  <th className="px-4 py-2">Type</th>
                  <th className="px-4 py-2">Readability</th>
                  {data.canUpload && <th className="px-4 py-2" />}
                </tr>
              </thead>
              <tbody>
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
              </tbody>
            </table>
          </div>
          <p className="px-5 py-3 text-[11px] text-ink-muted">
            Type and readability are an automatic pre-check. The officer makes the final decision.
            {!data.canUpload && ' This application is closed, so files can no longer be changed.'}
            {policy && !policy.marathiSupported
              ? ' Marathi scans need a text PDF on this server.'
              : ''}
          </p>
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
  const check = doc?.documentCheck
  return (
    <tr className="border-b border-border last:border-0" data-testid={`requirement-${req.code}`}>
      <td className="px-4 py-3 align-top">
        <div className="font-medium text-ink">{req.name}</div>
        <div className="mt-1 flex flex-wrap gap-1">
          {!req.mandatory && <Badge tone="pending">Optional</Badge>}
          <Badge tone={uploadStatusTone(req.uploadStatus)}>{req.uploadStatusLabel}</Badge>
        </div>
      </td>
      <td className="px-4 py-3 align-top">
        {doc ? (
          <>
            <div className="truncate font-medium text-ink" title={doc.fileName}>
              {doc.fileName}
            </div>
            <div className="mt-0.5 text-[11px] text-ink-muted">
              {doc.version > 1 ? `v${doc.version} · ` : ''}
              {formatBytes(doc.sizeBytes)} · {formatDateTime(doc.uploadedAt)}
            </div>
            {doc.previousVersions.length > 0 && (
              <details className="mt-1 text-[11px] text-ink-muted">
                <summary className="cursor-pointer select-none">
                  Earlier versions ({doc.previousVersions.length})
                </summary>
                <ul className="mt-1 space-y-0.5">
                  {doc.previousVersions.map((v) => (
                    <li key={v.version}>
                      v{v.version}: {v.fileName}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </>
        ) : (
          <span className="text-ink-muted">No file yet</span>
        )}
      </td>
      <td className="px-4 py-3 align-top">
        {check ? (
          <Badge tone={typeMatchTone(check.typeMatch)}>{TYPE_MATCH_SHORT[check.typeMatch]}</Badge>
        ) : (
          <span className="text-ink-muted">—</span>
        )}
      </td>
      <td className="px-4 py-3 align-top">
        {check ? (
          <Badge tone={clarityTone(check.clarity)}>{CLARITY_SHORT[check.clarity]}</Badge>
        ) : (
          <span className="text-ink-muted">—</span>
        )}
      </td>
      {canUpload && (
        <td className="px-4 py-3 align-top text-right">
          <DocumentUploadControl
            applicationId={applicationId}
            requirementCode={req.code}
            requirementName={req.name}
            hasDocument={Boolean(doc)}
            policy={filePolicy}
            compact
            onUploaded={onChanged}
          />
        </td>
      )}
    </tr>
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
            <div className="mt-2">
              <CorrectionTable
                rows={
                  d.description.includes(': ')
                    ? rowsFromOfficerText(d.description)
                    : [{ documentName: d.title, action: d.description }]
                }
              />
            </div>
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
