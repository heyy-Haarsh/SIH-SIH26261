import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Download, FileText, Info, Plug } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { Card } from '@/components/ui/Card'
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

/** Scrutiny officer / regional officer view of one application. Applicants have their own page. */
export function ApplicationDetailPage() {
  const { id } = useParams()
  const { role } = useRole()
  const staff = role === 'officer' || role === 'regional_officer'
  const { detail, source, loading, error, reload } = useApplicationDetail(staff ? id : undefined)
  const review = useRefreshable<ScrutinyReview>(
    staff && id && source === 'api' ? () => api.getScrutinyReview(role, id) : null,
    `${id}:${source}:${role}`,
  )
  const [tab, setTab] = useState('issues')
  const [openDocId, setOpenDocId] = useState<string | null>(null)
  const [workflowMsg, setWorkflowMsg] = useState<string | null>(null)
  const [workflowErr, setWorkflowErr] = useState(false)
  const [busy, setBusy] = useState(false)
  const pickedInitialTab = useRef<string | null>(null)

  const reloadReview = review.reload
  const refreshAll = useCallback(async () => {
    await Promise.all([reload(), reloadReview()])
  }, [reload, reloadReview])

  useEffect(() => {
    if (!detail || pickedInitialTab.current === detail.id) return
    pickedInitialTab.current = detail.id
    if (detail.status === 'clarification_required' || detail.status === 'resubmitted') setTab('review')
  }, [detail])

  const roleLabel =
    role === 'officer' ? 'Scrutiny Officer' : role === 'regional_officer' ? 'Regional Officer' : 'Applicant'

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
  const canStart = ['submitted', 'processing', 'resubmitted'].includes(detail.status)

  async function startScrutiny() {
    setBusy(true)
    setWorkflowMsg(null)
    setWorkflowErr(false)
    try {
      await api.startScrutiny(role, detail!.id)
      setWorkflowMsg('Scrutiny started.')
      await refreshAll()
    } catch (err) {
      setWorkflowMsg(errorText(err, 'Could not start scrutiny'))
      setWorkflowErr(true)
    } finally {
      setBusy(false)
    }
  }

  async function checkIssuers() {
    setBusy(true)
    setWorkflowMsg(null)
    setWorkflowErr(false)
    try {
      await api.runApplicationDocVerification(role, detail!.id)
      setWorkflowMsg('Issuer check finished. Results are from the local demo issuer — not an official authority.')
      await refreshAll()
    } catch (err) {
      setWorkflowMsg(errorText(err, 'Issuer check failed. Is the simulated issuer running on port 8001?'))
      setWorkflowErr(true)
    } finally {
      setBusy(false)
    }
  }

  async function downloadPdf() {
    setBusy(true)
    setWorkflowMsg(null)
    setWorkflowErr(false)
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
      setWorkflowErr(true)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AppShell
      title={detail.applicationNumber}
      breadcrumbs={[roleLabel, 'Applications', detail.applicationNumber]}
    >
      {/* ── Compact application header ───────────────────────────────── */}
      <div className="mb-3 overflow-hidden rounded-[var(--radius-lg)] border border-border bg-white shadow-[var(--shadow-card)]">

        {/* Demo / synthetic data notice — slim top strip */}
        {source !== 'api' && (
          <div className="flex items-center gap-2 border-b border-sky-100 bg-status-info-bg px-4 py-1.5 text-[11px] text-status-info">
            <Info size={12} className="shrink-0" />
            <span>Synthetic demo data — open an application created via the API for a live scrutiny review.</span>
          </div>
        )}

        {/* Main header row */}
        <div className="flex flex-wrap items-start justify-between gap-3 px-4 pt-3 pb-2">
          {/* Left: institution + badges */}
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-base font-bold text-ink">{detail.institutionName}</h2>
              <ApplicationStatusBadge status={detail.status} />
              <PriorityBadge priority={detail.priority} />
              {typeof detail.priorityScore === 'number' && (
                <span
                  className="inline-flex items-center gap-1 rounded border border-border bg-surface px-2 py-0.5 text-xs font-semibold text-ink"
                  title="Priority score — ordering aid only, not proof of fraud or compliance"
                >
                  <span className="font-normal text-ink-muted">Score</span>
                  {detail.priorityScore}
                </span>
              )}
            </div>
            <p className="mt-0.5 text-xs text-ink-secondary">
              {detail.category} · {detail.programName} · AY {detail.academicYear}
            </p>
            <p className="mt-0.5 text-[11px] text-ink-muted">
              #{detail.applicationNumber} · Submitted {formatDate(detail.submittedAt)} · Officer: {detail.assignedOfficer ?? 'Unassigned'} · {detail.contactEmail}
            </p>
          </div>

          {/* Right: action buttons */}
          <div className="flex shrink-0 flex-wrap items-center gap-1.5">
            {source === 'api' && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  leftIcon={<Plug size={13} />}
                  disabled={busy}
                  onClick={() => void checkIssuers()}
                >
                  Check issuers
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  leftIcon={<Download size={13} />}
                  disabled={busy}
                  onClick={() => void downloadPdf()}
                >
                  PDF report
                </Button>
              </>
            )}
            {canStart && (
              <Button size="sm" disabled={busy} onClick={() => void startScrutiny()}>
                Start scrutiny
              </Button>
            )}
          </div>
        </div>

        {/* Status snapshot row — inline chips */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border bg-surface px-4 py-2 text-xs">
          <StatusChip label="Status" value={detail.status.replace(/_/g, ' ')} />
          <StatusChip label="Open issues" value={data ? String(data.openIssueCount) : '—'} highlight={data ? data.openIssueCount > 0 : false} />
          <StatusChip label="Uploaded" value={`${detail.documents.length} doc${detail.documents.length !== 1 ? 's' : ''}`} />
          <StatusChip label="Missing" value={data ? String(data.missingDocuments.length) : '—'} highlight={data ? data.missingDocuments.length > 0 : false} />
          {detail.lastTransitionNote && (
            <span className="ml-auto text-[11px] text-ink-muted">
              <span className="font-medium">Last note: </span>
              {detail.lastTransitionNote.split('\n')[0].slice(0, 80)}
              {detail.lastTransitionNote.length > 80 ? '…' : ''}
            </span>
          )}
        </div>

        {/* Workflow feedback — only shown when something happened */}
        {workflowMsg && (
          <div
            role="status"
            className={`border-t px-4 py-1.5 text-xs ${
              workflowErr
                ? 'border-red-100 bg-status-failed-bg text-status-failed'
                : 'border-border bg-surface text-ink-secondary'
            }`}
          >
            {workflowMsg}
          </div>
        )}
      </div>

      {/* ── Tabs + content ───────────────────────────────────────────── */}
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

        <div className="p-4">
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

/** Inline status chip used in the header snapshot row. */
function StatusChip({ label, value, highlight = false }: { label: string; value: string; highlight?: boolean }) {
  return (
    <span className="flex items-center gap-1">
      <span className="text-ink-muted">{label}:</span>
      <span className={`font-medium ${highlight ? 'text-status-failed' : 'text-ink'}`}>{value}</span>
    </span>
  )
}
