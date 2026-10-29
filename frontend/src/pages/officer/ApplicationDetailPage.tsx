/**
 * Scrutiny Workspace — three-panel layout.
 *
 * Panel A (left  250px)  — Application details + document checklist
 * Panel B (center flex)  — Four-tab investigation workspace:
 *                           Findings | Authenticity | Clarifications | History
 * Panel C (right 320px)  — Status summary + quick actions + decision form
 *
 * Three slide-over drawers (only one open at a time):
 *   "doc"    — Document Evidence Viewer  (opened from Panel A)
 *   "finding"— Finding Details           (opened from Findings tab)
 *   "clarify"— Clarification Composer    (opened from Panel C)
 *
 * All existing business logic, APIs, permissions, and audit behaviour
 * are preserved exactly. No functionality has been removed.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Download,
  FileQuestion,
  FileText,
  Info,
  MessageSquare,
  Plug,
  Wand2,
} from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { Tabs } from '@/components/ui/Tabs'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'
import { SkeletonDetailLayout } from '@/components/ui/Skeleton'
import { SlideOver } from '@/components/ui/SlideOver'
import { StatusDot } from '@/components/ui/StatusDot'
import { Input, Textarea } from '@/components/ui/Input'
import { AuthenticityPanel } from '@/components/scrutiny/AuthenticityPanel'
import { DecisionPanel } from '@/components/scrutiny/DecisionPanel'
import { DocumentReportPanel } from '@/components/scrutiny/DocumentReportPanel'
import { IssuesPanel } from '@/components/scrutiny/IssuesPanel'
import { ReconciliationPanel } from '@/components/scrutiny/ReconciliationPanel'
import { CorrectionTable, rowsFromOfficerText } from '@/components/shared/CorrectionTable'
import { errorText } from '@/components/scrutiny/scrutinyUi'
import { formatDate, formatDateTime, formatRelative } from '@/lib/format'
import { useRole } from '@/app/RoleContext'
import { useApplicationDetail } from '@/hooks/useApplicationDetail'
import { useRefreshable } from '@/hooks/useRefreshable'
import { api } from '@/services/api'
import type {
  ApplicationDetail,
  RuleCheckRow,
  ScrutinyReview,
} from '@/types'

// ── Tab IDs for the center panel ─────────────────────────────────────────────
type CenterTab = 'findings' | 'authenticity' | 'clarifications' | 'history'
const CENTER_TABS: CenterTab[] = ['findings', 'authenticity', 'clarifications', 'history']

// ── Drawer identifiers ────────────────────────────────────────────────────────
type DrawerId = 'doc' | 'finding' | 'clarify' | null

// ── Design tokens (unchanged from existing codebase) ─────────────────────────
const BDR = '#F0F0F0'
const BDR_STRONG = '#E0E0E0'
const INK = '#111111'
const INK2 = '#555555'
const MUT = '#888888'
const SURF = '#FAFAFA'
const WHITE = '#FFFFFF'

// ─────────────────────────────────────────────────────────────────────────────
export function ApplicationDetailPage() {
  const { id } = useParams()
  const { role } = useRole()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const staff = role === 'officer' || role === 'regional_officer'

  // ── Data ────────────────────────────────────────────────────────────────────
  const { detail, source, loading, error, reload } = useApplicationDetail(staff ? id : undefined)
  const review = useRefreshable<ScrutinyReview>(
    staff && id && source === 'api' ? () => api.getScrutinyReview(role, id) : null,
    `${id}:${source}:${role}`,
  )
  const [ruleChecks, setRuleChecks] = useState<RuleCheckRow[] | null>(null)
  const [ruleChecksLoading, setRuleChecksLoading] = useState(false)

  // ── Center tab ───────────────────────────────────────────────────────────────
  const urlTab = searchParams.get('tab') as CenterTab | null
  const [tab, setTab] = useState<CenterTab>(
    CENTER_TABS.includes(urlTab as CenterTab) ? (urlTab as CenterTab) : 'findings',
  )
  function changeTab(t: string) {
    const tid = t as CenterTab
    setTab(tid)
    setSearchParams(
      (prev) => { const n = new URLSearchParams(prev); n.set('tab', tid); return n },
      { replace: true },
    )
  }

  // ── Drawer state ─────────────────────────────────────────────────────────────
  const [drawer, setDrawer] = useState<DrawerId>(null)
  const [openDocId, setOpenDocId] = useState<string | null>(null)
  // For Finding drawer: store the selected issue key
  const [focusedIssueKey, setFocusedIssueKey] = useState<string | null>(null)

  function openDocDrawer(docId: string) {
    setOpenDocId(docId)
    setDrawer('doc')
  }
  function openFindingDrawer(issueKey: string) {
    setFocusedIssueKey(issueKey)
    setDrawer('finding')
  }
  function openClarifyDrawer() {
    setDrawer('clarify')
  }
  function closeDrawer() {
    setDrawer(null)
  }

  // ── Workflow state ────────────────────────────────────────────────────────────
  const [workflowMsg, setWorkflowMsg] = useState<string | null>(null)
  const [workflowErr, setWorkflowErr] = useState(false)
  const [busy, setBusy] = useState(false)
  const pickedInitialTab = useRef<string | null>(null)

  const reloadReview = review.reload
  const refreshAll = useCallback(async () => {
    await Promise.all([reload(), reloadReview()])
  }, [reload, reloadReview])

  // Auto-switch to clarifications when resubmitted
  useEffect(() => {
    if (!detail || pickedInitialTab.current === detail.id) return
    pickedInitialTab.current = detail.id
    if (!urlTab && (detail.status === 'clarification_required' || detail.status === 'resubmitted')) {
      changeTab('clarifications')
    }
  }, [detail]) // eslint-disable-line react-hooks/exhaustive-deps

  // Lazy-load rule checks for Findings tab
  useEffect(() => {
    if (tab !== 'findings' || !id || !staff || source !== 'api' || ruleChecks !== null) return
    setRuleChecksLoading(true)
    api.listRuleChecks(role, id)
      .then((d) => setRuleChecks(d))
      .catch(() => setRuleChecks([]))
      .finally(() => setRuleChecksLoading(false))
  }, [tab, id, role, staff, source, ruleChecks]) // eslint-disable-line react-hooks/exhaustive-deps

  const roleLabel =
    role === 'officer' ? 'Scrutiny Officer'
    : role === 'regional_officer' ? 'Regional Officer'
    : 'Applicant'

  // ── Not staff ────────────────────────────────────────────────────────────────
  if (!staff) {
    return (
      <AppShell title="Scrutiny view" breadcrumbs={[roleLabel, 'Applications']}>
        <EmptyState
          icon={FileText}
          title="This page is for scrutiny officers"
          description="Applicants see their own application and deficiencies on their application page."
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
      <AppShell title="Loading Application…" breadcrumbs={[roleLabel, 'Applications']}>
        <SkeletonDetailLayout />
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
  const openClarifications = (detail.deficiencies ?? []).filter((d) => d.status === 'open').length
  const respondedClarifications = (detail.deficiencies ?? []).filter((d) => d.status === 'responded').length
  const missingDocs = data?.missingDocuments ?? []
  const canStart = ['submitted', 'processing', 'resubmitted'].includes(detail.status)
  const canAct = role === 'officer' || role === 'regional_officer'

  // Rule-check failure counts for Findings tab badge
  const ruleFailCount = ruleChecks
    ? ruleChecks.filter((r) => r.state === 'failed' || r.state === 'warning').length
    : 0
  const findingsBadge = ((data?.openIssueCount ?? 0) + ruleFailCount + mismatchCount) || undefined

  const CENTER_TAB_CONFIG = [
    { id: 'findings', label: 'Findings', count: findingsBadge },
    { id: 'authenticity', label: 'Authenticity' },
    {
      id: 'clarifications', label: 'Clarifications',
      count: (respondedClarifications + openClarifications) || undefined,
    },
    { id: 'history', label: 'History' },
  ]

  // ── Workflow actions ─────────────────────────────────────────────────────────
  async function startScrutiny() {
    setBusy(true); setWorkflowMsg(null); setWorkflowErr(false)
    try {
      await api.startScrutiny(role, detail!.id)
      setWorkflowMsg('Scrutiny started.')
      await refreshAll()
    } catch (err) {
      setWorkflowMsg(errorText(err, 'Could not start scrutiny')); setWorkflowErr(true)
    } finally { setBusy(false) }
  }

  async function checkIssuers() {
    setBusy(true); setWorkflowMsg(null); setWorkflowErr(false)
    try {
      await api.runApplicationDocVerification(role, detail!.id)
      setWorkflowMsg('Issuer check complete. Results are from the local demo issuer — not an official authority.')
      await refreshAll()
    } catch (err) {
      setWorkflowMsg(errorText(err, 'Issuer check failed. Is the simulated issuer running on port 8001?'))
      setWorkflowErr(true)
    } finally { setBusy(false) }
  }

  async function downloadPdf() {
    setBusy(true); setWorkflowMsg(null); setWorkflowErr(false)
    try {
      const { blob, fileName } = await api.downloadScrutinyPdf(role, detail!.id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href = url
      a.download = fileName ?? `scrutiny-report-${detail!.applicationNumber}.pdf`
      document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url)
    } catch (err) {
      setWorkflowMsg(errorText(err, 'Could not generate the PDF report')); setWorkflowErr(true)
    } finally { setBusy(false) }
  }

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <AppShell
      title={detail.applicationNumber}
      description="Evidence-first case workspace"
      breadcrumbs={[roleLabel, 'Applications', detail.applicationNumber]}
    >
      {/* ── Slim application header ──────────────────────────────────────── */}
      <div
        className="mb-3 overflow-hidden rounded-xl"
        style={{ background: WHITE, border: `1px solid ${BDR}` }}
      >
        {source !== 'api' && (
          <div className="flex items-center gap-2 px-4 py-1.5 text-[11px]"
            style={{ background: '#EFF6FF', borderBottom: '1px solid #BFDBFE', color: '#1D4ED8' }}
          >
            <Info size={12} className="shrink-0" />
            Synthetic demo data — open an API-backed application for a live scrutiny review.
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
          {/* Back + title */}
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={() => navigate(-1)}
              className="inline-flex shrink-0 items-center gap-1 text-sm transition-opacity hover:opacity-70"
              style={{ color: MUT }}
            >
              <ArrowLeft size={14} />
            </button>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-bold" style={{ color: INK }}>
                  {detail.institutionName}
                </span>
                <StatusDot status={detail.status} label={detail.status.replace(/_/g, ' ')} />
                {typeof detail.priorityScore === 'number' && (
                  <span
                    className="rounded-md border px-2 py-0.5 text-[11px]"
                    style={{ border: `1px solid ${BDR_STRONG}`, color: MUT }}
                    title="Priority score — ordering aid only"
                  >
                    Score {detail.priorityScore}
                  </span>
                )}
              </div>
              <p className="text-[11px]" style={{ color: INK2 }}>
                {detail.category} · {detail.programName} · AY {detail.academicYear}
                {' '}· #{detail.applicationNumber}
                {detail.assignedOfficer && ` · ${detail.assignedOfficer}`}
              </p>
            </div>
          </div>

          {/* Header actions */}
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            {source === 'api' && (
              <>
                <Button variant="outline" size="sm" leftIcon={<Plug size={13} />} disabled={busy} onClick={() => void checkIssuers()}>
                  Check issuers
                </Button>
                <Button variant="outline" size="sm" leftIcon={<Download size={13} />} disabled={busy} onClick={() => void downloadPdf()}>
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

        {/* Workflow feedback */}
        {workflowMsg && (
          <div
            role="status"
            className="px-5 py-2 text-xs"
            style={{
              borderTop: `1px solid ${BDR}`,
              background: workflowErr ? '#FEF2F2' : '#F0FDF4',
              color: workflowErr ? '#991B1B' : '#166534',
            }}
          >
            {workflowMsg}
          </div>
        )}
      </div>

      {/* ── Three-panel workspace ─────────────────────────────────────────── */}
      <div
        className="grid overflow-hidden rounded-xl"
        style={{
          gridTemplateColumns: '250px minmax(0,1fr) 340px',
          height: 'calc(100vh - 220px)',
          minHeight: '520px',
          border: `1px solid ${BDR}`,
          background: WHITE,
        }}
      >
        {/* ══ PANEL A — Application context + document checklist ══ */}
        <PanelA
          detail={detail}
          review={data}
          source={source}
          missingDocs={missingDocs}
          onOpenDocument={openDocDrawer}
        />

        {/* ══ PANEL B — Investigation workspace ══ */}
        <div
          className="flex flex-col overflow-hidden"
          style={{ borderLeft: `1px solid ${BDR}`, borderRight: `1px solid ${BDR}` }}
        >
          {/* Tab bar */}
          <div className="shrink-0 px-4 pt-1.5" style={{ borderBottom: `1px solid ${BDR}` }}>
            <Tabs active={tab} onChange={changeTab} tabs={CENTER_TAB_CONFIG} />
          </div>

          {/* Tab body */}
          <div className="flex-1 overflow-y-auto p-4">
            {review.error && !data && source === 'api' && (
              <p className="mb-3 rounded px-3 py-2 text-xs" role="alert"
                style={{ background: '#FEF2F2', color: '#B91C1C' }}>
                {review.error}
              </p>
            )}

            {/* Findings = rule checks + cross-doc + issues */}
            {tab === 'findings' && (
              <FindingsTab
                detail={detail}
                review={data}
                ruleChecks={ruleChecks}
                ruleChecksLoading={ruleChecksLoading}
                role={role}
                source={source}
                onOpenDocument={openDocDrawer}
                onOpenFinding={openFindingDrawer}
                onChanged={refreshAll}
              />
            )}

            {tab === 'authenticity' && (
              <AuthenticityPanel detail={detail} role={role} onChanged={refreshAll} />
            )}

            {tab === 'clarifications' && (
              <ClarificationsTab detail={detail} role={role} onChanged={refreshAll} />
            )}

            {tab === 'history' && (
              <HistoryTab detail={detail} />
            )}
          </div>
        </div>

        {/* ══ PANEL C — Summary + actions + decision ══ */}
        <PanelC
          detail={detail}
          review={data}
          role={role}
          canAct={canAct}
          onChanged={refreshAll}
          onRequestClarification={openClarifyDrawer}
        />
      </div>

      <SlideOver
        open={drawer === 'doc' && openDocId !== null && source === 'api'}
        onClose={closeDrawer}
        title="Document viewer"
        width="max-w-[640px]"
      >
        {openDocId && source === 'api' && (
          <DocumentReportPanel
            role={role}
            applicationId={detail.id}
            documentId={openDocId}
            onClose={closeDrawer}
            onChanged={refreshAll}
          />
        )}
      </SlideOver>

      {/* ══ DRAWER 2 — Finding Details ══ */}
      <SlideOver
        open={drawer === 'finding' && focusedIssueKey !== null}
        onClose={closeDrawer}
        title="Finding detail"
      >
        {data && focusedIssueKey && (
          <FindingDetailDrawer
            review={data}
            issueKey={focusedIssueKey}
            role={role}
            detail={detail}
            onChanged={refreshAll}
            onOpenDocument={openDocDrawer}
            onClose={closeDrawer}
          />
        )}
        {!data && (
          <p className="text-sm" style={{ color: MUT }}>
            Finding details require an API-backed application.
          </p>
        )}
      </SlideOver>

      {/* ══ DRAWER 3 — Clarification Composer ══ */}
      <SlideOver
        open={drawer === 'clarify'}
        onClose={closeDrawer}
        title="Request clarification"
        subtitle="The applicant sees this message word for word."
        allowEasyClose={false}
      >
        {data && (
          <ClarificationComposerDrawer
            detail={detail}
            review={data}
            role={role}
            onClose={closeDrawer}
            onChanged={refreshAll}
          />
        )}
        {!data && (
          <p className="text-sm" style={{ color: MUT }}>
            Clarification requests require an API-backed application.
          </p>
        )}
      </SlideOver>
    </AppShell>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Panel A — Application context + document checklist
// ─────────────────────────────────────────────────────────────────────────────
function PanelA({
  detail,
  review,
  source,
  missingDocs,
  onOpenDocument,
}: {
  detail: ApplicationDetail
  review: ScrutinyReview | null | undefined
  source: string
  missingDocs: string[]
  onOpenDocument: (docId: string) => void
}) {
  return (
    <div className="flex flex-col overflow-y-auto" style={{ background: SURF }}>
      {/* Application details */}
      <section className="shrink-0 px-4 py-3.5" style={{ borderBottom: `1px solid ${BDR}` }}>
        <h3 className="mb-2.5 text-[10px] font-semibold uppercase tracking-widest" style={{ color: MUT }}>
          Application
        </h3>
        <dl className="space-y-1.5">
          {([
            ['ID', `#${detail.applicationNumber}`],
            ['Institution', detail.institutionName],
            ['Category', detail.category],
            ['Status', detail.status.replace(/_/g, ' ')],
            ['Officer', detail.assignedOfficer ?? 'Unassigned'],
            ['Submitted', formatDate(detail.submittedAt)],
          ] as [string, string][]).map(([label, value]) => (
            <div key={label} className="flex gap-2 text-[11px]">
              <dt className="w-[72px] shrink-0" style={{ color: MUT }}>{label}</dt>
              <dd className="min-w-0 truncate font-medium" style={{ color: INK }} title={value}>{value}</dd>
            </div>
          ))}
        </dl>
      </section>

      {/* Missing items */}
      {(missingDocs.length > 0 || (review && review.openIssueCount > 0)) && (
        <section className="shrink-0 px-4 py-3" style={{ borderBottom: `1px solid ${BDR}` }}>
          <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-widest" style={{ color: MUT }}>
            Outstanding
          </h3>
          {missingDocs.length > 0 && (
            <div className="mb-1.5 flex items-start gap-1.5">
              <AlertTriangle size={11} className="mt-0.5 shrink-0" style={{ color: '#B45309' }} />
              <p className="text-[11px]" style={{ color: '#92400E' }}>
                {missingDocs.length} missing document{missingDocs.length !== 1 ? 's' : ''}:
                {' '}{missingDocs.join(', ')}
              </p>
            </div>
          )}
          {review && review.openIssueCount > 0 && (
            <div className="flex items-center gap-1.5">
              <AlertTriangle size={11} className="shrink-0" style={{ color: '#991B1B' }} />
              <p className="text-[11px]" style={{ color: '#991B1B' }}>
                {review.openIssueCount} open finding{review.openIssueCount !== 1 ? 's' : ''}
              </p>
            </div>
          )}
        </section>
      )}

      {/* Document checklist */}
      <section className="flex-1 overflow-y-auto px-4 py-3">
        <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-widest" style={{ color: MUT }}>
          Documents ({detail.documents.length})
        </h3>

        {detail.documents.length === 0 ? (
          <p className="text-[11px]" style={{ color: MUT }}>No documents uploaded.</p>
        ) : (
          <ul className="space-y-1">
            {detail.documents.map((doc) => {
              const hasFindings = detail.findings?.some((f) => f.documentId === doc.id)
              return (
                <li key={doc.id}>
                  <button
                    type="button"
                    disabled={source !== 'api'}
                    onClick={() => onOpenDocument(doc.id)}
                    className="flex w-full items-start gap-2 rounded-lg px-2 py-2 text-left transition-colors hover:bg-white disabled:cursor-default"
                    style={{ minHeight: '44px' }}
                    title={source !== 'api' ? 'Document viewer requires an API application' : undefined}
                  >
                    <DocStatusIcon doc={doc} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[11px] font-medium leading-tight" style={{ color: INK }}>
                        {doc.fileName ?? doc.requirementName ?? doc.id}
                      </p>
                      <p className="text-[10px]" style={{ color: MUT }}>
                        {doc.requirementName && doc.fileName ? doc.requirementName : ''}
                      </p>
                    </div>
                    {hasFindings && (
                      <span
                        className="mt-0.5 shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-semibold"
                        style={{ background: '#FEF2F2', color: '#991B1B' }}
                        title="Has related findings"
                      >
                        !
                      </span>
                    )}
                  </button>
                </li>
              )
            })}
          </ul>
        )}

        {/* Requirements not yet uploaded */}
        {detail.requirements && (
          <div className="mt-3 space-y-1">
            {detail.requirements
              .filter((r) => r.mandatory && !detail.documents.find((d) => d.requirementCode === r.code))
              .map((r) => (
                <div key={r.code} className="flex items-center gap-2 rounded-lg px-2 py-2"
                  style={{ minHeight: '44px' }}>
                  <FileQuestion size={13} className="shrink-0" style={{ color: MUT }} />
                  <p className="min-w-0 flex-1 truncate text-[11px]" style={{ color: MUT }}>
                    {r.name}
                  </p>
                  <span className="text-[10px] font-medium" style={{ color: '#B45309' }}>
                    Missing
                  </span>
                </div>
              ))}
          </div>
        )}
      </section>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Panel C — Summary + quick actions + decision form
// ─────────────────────────────────────────────────────────────────────────────
function PanelC({
  detail,
  review,
  role,
  canAct: _canAct,
  onChanged,
  onRequestClarification,
}: {
  detail: ApplicationDetail
  review: ScrutinyReview | null | undefined
  role: string
  canAct: boolean
  onChanged: () => Promise<unknown> | void
  onRequestClarification: () => void
}) {
  const openFindings = review?.openIssueCount ?? 0
  const missingDocs = review?.missingDocuments.length ?? 0
  const openClarifs = (detail.deficiencies ?? []).filter((d) => d.status === 'open').length

  return (
    <div className="flex flex-col overflow-hidden h-full">
      {/* Status summary */}
      <section
        className="shrink-0 px-4 py-3"
        style={{ borderBottom: `1px solid ${BDR}`, background: SURF }}
      >
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: MUT }}>
            Review Status
          </h3>
          <span
            className="rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
            style={{
              background: detail.status === 'recommended' ? '#F0FDF4' : detail.status === 'rejected' ? '#FEF2F2' : '#EFF6FF',
              color: detail.status === 'recommended' ? '#166534' : detail.status === 'rejected' ? '#991B1B' : '#1D4ED8',
            }}
          >
            {detail.statusLabel ?? detail.status.replace(/_/g, ' ')}
          </span>
        </div>
        <div className="space-y-1.5">
          <SummaryRow
            label="Open findings"
            value={openFindings}
            tone={openFindings > 0 ? 'warn' : 'ok'}
          />
          <SummaryRow
            label="Missing documents"
            value={missingDocs}
            tone={missingDocs > 0 ? 'warn' : 'ok'}
          />
          <SummaryRow
            label="Pending clarifications"
            value={openClarifs}
            tone={openClarifs > 0 ? 'warn' : 'ok'}
          />
        </div>
      </section>

      {/* DecisionPanel with full tabbed navigation & popup modal support */}
      <div className="flex-1 overflow-hidden flex flex-col min-h-0">
        <DecisionPanel
          detail={detail}
          review={review ?? undefined}
          role={role}
          onChanged={onChanged}
          onRequestClarificationDrawer={onRequestClarification}
        />
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Findings tab — combines rule checks + cross-doc + IssuesPanel
// ─────────────────────────────────────────────────────────────────────────────
function FindingsTab({
  detail,
  review,
  ruleChecks,
  ruleChecksLoading,
  role,
  source,
  onOpenDocument,
  onOpenFinding,
  onChanged,
}: {
  detail: ApplicationDetail
  review: ScrutinyReview | null | undefined
  ruleChecks: RuleCheckRow[] | null
  ruleChecksLoading: boolean
  role: string
  source: string
  onOpenDocument: (docId: string) => void
  onOpenFinding: (issueKey: string) => void
  onChanged: () => Promise<unknown> | void
}) {
  const [section, setSection] = useState<'issues' | 'rules' | 'cross'>('issues')

  const ruleFailCount = ruleChecks
    ? ruleChecks.filter((r) => r.state === 'failed' || r.state === 'warning').length
    : 0
  const mismatchCount = detail.discrepancies.filter((d) => d.outcome !== 'MATCH').length

  return (
    <div className="space-y-4">
      {/* Sub-section pills */}
      <div className="flex flex-wrap gap-2">
        {([
          ['issues', 'Findings', review?.openIssueCount],
          ['rules', 'Rule checks', ruleFailCount || undefined],
          ['cross', 'Cross-document', mismatchCount || undefined],
        ] as [typeof section, string, number | undefined][]).map(([id, label, count]) => (
          <button
            key={id}
            type="button"
            onClick={() => setSection(id)}
            className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-medium transition-colors"
            style={{
              background: section === id ? INK : '#F0F0F0',
              color: section === id ? '#FFFFFF' : INK2,
            }}
          >
            {label}
            {count != null && count > 0 && (
              <span
                className="rounded-full px-1.5 py-0.5 text-[10px] font-semibold"
                style={{
                  background: section === id ? 'rgba(255,255,255,0.25)' : '#E0E0E0',
                  color: section === id ? '#FFFFFF' : '#555555',
                }}
              >
                {count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Issues (open findings from IssuesPanel) */}
      {section === 'issues' && (
        review ? (
          <IssuesPanel
            review={review}
            role={role}
            onOpenDocument={onOpenDocument}
            onChanged={onChanged}
          />
        ) : (
          <EmptyCard
            icon={<FileText size={20} style={{ color: MUT }} />}
            message={source !== 'api' ? 'Findings require an API-backed application.' : 'Loading findings…'}
          />
        )
      )}

      {/* Rule checks */}
      {section === 'rules' && (
        ruleChecksLoading ? (
          <p className="text-sm" style={{ color: MUT }}>Loading rule checks…</p>
        ) : !ruleChecks || ruleChecks.length === 0 ? (
          <EmptyCard
            icon={<CheckCircle2 size={20} style={{ color: MUT }} />}
            message={ruleChecks === null
              ? 'Loading rule checks for this application.'
              : 'No rule checks found. Rule checks run automatically during validation.'}
          />
        ) : (
          <RuleChecksView ruleChecks={ruleChecks} />
        )
      )}

      {/* Cross-document */}
      {section === 'cross' && (
        <div>
          <div
            className="mb-3 rounded-xl px-4 py-2.5 text-xs leading-relaxed"
            style={{ background: '#F0F9FF', border: '1px solid #BAE6FD', color: '#0369A1' }}
          >
            <strong>Note:</strong> Mismatches compare extracted fields across documents.
            They do not imply fraud or determine the review outcome.
          </div>
          <ReconciliationPanel detail={detail} role={role} onChanged={onChanged} />
        </div>
      )}

      {/* Limitations */}
      {section === 'issues' && review && review.limitations.length > 0 && (
        <div
          className="rounded-xl px-4 py-3"
          style={{ background: SURF, border: `1px solid ${BDR_STRONG}` }}
        >
          <h4 className="text-xs font-semibold mb-1" style={{ color: INK2 }}>
            What this review could not check
          </h4>
          <ul className="list-disc pl-4 space-y-0.5 text-[11px]" style={{ color: MUT }}>
            {review.limitations.map((l) => <li key={l}>{l}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Finding Detail Drawer body
// ─────────────────────────────────────────────────────────────────────────────
function FindingDetailDrawer({
  review,
  issueKey,
  role,
  detail,
  onChanged,
  onOpenDocument,
  onClose,
}: {
  review: ScrutinyReview
  issueKey: string
  role: string
  detail: ApplicationDetail
  onChanged: () => Promise<unknown> | void
  onOpenDocument: (docId: string) => void
  onClose: () => void
}) {
  // Find the issue by key across all groups
  const issue = review.issueGroups.flatMap((g) => g.issues).find((i) => i.key === issueKey)
  if (!issue) {
    return <p className="text-sm" style={{ color: MUT }}>Finding not found.</p>
  }

  // Find related discrepancy (cross-doc)
  const discrepancy = detail.discrepancies.find((d) =>
    issue.findingIds.some((fid) => d.fingerprint === fid || d.id === fid),
  )

  const SEVERITY_COLOR: Record<string, { bg: string; text: string }> = {
    critical: { bg: '#FEF2F2', text: '#991B1B' },
    high:     { bg: '#FEF2F2', text: '#991B1B' },
    medium:   { bg: '#FFFBEB', text: '#92400E' },
    low:      { bg: '#F0F9FF', text: '#0369A1' },
    info:     { bg: '#F5F5F5', text: '#555555' },
  }
  const sev = SEVERITY_COLOR[issue.severity] ?? SEVERITY_COLOR['info']

  return (
    <div className="space-y-5">
      {/* Title + status + severity */}
      <div>
        <div className="flex flex-wrap items-start gap-2 mb-2">
          <span
            className="rounded-md px-2 py-0.5 text-[10px] font-semibold"
            style={{ background: sev.bg, color: sev.text }}
          >
            {issue.severity.toUpperCase()}
          </span>
          <span className="rounded-md px-2 py-0.5 text-[10px] font-semibold"
            style={{ background: '#F5F5F5', color: '#555555' }}>
            {issue.status}
          </span>
          {issue.layer && (
            <span className="text-[10px]" style={{ color: MUT }}>{issue.layer}</span>
          )}
        </div>
        <h3 className="text-sm font-semibold leading-snug" style={{ color: INK }}>{issue.title}</h3>
        {issue.documentName && (
          <p className="mt-1 text-xs" style={{ color: INK2 }}>Document: {issue.documentName}</p>
        )}
      </div>

      {/* Explanation */}
      {issue.explanation && (
        <div>
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest" style={{ color: MUT }}>
            Explanation
          </p>
          <p className="text-sm leading-relaxed" style={{ color: INK2 }}>{issue.explanation}</p>
        </div>
      )}

      {/* Regulatory / rule reference */}
      {(issue.handbook?.title || issue.handbook?.section || issue.handbook?.note) && (
        <div
          className="rounded-lg px-3 py-2.5"
          style={{ background: SURF, border: `1px solid ${BDR_STRONG}` }}
        >
          <p className="text-[10px] font-semibold uppercase tracking-widest mb-1" style={{ color: MUT }}>
            Regulatory reference
          </p>
          {issue.handbook.title && (
            <p className="text-xs font-medium" style={{ color: INK }}>{issue.handbook.title}</p>
          )}
          {issue.handbook.section && (
            <p className="text-xs mt-0.5" style={{ color: INK2 }}>
              Section {issue.handbook.section}{issue.handbook.page ? `, p${issue.handbook.page}` : ''}
            </p>
          )}
          {issue.handbook.note && (
            <p className="text-xs mt-0.5 italic" style={{ color: MUT }}>{issue.handbook.note}</p>
          )}
        </div>
      )}

      {/* Cross-document discrepancy values (source A vs B) */}
      {discrepancy && discrepancy.values.length >= 2 && (
        <div>
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest" style={{ color: MUT }}>
            Values compared
          </p>
          <div className="grid grid-cols-2 gap-3">
            {discrepancy.values.slice(0, 2).map((v, i) => (
              <div key={i} className="rounded-lg px-3 py-2.5"
                style={{ background: SURF, border: `1px solid ${BDR_STRONG}` }}>
                <p className="text-[10px] font-medium mb-1" style={{ color: MUT }}>
                  {v.documentName}{v.pageNumber != null ? ` · p${v.pageNumber}` : ''}
                </p>
                <p className="text-xs font-mono" style={{ color: INK }}>
                  {v.normalizedValue ?? v.value ?? '—'}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Document links */}
      {issue.documentId && (
        <div>
          <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-widest" style={{ color: MUT }}>
            Source document
          </p>
          <button
            type="button"
            onClick={() => { onOpenDocument(issue.documentId!); onClose() }}
            className="inline-flex items-center gap-1.5 text-xs underline"
            style={{ color: '#1D4ED8' }}
          >
            <FileText size={12} />
            {issue.documentName ?? issue.documentId}
          </button>
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Clarification Composer Drawer
// ─────────────────────────────────────────────────────────────────────────────
function ClarificationComposerDrawer({
  detail,
  review,
  role,
  onClose,
  onChanged,
}: {
  detail: ApplicationDetail
  review: ScrutinyReview
  role: string
  onClose: () => void
  onChanged: () => Promise<unknown> | void
}) {
  const [title, setTitle] = useState('Clarification required')
  const [body, setBody] = useState(review.decision?.clarificationDraftBody ?? '')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ tone: 'ok' | 'error'; text: string } | null>(null)

  const clarifiable = review.issueGroups.flatMap((g) =>
    g.issues.filter((i) => i.status === 'open' && i.findingIds.length > 0 && i.severity !== 'info'),
  )
  const chosen = clarifiable.filter((i) => selected.has(i.key))
  const chosenFindingIds = Array.from(new Set(chosen.flatMap((i) => i.findingIds)))

  function toggle(key: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  async function send() {
    if (busy || body.trim().length < 5 || title.trim().length < 3) return
    setBusy(true); setMsg(null)
    try {
      await api.requestClarification(role, detail.id, {
        title: title.trim(),
        description: body.trim(),
        finding_ids: chosenFindingIds,
      })
      setMsg({ tone: 'ok', text: 'Clarification sent. The application is now waiting for the applicant.' })
      await onChanged()
      setTimeout(onClose, 1500)
    } catch (err) {
      setMsg({ tone: 'error', text: errorText(err, 'Could not send clarification') })
    } finally { setBusy(false) }
  }

  return (
    <div className="space-y-4">
      {/* Findings selector */}
      {clarifiable.length > 0 && (
        <div>
          <p className="mb-2 text-[11px] font-semibold" style={{ color: INK }}>
            Findings covered ({chosen.length} of {clarifiable.length} selected)
          </p>
          <fieldset
            className="rounded-lg p-2 space-y-1.5 max-h-44 overflow-y-auto"
            style={{ border: `1px solid ${BDR_STRONG}` }}
          >
            {clarifiable.map((i) => (
              <label key={i.key} className="flex cursor-pointer items-start gap-2 text-xs" style={{ color: INK2 }}>
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={selected.has(i.key)}
                  onChange={() => toggle(i.key)}
                />
                <span>
                  <span className="font-medium" style={{ color: INK }}>{i.title}</span>
                  {i.documentName ? ` — ${i.documentName}` : ''}
                </span>
              </label>
            ))}
          </fieldset>
          <p className="mt-1 text-[10px]" style={{ color: MUT }}>
            Selected findings move to "clarification requested" and return to "under review" when answered.
          </p>
        </div>
      )}

      {/* Wand: use suggested text */}
      {review.decision?.clarificationDraftBody && (
        <Button
          size="sm"
          variant="outline"
          leftIcon={<Wand2 size={13} />}
          onClick={() => {
            setTitle(review.decision?.clarificationDraftTitle || title)
            setBody(review.decision!.clarificationDraftBody)
            setSelected(new Set(clarifiable.map((i) => i.key)))
          }}
        >
          Use suggested text
        </Button>
      )}

      {/* Title */}
      <div>
        <label className="mb-1 block text-xs font-semibold" style={{ color: INK }}>Title</label>
        <Input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Subject line the applicant sees"
        />
      </div>

      {/* Message */}
      <div>
        <label className="mb-1 block text-xs font-semibold" style={{ color: INK }}>Message</label>
        <Textarea
          rows={6}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Tell the applicant exactly what to correct and which document it is in…"
        />
        <p className="mt-1 text-[10px]" style={{ color: MUT }}>
          Applicants never see scores, rule codes, or forensic detail.
          Edit the suggested text carefully before sending.
        </p>
      </div>

      {/* Feedback */}
      {msg && (
        <p
          className="rounded-lg px-3 py-2 text-xs"
          style={{
            background: msg.tone === 'error' ? '#FEF2F2' : '#F0FDF4',
            color: msg.tone === 'error' ? '#991B1B' : '#166534',
          }}
        >
          {msg.text}
        </p>
      )}

      {/* Actions */}
      <div className="flex gap-2">
        <Button
          disabled={busy || body.trim().length < 5 || title.trim().length < 3}
          onClick={() => void send()}
        >
          {busy ? 'Sending…' : 'Send request'}
        </Button>
        <Button variant="outline" onClick={onClose}>
          Cancel
        </Button>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Clarifications tab (centre panel)
// ─────────────────────────────────────────────────────────────────────────────
function ClarificationsTab({
  detail,
  role,
  onChanged,
}: {
  detail: ApplicationDetail
  role: string
  onChanged: () => void
}) {
  void role; void onChanged // kept for API parity with existing pattern
  const deficiencies = detail.deficiencies ?? []
  if (deficiencies.length === 0) {
    return (
      <EmptyCard
        icon={<MessageSquare size={20} style={{ color: MUT }} />}
        message="No clarification requests for this application. Use 'Request clarification' in the right panel."
      />
    )
  }
  return (
    <div className="space-y-4">
      {deficiencies.map((d) => (
        <div
          key={d.id}
          className="rounded-xl overflow-hidden"
          style={{ border: `1px solid ${BDR}`, background: d.status === 'responded' ? '#FFFBF8' : WHITE }}
        >
          <div className="px-5 py-3.5" style={{ borderBottom: `1px solid ${BDR}` }}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold" style={{ color: INK }}>{d.title}</div>
                {d.description && (
                  <div className="text-[12px] mt-0.5" style={{ color: INK2 }}>{d.description}</div>
                )}
                <div className="text-[11px] mt-1" style={{ color: MUT }}>
                  Sent {formatDate(d.createdAt)} · {formatRelative(d.createdAt)}
                </div>
              </div>
              <StatusDot
                status={d.status === 'responded' ? 'resubmitted' : d.status === 'closed' ? 'pass' : 'clarification_required'}
                label={d.status === 'responded' ? 'Response received' : d.status === 'closed' ? 'Resolved' : 'Awaiting response'}
              />
            </div>
          </div>
          {d.status === 'responded' && d.applicantResponse && (
            <div className="px-5 py-4">
              <div className="text-[11px] font-semibold uppercase tracking-widest mb-2" style={{ color: MUT }}>
                Institution response
              </div>
              <div className="text-sm leading-relaxed" style={{ color: '#333333' }}>{d.applicantResponse}</div>
              {d.respondedAt && (
                <div className="text-[11px] mt-2" style={{ color: MUT }}>
                  Responded {formatDate(d.respondedAt)} · {formatRelative(d.respondedAt)}
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// History tab
// ─────────────────────────────────────────────────────────────────────────────
function HistoryTab({ detail }: { detail: ApplicationDetail }) {
  const events = [
    ...(detail.auditEvents ?? []).map((e) => ({
      id: `audit-${e.id}`, type: 'audit' as const,
      actor: e.actor, title: e.action.replace(/_/g, ' '),
      detail: e.detail, timestamp: e.timestamp,
    })),
    ...(detail.reviewNotes ?? []).map((n) => ({
      id: `note-${n.id}`, type: 'note' as const,
      actor: n.author, title: 'Review note',
      detail: n.content, timestamp: n.createdAt,
    })),
  ].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())

  if (events.length === 0) {
    return (
      <EmptyCard
        icon={<FileText size={20} style={{ color: MUT }} />}
        message="No history events recorded yet. Audit events and review notes appear here as the review progresses."
      />
    )
  }
  return (
    <div className="space-y-0">
      {events.map((ev, i) => (
        <div key={ev.id} className="flex gap-4 pb-4">
          <div className="flex flex-col items-center" style={{ width: '24px' }}>
            <div
              className="z-10 mt-1 h-2.5 w-2.5 rounded-full ring-2 ring-white shrink-0"
              style={{ background: ev.type === 'note' ? '#E8622A' : '#1D4ED8' }}
            />
            {i < events.length - 1 && (
              <div className="mt-1 flex-1 w-px" style={{ background: BDR_STRONG }} />
            )}
          </div>
          <div className="min-w-0 flex-1 pb-1">
            <div className="flex items-start justify-between gap-2">
              <div className="text-sm font-medium capitalize" style={{ color: INK }}>{ev.title}</div>
              <div className="shrink-0 text-[11px]" style={{ color: MUT }}>{formatRelative(ev.timestamp)}</div>
            </div>
            <div className="text-[12px] mt-0.5" style={{ color: INK2 }}>{ev.detail}</div>
            <div className="text-[11px] mt-0.5" style={{ color: MUT }}>
              {ev.actor} · {formatDate(ev.timestamp)}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// RuleChecksView (moved from outer scope, unchanged logic)
// ─────────────────────────────────────────────────────────────────────────────
const RULE_STATE_STYLE: Record<string, { bg: string; text: string; label: string }> = {
  pass:          { bg: '#F0FDF4', text: '#166534', label: 'Pass' },
  warning:       { bg: '#FFFBEB', text: '#92400E', label: 'Warning' },
  failed:        { bg: '#FEF2F2', text: '#991B1B', label: 'Failed' },
  pending:       { bg: '#F5F5F5', text: '#555555', label: 'Pending' },
  manual_review: { bg: '#F5F3FF', text: '#5B21B6', label: 'Manual review' },
  skipped:       { bg: '#F5F5F5', text: '#888888', label: 'Skipped' },
  error:         { bg: '#FEF2F2', text: '#991B1B', label: 'Error' },
  unreadable:    { bg: '#FFF7ED', text: '#C2410C', label: 'Unreadable' },
}

function RuleChecksView({ ruleChecks }: { ruleChecks: RuleCheckRow[] }) {
  const byReq = new Map<string, { code: string; checks: RuleCheckRow[] }>()
  for (const r of ruleChecks) {
    const key = r.requirementCode ?? 'unassigned'
    if (!byReq.has(key)) byReq.set(key, { code: key, checks: [] })
    byReq.get(key)!.checks.push(r)
  }
  const failCount = ruleChecks.filter((r) => r.state === 'failed').length
  const warnCount = ruleChecks.filter((r) => r.state === 'warning').length

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3 text-xs">
        <span style={{ color: MUT }}>{ruleChecks.length} check{ruleChecks.length !== 1 ? 's' : ''} total</span>
        {failCount > 0 && (
          <span className="rounded-md px-2 py-0.5 font-semibold" style={{ background: '#FEF2F2', color: '#991B1B' }}>
            {failCount} failed
          </span>
        )}
        {warnCount > 0 && (
          <span className="rounded-md px-2 py-0.5 font-semibold" style={{ background: '#FFFBEB', color: '#92400E' }}>
            {warnCount} warning
          </span>
        )}
        <span className="ml-auto italic" style={{ color: '#AAAAAA' }}>
          Version shown is the rule version applied at check time
        </span>
      </div>
      {Array.from(byReq.entries()).map(([req, { checks }]) => (
        <div key={req} className="rounded-xl overflow-hidden" style={{ border: `1px solid ${BDR}` }}>
          <div className="px-4 py-2.5" style={{ borderBottom: `1px solid ${BDR}`, background: SURF }}>
            <div className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: MUT }}>
              {req.replace(/_/g, ' ')}
            </div>
          </div>
          <ul>
            {checks.map((check) => {
              const style = RULE_STATE_STYLE[check.state] ?? RULE_STATE_STYLE['pending']
              return (
                <li key={check.id} className="flex items-start gap-4 px-4 py-3.5"
                  style={{ borderBottom: `1px solid ${BDR}` }}>
                  <span
                    className="shrink-0 mt-0.5 rounded-md px-2 py-0.5 text-[10px] font-semibold"
                    style={{ background: style.bg, color: style.text }}
                  >
                    {style.label}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium" style={{ color: INK }}>
                      {check.ruleTitle ?? check.ruleCode ?? check.ruleId}
                    </div>
                    {check.message && (
                      <div className="text-[12px] mt-0.5" style={{ color: INK2 }}>{check.message}</div>
                    )}
                    <div className="text-[11px] mt-1 flex flex-wrap gap-3" style={{ color: '#AAAAAA' }}>
                      {check.ruleVersion && <span>Rule v{check.ruleVersion}</span>}
                      {check.configVersion && <span>Config v{check.configVersion}</span>}
                      {check.severity && <span>Severity: {check.severity}</span>}
                      {check.isCurrent === false && (
                        <span className="font-medium" style={{ color: '#B45309' }}>Superseded</span>
                      )}
                    </div>
                  </div>
                </li>
              )
            })}
          </ul>
        </div>
      ))}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────
function EmptyCard({ icon, message }: { icon: React.ReactNode; message: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl px-6 py-12 text-center"
      style={{ background: SURF }}>
      <div className="mb-2 opacity-40">{icon}</div>
      <p className="text-sm max-w-[260px]" style={{ color: MUT }}>{message}</p>
    </div>
  )
}

function SummaryRow({ label, value, tone }: { label: string; value: number; tone: 'ok' | 'warn' }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[11px]" style={{ color: MUT }}>{label}</span>
      <span
        className="text-[11px] font-semibold"
        style={{ color: tone === 'warn' && value > 0 ? '#991B1B' : INK2 }}
      >
        {value}
      </span>
    </div>
  )
}

function DocStatusIcon({ doc }: { doc: ApplicationDetail['documents'][number] }) {
  const status = doc.status
  if (status === 'pass' || status === 'valid') {
    return <CheckCircle2 size={13} className="mt-0.5 shrink-0" style={{ color: '#2E7D52' }} />
  }
  if (status === 'failed' || status === 'invalid' || status === 'unreadable') {
    return <AlertTriangle size={13} className="mt-0.5 shrink-0" style={{ color: '#B91C1C' }} />
  }
  return <FileText size={13} className="mt-0.5 shrink-0" style={{ color: MUT }} />
}
