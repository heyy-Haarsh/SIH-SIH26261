import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Download, FileText, Info, Plug } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { Card, CardHeader } from '@/components/ui/Card'
import { Tabs } from '@/components/ui/Tabs'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { ApplicationStatusBadge, PriorityBadge } from '@/components/ui/StatusBadge'
import { AuthenticityPanel } from '@/components/scrutiny/AuthenticityPanel'
import { DecisionPanel } from '@/components/scrutiny/DecisionPanel'
import { DocumentCards } from '@/components/scrutiny/DocumentCards'
import { DocumentReportPanel } from '@/components/scrutiny/DocumentReportPanel'
import { IssuesPanel } from '@/components/scrutiny/IssuesPanel'
import { ReconciliationPanel } from '@/components/scrutiny/ReconciliationPanel'
import { errorText } from '@/components/scrutiny/scrutinyUi'
import { formatDate } from '@/lib/format'
import { useRole } from '@/app/RoleContext'
import { useApplicationDetail } from '@/hooks/useApplicationDetail'
import { useRefreshable } from '@/hooks/useRefreshable'
import { api } from '@/services/api'
import type { ScrutinyReview } from '@/types'

/** Scrutiny officer / administrator view of one application. Applicants have their own page. */
export function ApplicationDetailPage() {
  const { id } = useParams()
  const { role } = useRole()
  const staff = role === 'officer' || role === 'admin'
  const { detail, source, loading, error, reload } = useApplicationDetail(staff ? id : undefined)
  const review = useRefreshable<ScrutinyReview>(
    staff && id && source === 'api' ? () => api.getScrutinyReview(role, id) : null,
    `${id}:${source}:${role}`,
  )
  const [tab, setTab] = useState('issues')
  const [openDocId, setOpenDocId] = useState<string | null>(null)
  const [workflowMsg, setWorkflowMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const pickedInitialTab = useRef<string | null>(null)

  const reloadReview = review.reload
  const refreshAll = useCallback(async () => {
    await Promise.all([reload(), reloadReview()])
  }, [reload, reloadReview])

  // Land on the decision tab once when the application is waiting on a clarification.
  useEffect(() => {
    if (!detail || pickedInitialTab.current === detail.id) return
    pickedInitialTab.current = detail.id
    if (detail.status === 'clarification_required' || detail.status === 'resubmitted') setTab('review')
  }, [detail])

  const roleLabel = role === 'officer' ? 'Scrutiny Officer' : role === 'admin' ? 'Administrator' : 'Applicant'

  if (!staff) {
    return (
      <AppShell title="Scrutiny view" breadcrumbs={[roleLabel, 'Applications']}>
        <EmptyState
          icon={FileText}
          title="This page is for scrutiny officers"
          description="Applicants see their own application, required documents and deficiencies on their application page."
          action={
            <Link to={id ? `/applicant/applications/${id}` : '/applicant/applications'}>
              <Button variant="outline">Open my application</Button>
            </Link>
          }
        />
      </AppShell>
    )
  }

  if (loading) {
    return (
      <AppShell title="Loading…" breadcrumbs={[roleLabel, 'Applications']}>
        <p className="text-sm text-ink-muted">Loading application…</p>
      </AppShell>
    )
  }

  if (!detail) {
    return (
      <AppShell title="Application not found" breadcrumbs={[roleLabel, 'Applications']}>
        <EmptyState
          icon={FileText}
          title="Application not found"
          description={error ?? 'No matching application.'}
          action={
            <Link to="/officer/queue">
              <Button variant="outline">Back to queue</Button>
            </Link>
          }
        />
      </AppShell>
    )
  }

  const data = review.data
  const mismatchCount = detail.discrepancies.filter((d) => d.outcome !== 'MATCH').length
  const authenticityOpen = (detail.forensicsIndicators ?? []).filter(
    (i) =>
      i.riskClass === 'technical_anomaly' ||
      i.riskClass === 'authenticity_concern' ||
      i.riskClass === 'possible_duplicate',
  ).length

  async function startScrutiny() {
    setBusy(true)
    setWorkflowMsg(null)
    try {
      await api.startScrutiny(role, detail!.id)
      setWorkflowMsg('Scrutiny started.')
      await refreshAll()
    } catch (err) {
      setWorkflowMsg(errorText(err, 'Could not start scrutiny'))
    } finally {
      setBusy(false)
    }
  }

  async function checkIssuers() {
    setBusy(true)
    setWorkflowMsg(null)
    try {
      await api.runApplicationDocVerification(role, detail!.id)
      setWorkflowMsg(
        'Issuer check finished. Results are from the local demo issuer — not an official authority.',
      )
      await refreshAll()
    } catch (err) {
      setWorkflowMsg(errorText(err, 'Issuer check failed. Is the simulated issuer running on port 8001?'))
    } finally {
      setBusy(false)
    }
  }

  async function downloadPdf() {
    setBusy(true)
    setWorkflowMsg(null)
    try {
      const { blob, fileName } = await api.downloadScrutinyPdf(role, detail!.id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = fileName ?? `scrutiny-report-${detail!.applicationNumber}.pdf`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      setWorkflowMsg(errorText(err, 'Could not generate the PDF report'))
    } finally {
      setBusy(false)
    }
  }

  const canStart = ['submitted', 'processing', 'resubmitted'].includes(detail.status)

  return (
    <AppShell
      title={detail.applicationNumber}
      breadcrumbs={[roleLabel, 'Applications', detail.applicationNumber]}
      actions={
        <>
          {source === 'api' && (
            <>
              <Button
                variant="outline"
                size="sm"
                leftIcon={<Plug size={14} />}
                disabled={busy}
                onClick={() => void checkIssuers()}
              >
                Check with issuer
              </Button>
              <Button
                variant="outline"
                size="sm"
                leftIcon={<Download size={14} />}
                disabled={busy}
                onClick={() => void downloadPdf()}
              >
                Download PDF report
              </Button>
            </>
          )}
          {canStart && (
            <Button size="sm" disabled={busy} onClick={() => void startScrutiny()}>
              Start scrutiny
            </Button>
          )}
        </>
      }
    >
      {source !== 'api' && (
        <DemoBanner>
          Synthetic demo data. Open an application created through the API to use the full scrutiny
          review.
        </DemoBanner>
      )}
      {workflowMsg && (
        <div
          role="status"
          className="mb-4 rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2 text-xs text-ink-secondary"
        >
          {workflowMsg}
        </div>
      )}

      <div className="mb-5 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-lg font-semibold text-ink">{detail.institutionName}</h2>
                <ApplicationStatusBadge status={detail.status} />
                <PriorityBadge priority={detail.priority} />
              </div>
              <p className="mt-1 text-sm text-ink-secondary">
                {detail.category} · {detail.programName} · AY {detail.academicYear}
              </p>
            </div>
            {typeof detail.priorityScore === 'number' && (
              <div className="rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2 text-right">
                <div className="text-[10px] uppercase tracking-wide text-ink-muted">Priority aid</div>
                <div className="text-xl font-semibold text-ink">{detail.priorityScore}</div>
                <div className="max-w-[150px] text-[10px] text-ink-muted">
                  Ordering aid only — not proof of fraud or compliance
                </div>
              </div>
            )}
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-4">
            <Meta label="Application" value={detail.applicationNumber} />
            <Meta label="Submitted" value={formatDate(detail.submittedAt)} />
            <Meta label="Officer" value={detail.assignedOfficer ?? 'Unassigned'} />
            <Meta label="Contact" value={detail.contactEmail} />
          </div>
        </Card>

        <Card>
          <CardHeader title="Where this stands" description="Latest validation run" />
          <dl className="space-y-2 text-sm">
            <Row label="Status" value={detail.status.replace(/_/g, ' ')} />
            <Row label="Open issues" value={data ? String(data.openIssueCount) : '—'} />
            <Row label="Documents" value={`${detail.documents.length} uploaded`} />
            <Row
              label="Not uploaded"
              value={data ? String(data.missingDocuments.length) : '—'}
            />
            {detail.lastTransitionNote && <Row label="Last note" value={detail.lastTransitionNote} />}
          </dl>
          <p className="mt-3 flex items-start gap-1.5 text-[11px] text-ink-muted">
            <Info size={12} className="mt-0.5 shrink-0" />
            {data?.disclaimer ??
              'Automated results support the officer; they never decide an application.'}
          </p>
        </Card>
      </div>

      <Card padding={false}>
        <div className="px-4 pt-2">
          <Tabs
            active={tab}
            onChange={setTab}
            tabs={[
              { id: 'issues', label: 'Issues', count: data?.openIssueCount },
              { id: 'documents', label: 'Documents', count: detail.documents.length },
              { id: 'compare', label: 'Cross-document', count: mismatchCount || undefined },
              { id: 'authenticity', label: 'Authenticity', count: authenticityOpen || undefined },
              {
                id: 'review',
                label: 'Review & decision',
                count: (detail.deficiencies ?? []).filter((d) => d.status === 'open').length || undefined,
              },
            ]}
          />
        </div>

        <div className="p-4 md:p-5">
          {review.error && !data && source === 'api' && (
            <p className="mb-3 text-xs text-status-failed" role="alert">
              {review.error}
            </p>
          )}

          {tab === 'issues' &&
            (data ? (
              <div className="space-y-4">
                <IssuesPanel
                  review={data}
                  role={role}
                  onOpenDocument={setOpenDocId}
                  onChanged={refreshAll}
                />
                {data.limitations.length > 0 && (
                  <section className="rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2">
                    <h4 className="mb-1 text-xs font-semibold text-ink-secondary">
                      What this review could not check
                    </h4>
                    <ul className="list-disc space-y-0.5 pl-4 text-[11px] text-ink-muted">
                      {data.limitations.map((l) => (
                        <li key={l}>{l}</li>
                      ))}
                    </ul>
                  </section>
                )}
              </div>
            ) : (
              <p className="text-sm text-ink-muted">
                {review.loading ? 'Loading review…' : 'The scrutiny review is available for API-backed applications.'}
              </p>
            ))}

          {tab === 'documents' &&
            (data ? (
              <DocumentCards review={data} onOpen={setOpenDocId} />
            ) : (
              <p className="text-sm text-ink-muted">{review.loading ? 'Loading…' : 'No review data.'}</p>
            ))}

          {tab === 'compare' && <ReconciliationPanel detail={detail} role={role} onChanged={refreshAll} />}

          {tab === 'authenticity' && (
            <AuthenticityPanel detail={detail} role={role} onChanged={refreshAll} />
          )}

          {tab === 'review' && (
            <DecisionPanel detail={detail} review={data} role={role} onChanged={refreshAll} />
          )}
        </div>
      </Card>

      {openDocId && source === 'api' && (
        <DocumentReportPanel
          role={role}
          applicationId={detail.id}
          documentId={openDocId}
          onClose={() => setOpenDocId(null)}
          onChanged={refreshAll}
        />
      )}
    </AppShell>
  )
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-ink-muted">{label}</div>
      <div className="mt-0.5 truncate text-sm font-medium text-ink">{value}</div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-border pb-2 last:border-0">
      <dt className="text-ink-muted">{label}</dt>
      <dd className="text-right font-medium text-ink">{value}</dd>
    </div>
  )
}
