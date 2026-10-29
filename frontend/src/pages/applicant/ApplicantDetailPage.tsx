import { useCallback, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, History as HistoryIcon, ShieldAlert } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'
import { SkeletonDetailLayout } from '@/components/ui/Skeleton'
import { Textarea } from '@/components/ui/Input'
import { DocumentUploadControl } from '@/components/applicant/DocumentUploadControl'
import {
  CorrectionTable,
  OfficerUpdateTable,
  rowsFromOfficerText,
} from '@/components/shared/CorrectionTable'
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
import type {
  ApplicantApplication,
  ApplicantDeficiency,
  ApplicantRequirement,
  Readiness,
} from '@/types'

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

  // Readiness is computed by the server (pre-submission checks), not derived in the browser.
  const loadReadiness = useCallback(() => api.getReadiness(role, id as string), [id, role])
  const { data: readiness, reload: reloadReadiness } = useRefreshable<Readiness>(
    id && role === 'applicant' ? loadReadiness : null,
    `readiness:${id}:${role}`,
  )
  const [submitting, setSubmitting] = useState(false)
  const [submitMsg, setSubmitMsg] = useState<{ tone: 'ok' | 'err'; text: string } | null>(null)
  const [declared, setDeclared] = useState(false)
  const refreshAll = useCallback(() => {
    void reload()
    void reloadReadiness()
  }, [reload, reloadReadiness])

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
        <SkeletonDetailLayout />
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
  const missingMandatory = data.requirements.filter(
    (r) => r.mandatory && r.uploadStatus === 'not_uploaded',
  )
  const needsAttention = data.requirements.filter((r) => r.uploadStatus === 'needs_attention')
  const isDraft = data.status === 'draft'

  async function submit() {
    if (!data) return
    setSubmitting(true)
    setSubmitMsg(null)
    try {
      const result = await api.submitApplication(role, data.id, true)
      setSubmitMsg({
        tone: 'ok',
        text: result.alreadySubmitted
          ? 'This application had already been submitted — nothing was sent twice.'
          : result.message,
      })
      refreshAll()
    } catch (err) {
      setSubmitMsg({
        tone: 'err',
        text:
          err instanceof ApiError
            ? err.message
            : 'Could not submit the application. Please try again.',
      })
      refreshAll()
    } finally {
      setSubmitting(false)
    }
  }

  const nextAction =
    openClarifications.length > 0
      ? 'Respond to clarification requests, then resubmit.'
      : isDraft
        ? readiness?.canSubmit
          ? 'All required documents are in. Review the readiness check, then submit.'
          : 'Upload all mandatory documents, then review readiness and submit.'
        : data.canResubmit
          ? 'You can resubmit after answering open clarifications.'
          : data.statusMessage

  return (
    <AppShell
      title={data.applicationNumber}
      description={nextAction}
      breadcrumbs={breadcrumbs}
    >
      <div className="space-y-5">
        {error && (
          <div className="rounded-[var(--radius-md)] border border-[#e3d8bd] bg-status-warning-bg px-3 py-2 text-xs text-status-warning">
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

        {isDraft && (
          <Card>
            <div className="space-y-3">
              <label className="flex items-start gap-2.5 text-sm text-ink-secondary">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={declared}
                  onChange={(e) => setDeclared(e.target.checked)}
                />
                <span>
                  I confirm that the information and documents in this application are accurate
                  and complete to the best of my knowledge.
                </span>
              </label>
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  disabled={!declared || submitting || !(readiness?.canSubmit ?? false)}
                  onClick={() => void submit()}
                >
                  {submitting ? 'Submitting…' : 'Submit for scrutiny'}
                </Button>
                {declared && readiness && !readiness.canSubmit && (
                  <span className="text-xs text-ink-muted">
                    Upload all required documents to enable submission.
                  </span>
                )}
              </div>
              {submitMsg && (
                <p
                  role="status"
                  className={`text-xs ${submitMsg.tone === 'ok' ? 'text-status-pass' : 'text-status-failed'}`}
                >
                  {submitMsg.text}
                </p>
              )}
            </div>
          </Card>
        )}

        {!isDraft && (
        <Card>
          <CardHeader
            title="Readiness review"
            description="Pre-submission and correction readiness. This is not an official compliance verdict."
          />
          <div className="grid gap-4 md:grid-cols-3">
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-status-failed">Must fix</h3>
              <ul className="mt-2 space-y-1 text-xs text-ink-secondary">
                {missingMandatory.map((r) => (
                  <li key={r.code}>Required document missing: {r.name}</li>
                ))}
                {openClarifications.map((d) => (
                  <li key={d.id}>Open clarification: {d.title}</li>
                ))}
                {data.resubmitBlockers.map((b) => (
                  <li key={b}>{b}</li>
                ))}
                {missingMandatory.length === 0 &&
                  openClarifications.length === 0 &&
                  data.resubmitBlockers.length === 0 && (
                    <li className="text-ink-muted">No mandatory blockers from the applicant side.</li>
                  )}
              </ul>
            </div>
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-status-warning">
                Review recommended
              </h3>
              <ul className="mt-2 space-y-1 text-xs text-ink-secondary">
                {needsAttention.map((r) => (
                  <li key={r.code}>
                    {r.name}: type or readability needs attention
                  </li>
                ))}
                {(data.corrections?.length ?? 0) > 0 && (
                  <li>{data.corrections!.length} correction item(s) from the officer</li>
                )}
                {needsAttention.length === 0 && (data.corrections?.length ?? 0) === 0 && (
                  <li className="text-ink-muted">No review-recommended items right now.</li>
                )}
              </ul>
            </div>
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
                Processing limitations
              </h3>
              <ul className="mt-2 space-y-1 text-xs text-ink-secondary">
                <li>
                  Type match and clarity are automatic pre-checks, not authenticity results.
                </li>
                <li>
                  External issuer confirmation is separate and may show unavailable or simulated
                  for the officer — that is not counted as your non-compliance here.
                </li>
                {policy && !policy.marathiSupported && (
                  <li>Marathi OCR language data is not installed on this server.</li>
                )}
              </ul>
            </div>
          </div>
        </Card>
        )}

        {(data.officerDecision ||
          (data.corrections && data.corrections.length > 0) ||
          (data.officerUpdates && data.officerUpdates.length > 0) ||
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
            <div className="space-y-4 p-5">
              {(data.corrections?.length ?? 0) > 0 && (
                <div>
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                    What you must correct
                  </h3>
                  <CorrectionTable rows={data.corrections ?? []} />
                </div>
              )}
              {(data.officerUpdates?.length ?? 0) > 0 && (
                <div>
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                    Officer decisions on issues
                  </h3>
                  <OfficerUpdateTable rows={data.officerUpdates ?? []} />
                </div>
              )}
              {(data.corrections?.length ?? 0) === 0 && (data.officerUpdates?.length ?? 0) === 0 && (
                <p className="text-xs text-ink-muted">No outstanding corrections from the officer.</p>
              )}
            </div>
          </Card>
        )}

        {data.deficiencies.length > 0 && (
          <ClarificationSection
            app={data}
            openCount={openClarifications.length}
            onChanged={refreshAll}
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
            <div className="flex flex-wrap items-center gap-2">
              {data.canUpload && (
                <AttachDemoDocsButton
                  applicationId={data.id}
                  onDone={reload}
                  label={
                    data.requiredUploaded >= data.requirements.length
                      ? 'Re-run document checks'
                      : 'Attach demo documents'
                  }
                />
              )}
              <Badge tone={data.requiredUploaded >= data.requiredTotal ? 'pass' : 'pending'}>
                {data.requiredUploaded}/{data.requiredTotal}
              </Badge>
            </div>
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
                    onChanged={refreshAll}
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


function AttachDemoDocsButton({
  applicationId,
  onDone,
  label = 'Attach demo documents',
}: {
  applicationId: string
  onDone: () => Promise<void> | void
  label?: string
}) {
  const { role } = useRole()
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  async function run() {
    setBusy(true)
    setMsg(null)
    try {
      const res = await api.attachDemoDocuments(applicationId, role, true)
      setMsg(res.message)
      await onDone()
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : 'Could not attach demo documents.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => void run()}>
        {busy ? 'Working…' : label}
      </Button>
      {msg && <span className="max-w-[220px] text-right text-[10px] text-ink-muted">{msg}</span>}
    </div>
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
    <Card className={openCount > 0 || awaitingResubmit ? 'border-[#e3d8bd]' : undefined}>
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
            {d.linkedItems && d.linkedItems.length > 0 && (
              <div className="mt-2">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                  Items this request covers
                </p>
                <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-ink-secondary">
                  {d.linkedItems.map((item) => (
                    <li key={`${item.documentName}:${item.summary}`}>
                      <span className="font-medium text-ink">{item.documentName}</span> — {item.summary}
                    </li>
                  ))}
                </ul>
              </div>
            )}
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
            <ul className="list-disc pl-5 text-xs text-status-warning">
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
