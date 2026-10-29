import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { EmptyState } from '@/components/ui/EmptyState'
import { Input, Label } from '@/components/ui/Input'
import { SearchableSelect } from '@/components/ui/SearchableSelect'
import { withServerCheck, failingActions, type CheckLine } from '@/lib/intakeChecks'
import { Loading, Notice } from '@/components/ui/Notice'
import { DocumentUploadControl } from '@/components/applicant/DocumentUploadControl'
import { InfoFieldInput, missingRequired } from '@/components/applicant/InfoFieldInput'
import { useRole } from '@/app/RoleContext'
import { useUploadPolicy } from '@/hooks/useUploadPolicy'
import { api, ApiError } from '@/services/api'
import { validateApplicationForm } from '@/lib/applicationForm'
import { DECLARATION_FALLBACK, uploadErrorMessage } from '@/lib/applicantLifecycle'
import { formatBytes } from '@/lib/fileValidation'
import { formatDateTime } from '@/lib/format'
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Info,
  Loader2,
  XCircle,
} from 'lucide-react'
import type {
  ApplicantApplication,
  ApplicantCategoryOption,
  ApplicantRequirement,
  Discrepancy,
  PublicCategoryConfig,
  PublicInfoField,
  Readiness,
} from '@/types'

type Step = 1 | 2 | 3
type SaveState = 'idle' | 'saving' | 'saved' | 'error' | 'creating'
type RowPhase = 'idle' | 'validating' | 'uploading'

// ─── Design tokens (premium SaaS palette, matching the spec) ────────────────
const OX = '#7A3E3E'   // muted oxblood — blockers, fails
const BRZ = '#8A6D3B'  // muted bronze — warnings
const TL = '#4A6670'   // slate-teal — processing
const PASS = '#2E5040' // muted green — success
const BDR = '#E0E0E0'  // border
const MUT = '#888888'  // muted ink
const INK = '#111111'  // primary ink

// ─── Helpers (unchanged from original) ──────────────────────────────────────
function documentBlockerMessages(
  application: ApplicantApplication | null,
  lines: Record<string, CheckLine[]>,
): string[] {
  if (!application) return []
  const missing = application.requirements.filter((r) => r.mandatory && !r.document)
  const missingLine =
    missing.length > 0
      ? [`Upload every required document before submitting. Still needed: ${missing.map((r) => r.name).join(', ')}.`]
      : []
  const fileLines = application.requirements.flatMap((r) => {
    if (!r.document && !lines[r.code]) return []
    return failingActions(withServerCheck(lines[r.code] ?? [], r.document?.documentCheck)).map(
      (action) => `${r.name}: ${action}`,
    )
  })
  return [...missingLine, ...fileLines]
}

function valuesFrom(fields: PublicInfoField[]): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const f of fields)
    if (f.value !== undefined && f.value !== null && f.value !== '') out[f.key] = f.value
  return out
}

// ─── Step Indicator ──────────────────────────────────────────────────────────
function StepIndicator({ step, onGo }: { step: Step; onGo: (s: Step) => void }) {
  const steps: { n: Step; label: string }[] = [
    { n: 1, label: 'Purpose' },
    { n: 2, label: 'Documents' },
    { n: 3, label: 'Review' },
  ]
  return (
    <div className="flex items-center">
      {steps.map((s, i) => {
        const done = step > s.n
        const active = step === s.n
        return (
          <div key={s.n} className="flex items-center">
            <button
              type="button"
              onClick={() => onGo(s.n)}
              className="flex items-center gap-2.5"
              aria-current={active ? 'step' : undefined}
            >
              <span
                className="flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full text-[11px] font-semibold transition-colors"
                style={{
                  background: done || active ? INK : '#EBEBEB',
                  color: done || active ? '#FFFFFF' : MUT,
                }}
              >
                {done ? '✓' : s.n}
              </span>
              <span
                className="text-[13px] transition-colors"
                style={{
                  color: active ? INK : done ? '#555555' : MUT,
                  fontWeight: active ? 600 : 400,
                }}
              >
                {s.label}
              </span>
            </button>
            {i < steps.length - 1 && (
              <div
                className="mx-4 h-px w-10 shrink-0 transition-colors"
                style={{ background: step > s.n ? '#AAAAAA' : BDR }}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}

// ─── Per-check icon ──────────────────────────────────────────────────────────
function CheckIcon({ status }: { status: 'pass' | 'fail' | 'pending' }) {
  if (status === 'pass') return <CheckCircle2 size={12} className="shrink-0" style={{ color: PASS }} />
  if (status === 'fail') return <XCircle size={12} className="shrink-0" style={{ color: OX }} />
  return <Loader2 size={12} className="shrink-0 animate-spin" style={{ color: TL }} />
}

const CHECK_LABELS: Record<string, string> = {
  integrity: 'File opens correctly',
  blur: 'Text is readable',
  blank: 'No blank pages',
  orientation: 'Orientation correct',
  content: 'Document contains content',
  type: 'Matches selected purpose',
}

// ─── Inline live-check list (shown inside the document row) ─────────────────
function LiveCheckList({ lines, phase }: { lines: CheckLine[]; phase: RowPhase }) {
  if (lines.length === 0 && phase === 'idle') return null
  const spinning = phase === 'validating' && lines.length === 0
  return (
    <ul className="mt-2.5 space-y-1.5">
      {spinning
        ? Object.keys(CHECK_LABELS).map((key) => (
            <li key={key} className="flex items-center gap-2">
              <Loader2 size={11} className="shrink-0 animate-spin" style={{ color: TL }} />
              <span className="text-[11px]" style={{ color: TL }}>
                {CHECK_LABELS[key]}
              </span>
            </li>
          ))
        : lines.map((row) => (
            <li key={row.key} className="flex items-start gap-2">
              <span className="mt-[1px] shrink-0">
                <CheckIcon status={row.status} />
              </span>
              <span>
                <span
                  className="text-[11px]"
                  style={{
                    color: row.status === 'fail' ? OX : row.status === 'pending' ? TL : '#555555',
                  }}
                >
                  {CHECK_LABELS[row.key] ?? row.key}
                </span>
                {row.action && (
                  <span className="block text-[10px] mt-0.5" style={{ color: row.status === 'fail' ? OX : BRZ }}>
                    {row.action}
                  </span>
                )}
              </span>
            </li>
          ))}
      {phase === 'uploading' && (
        <li className="flex items-center gap-2">
          <Loader2 size={11} className="shrink-0 animate-spin" style={{ color: TL }} />
          <span className="text-[11px]" style={{ color: TL }}>
            Uploading to server…
          </span>
        </li>
      )}
    </ul>
  )
}

// ─── Main wizard page ────────────────────────────────────────────────────────
/**
 * Three-step wizard: purpose and information → documents → review and submit.
 * Auto-saves a private draft. Changing category requires confirmation if files exist.
 */
export function NewApplicationPage() {
  const { role, user } = useRole()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const resumeId = params.get('id')
  const { filePolicy } = useUploadPolicy()

  const [step, setStep] = useState<Step>(1)
  const [categories, setCategories] = useState<ApplicantCategoryOption[] | null>(null)
  const [catError, setCatError] = useState<string | null>(null)
  const [config, setConfig] = useState<PublicCategoryConfig | null>(null)
  const [configError, setConfigError] = useState<string | null>(null)

  const [categoryCode, setCategoryCode] = useState('')
  const [institutionName, setInstitutionName] = useState(user.institutionName ?? '')
  const [program, setProgram] = useState('')
  const [year, setYear] = useState('2025-26')
  const [infoValues, setInfoValues] = useState<Record<string, unknown>>({})
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  const [app, setApp] = useState<ApplicantApplication | null>(null)
  const [readiness, setReadiness] = useState<Readiness | null>(null)
  const [conflicts, setConflicts] = useState<Discrepancy[]>([])
  const [limitationsOpen, setLimitationsOpen] = useState(false)
  const [saveState, setSaveState] = useState<SaveState>('idle')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [pendingCategory, setPendingCategory] = useState<string | null>(null)
  const [confirmed, setConfirmed] = useState<Record<number, boolean>>({})
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [intake, setIntake] = useState<Record<string, CheckLine[]>>({})
  const lastSaved = useRef<string>('')
  const inflight = useRef<Promise<void> | null>(null)

  const loadCategories = useCallback(() => {
    setCatError(null)
    api
      .listCategoryOptions(role)
      .then((rows) => setCategories(rows.filter((c) => c.available)))
      .catch((err) =>
        setCatError(err instanceof ApiError ? err.message : 'Categories could not be loaded.'),
      )
  }, [role])

  useEffect(loadCategories, [loadCategories])

  useEffect(() => {
    if (!resumeId) return
    api
      .getMyApplication(resumeId, role)
      .then((a) => {
        setApp(a)
        setCategoryCode(a.categoryCode)
        setInstitutionName(a.institutionName)
        setProgram(a.programName)
        setYear(a.academicYear)
        setInfoValues(valuesFrom(a.infoFields))
      })
      .catch(() => undefined)
  }, [resumeId, role])

  useEffect(() => {
    if (!categoryCode) {
      setConfig(null)
      return
    }
    setConfigError(null)
    api
      .getCategoryConfig(role, categoryCode)
      .then((c) => {
        setConfig(c)
        setInfoValues((prev) => {
          const next = { ...prev }
          for (const f of c.infoFields)
            if (next[f.key] === undefined && f.value != null) next[f.key] = f.value
          return next
        })
      })
      .catch((err) =>
        setConfigError(
          err instanceof ApiError
            ? err.message
            : "This category's configuration could not be loaded.",
        ),
      )
  }, [role, categoryCode])

  const payload = useMemo(
    () => ({
      category_code: categoryCode,
      institution_name: institutionName,
      program_name: program,
      academic_year: year,
      info_values: infoValues,
    }),
    [categoryCode, institutionName, program, year, infoValues],
  )
  const payloadKey = JSON.stringify(payload)

  const persist = useCallback(async () => {
    if (!categoryCode) return
    const { errors } = validateApplicationForm({ institutionName, program, year })
    if (Object.keys(errors).length) return
    if (inflight.current) {
      await inflight.current
      return
    }
    const run = (async () => {
      try {
        if (!app) {
          setSaveState('creating')
          const created = await api.createApplication(role, { ...payload, save_as_draft: true })
          setApp(created)
          lastSaved.current = payloadKey
          setSaveState('saved')
          navigate(`/applicant/applications/new?id=${created.id}`, { replace: true })
        } else if (payloadKey !== lastSaved.current) {
          setSaveState('saving')
          const updated = await api.updateDraft(role, app.id, payload)
          setApp(updated)
          lastSaved.current = payloadKey
          setSaveState('saved')
        }
        setSaveError(null)
      } catch (err) {
        setSaveState('error')
        setSaveError(
          err instanceof ApiError
            ? uploadErrorMessage(err.code, err.message)
            : 'The draft could not be saved. Check your connection.',
        )
      }
    })()
    inflight.current = run
    try {
      await run
    } finally {
      inflight.current = null
    }
  }, [app, categoryCode, payload, payloadKey, role, navigate, institutionName, program, year])

  useEffect(() => {
    if (step !== 1 || !categoryCode) return
    const t = window.setTimeout(() => void persist(), 800)
    return () => window.clearTimeout(t)
  }, [step, categoryCode, persist])

  async function loadReadiness(id: string) {
    try {
      setReadiness(await api.getReadiness(role, id))
    } catch {
      setReadiness(null)
    }
  }

  async function go(next: Step) {
    if (next > 1) {
      const form = validateApplicationForm({ institutionName, program, year })
      const info = missingRequired(config?.infoFields ?? app?.infoFields ?? [], infoValues)
      setFieldErrors({ ...form.errors, ...info })
      if (Object.keys(form.errors).length || Object.keys(info).length) {
        setStep(1)
        return
      }
      await persist()
    }
    if (next === 3) {
      if (documentBlockerMessages(app, intake).length > 0) {
        setStep(2)
        return
      }
      if (app) {
        await loadReadiness(app.id)
        // Load cross-document conflicts for the review step
        try {
          const items = await api.listReconciliationItems(role, app.id)
          setConflicts(items.filter((i) => i.outcome !== 'MATCH' && i.status !== 'cleared'))
        } catch {
          setConflicts([])
        }
      }
    }
    setStep(next)
  }

  function requestCategoryChange(code: string) {
    if (!app || code === categoryCode) {
      setCategoryCode(code)
      return
    }
    const uploaded = app.requirements.filter((r) => r.document).length
    if (uploaded > 0) setPendingCategory(code)
    else setCategoryCode(code)
  }

  async function confirmCategoryChange() {
    if (!pendingCategory) return
    setCategoryCode(pendingCategory)
    setPendingCategory(null)
  }

  async function submit() {
    if (!app) return
    setSubmitting(true)
    setSubmitError(null)
    try {
      const result = await api.submitApplication(role, app.id, true)
      navigate(`/applicant/applications/${app.id}`, {
        replace: true,
        state: { submitted: result.alreadySubmitted ? 'already' : 'ok' },
      })
    } catch (err) {
      setSubmitError(
        err instanceof ApiError ? err.message : 'The application could not be submitted.',
      )
      if (app) await loadReadiness(app.id)
    } finally {
      setSubmitting(false)
    }
  }

  const selected = categories?.find((c) => c.code === categoryCode)
  const documentBlockers = useMemo(() => documentBlockerMessages(app, intake), [app, intake])
  const infoFields = config?.infoFields ?? app?.infoFields ?? []
  const declarations = readiness?.declarations?.length ? readiness.declarations : DECLARATION_FALLBACK
  const allDeclared = declarations.every((_, i) => confirmed[i])
  const saveLabel =
    saveState === 'saving' || saveState === 'creating'
      ? 'Saving draft…'
      : saveState === 'saved'
        ? 'Draft saved'
        : saveState === 'error'
          ? 'Draft not saved'
          : 'Not saved yet'

  return (
    <AppShell
      title={app ? `Continue ${app.applicationNumber}` : 'Create Application'}
      description="Three steps: purpose, documents, then review. The draft is private until you submit."
      breadcrumbs={['Applicant', 'Create Application']}
    >
      <div className="space-y-4" style={{ maxWidth: '900px' }}>
        {/* ── Step tracker bar ── */}
        <div
          className="flex items-center justify-between rounded-xl px-5 py-3"
          style={{ background: '#FFFFFF', border: `1px solid ${BDR}` }}
        >
          <StepIndicator step={step} onGo={(s) => void go(s)} />
          <p
            className="text-[11px]"
            aria-live="polite"
            style={{ color: saveState === 'error' ? OX : MUT }}
          >
            {saveLabel}
            {saveError ? ` — ${saveError}` : ''}
          </p>
        </div>

        {/* ── Step 1: Purpose ── */}
        {step === 1 && (
          <div
            className="rounded-xl overflow-hidden"
            style={{ background: '#FFFFFF', border: `1px solid ${BDR}` }}
          >
            <div className="px-6 py-5" style={{ borderBottom: `1px solid ${BDR}` }}>
              <h2 className="text-sm font-semibold" style={{ color: INK }}>
                Purpose and institution
              </h2>
              <p className="mt-1 text-xs" style={{ color: MUT }}>
                Choose what this application is for, then fill in the institution details.
              </p>
            </div>

            <div className="px-6 py-5">
              {catError && (
                <Notice tone="error" className="mb-4" title="Categories unavailable" onRetry={loadCategories}>
                  {catError}
                </Notice>
              )}
              {categories === null && !catError && <Loading label="Loading categories" />}
              {categories?.length === 0 && (
                <EmptyState
                  title="No application categories are open"
                  description="Nothing is published for institutions right now. Try again later."
                />
              )}

              <div className="grid gap-8 lg:grid-cols-2">
                {/* Left: purpose dropdown */}
                <div>
                  {categories && categories.length > 0 && (
                    <>
                      <SearchableSelect
                        id="application-purpose"
                        label="Application purpose"
                        placeholder="Search application purposes"
                        options={categories.map((c) => ({
                          value: c.code,
                          label: c.name,
                          hint: `${c.mandatoryCount} required document${c.mandatoryCount === 1 ? '' : 's'}${
                            c.optionalCount > 0 ? ` · ${c.optionalCount} optional` : ''
                          }`,
                        }))}
                        value={categoryCode}
                        onChange={requestCategoryChange}
                      />
                      <p className="mt-2 text-[11px]" style={{ color: MUT }}>
                        Selecting a purpose automatically loads the document checklist configured
                        by AICTE for that category.
                      </p>
                      {selected && (
                        <p className="mt-1.5 text-[11px]" style={{ color: '#555555' }}>
                          {selected.description ? `${selected.description} · ` : ''}
                          {`${selected.mandatoryCount} required`}
                          {selected.optionalCount > 0 ? ` · ${selected.optionalCount} optional` : ''}
                          {selected.configVersion != null ? ` · config v${selected.configVersion}` : ''}
                        </p>
                      )}
                    </>
                  )}
                  {configError && (
                    <Notice tone="error" className="mt-3" title="This category cannot be used">
                      {configError}
                    </Notice>
                  )}
                </div>

                {/* Right: institution details */}
                <div className="grid gap-4">
                  <div>
                    <Label htmlFor="institutionName">Institution name</Label>
                    <Input
                      id="institutionName"
                      value={institutionName}
                      onChange={(e) => setInstitutionName(e.target.value)}
                      aria-invalid={Boolean(fieldErrors.institutionName)}
                    />
                    {fieldErrors.institutionName && (
                      <p className="mt-1 text-[11px]" style={{ color: OX }}>
                        {fieldErrors.institutionName}
                      </p>
                    )}
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <Label htmlFor="program">Programme</Label>
                      <Input
                        id="program"
                        value={program}
                        onChange={(e) => setProgram(e.target.value)}
                      />
                      {fieldErrors.program && (
                        <p className="mt-1 text-[11px]" style={{ color: OX }}>
                          {fieldErrors.program}
                        </p>
                      )}
                    </div>
                    <div>
                      <Label htmlFor="year">Academic year</Label>
                      <Input
                        id="year"
                        value={year}
                        onChange={(e) => setYear(e.target.value)}
                        placeholder="2025-26"
                      />
                      {fieldErrors.year && (
                        <p className="mt-1 text-[11px]" style={{ color: OX }}>
                          {fieldErrors.year}
                        </p>
                      )}
                    </div>
                  </div>
                  {infoFields.map((f) => (
                    <InfoFieldInput
                      key={f.key}
                      field={f}
                      value={infoValues[f.key]}
                      error={fieldErrors[f.key] ?? app?.infoProblems?.[f.key]}
                      onChange={(v) => setInfoValues((cur) => ({ ...cur, [f.key]: v }))}
                    />
                  ))}
                </div>
              </div>
            </div>

            {/* Action bar */}
            <div
              className="flex justify-end px-6 py-3"
              style={{ borderTop: `1px solid ${BDR}` }}
            >
              <Button
                onClick={() => void go(2)}
                disabled={!categoryCode || Boolean(configError)}
              >
                Continue to documents
              </Button>
            </div>
          </div>
        )}

        {/* ── Step 2: Documents ── */}
        {step === 2 && app && (
          <DocumentsStep
            app={app}
            config={config}
            filePolicy={filePolicy}
            intake={intake}
            blocked={documentBlockers.length > 0}
            onBack={() => setStep(1)}
            onNext={() => void go(3)}
            onChecked={(code, lines) => setIntake((cur) => ({ ...cur, [code]: lines }))}
            onChanged={async () => {
              const fresh = await api.getMyApplication(app.id, role)
              setApp(fresh)
            }}
          />
        )}
        {step === 2 && !app && (
          <div
            className="rounded-xl px-6 py-8"
            style={{ background: '#FFFFFF', border: `1px solid ${BDR}` }}
          >
            <p className="text-sm" style={{ color: MUT }}>
              Saving draft so documents can be attached…
            </p>
            <Button className="mt-3" variant="outline" onClick={() => void persist()}>
              Save draft and continue
            </Button>
          </div>
        )}

        {/* ── Step 3: Review ── */}
        {step === 3 && (
          <div
            className="rounded-xl overflow-hidden"
            style={{ background: '#FFFFFF', border: `1px solid ${BDR}` }}
          >
            <div className="px-6 py-5" style={{ borderBottom: `1px solid ${BDR}` }}>
              <h2 className="text-sm font-semibold" style={{ color: INK }}>
                Review and submit
              </h2>
              <p className="mt-1 text-xs" style={{ color: MUT }}>
                Nothing is sent until you confirm the declarations. Submitting twice does not
                create a second application.
              </p>
            </div>

            <div className="px-6 py-5 space-y-6">
              {/* Summary cards */}
              <section className="space-y-2">
                {[
                  {
                    label: 'Purpose',
                    primary: selected?.name ?? app?.category,
                    secondary: `${institutionName} · ${program} · ${year}`,
                    onEdit: () => setStep(1),
                  },
                  {
                    label: 'Documents',
                    primary: app
                      ? `${app.requiredUploaded} of ${app.requiredTotal} required documents uploaded`
                      : 'Not saved yet',
                    secondary: undefined,
                    onEdit: () => setStep(2),
                  },
                ].map((row) => (
                  <div
                    key={row.label}
                    className="flex items-start justify-between gap-3 rounded-lg px-4 py-3"
                    style={{ background: '#FAFAFA', border: `1px solid ${BDR}` }}
                  >
                    <div>
                      <p
                        className="text-[10px] font-semibold uppercase tracking-widest"
                        style={{ color: MUT }}
                      >
                        {row.label}
                      </p>
                      <p className="mt-1 text-sm font-medium" style={{ color: INK }}>
                        {row.primary}
                      </p>
                      {row.secondary && (
                        <p className="text-xs" style={{ color: '#555555' }}>
                          {row.secondary}
                        </p>
                      )}
                    </div>
                    <Button size="sm" variant="ghost" onClick={row.onEdit}>
                      Edit
                    </Button>
                  </div>
                ))}
              </section>

              {/* Cross-document conflict cards */}
              {conflicts.length > 0 && (
                <section>
                  <h3 className="text-sm font-semibold mb-1" style={{ color: INK }}>
                    Cross-document discrepancies ({conflicts.length})
                  </h3>
                  <p className="text-xs mb-3" style={{ color: MUT }}>
                    The following information appears inconsistent across uploaded documents.
                    Review before submitting.
                  </p>
                  <div className="space-y-3">
                    {conflicts.map((item) => (
                      <div
                        key={item.id}
                        className="rounded-lg overflow-hidden"
                        style={{
                          border: `1px solid ${BDR}`,
                          borderLeft: `3px solid ${BRZ}`,
                        }}
                      >
                        {/* Conflict header */}
                        <div
                          className="flex items-center gap-2 px-4 py-2.5"
                          style={{
                            background: '#FAFAFA',
                            borderBottom: `1px solid ${BDR}`,
                          }}
                        >
                          <AlertTriangle size={12} style={{ color: BRZ, flexShrink: 0 }} />
                          <span className="text-xs font-semibold" style={{ color: INK }}>
                            {item.title ?? item.fieldName.replace(/_/g, ' ')}
                          </span>
                          <span
                            className="ml-auto text-[10px] uppercase tracking-widest"
                            style={{ color: MUT }}
                          >
                            {item.outcome.replace(/_/g, ' ')}
                          </span>
                        </div>

                        {/* Side-by-side values */}
                        {item.values.length >= 2 && (
                          <div
                            className="grid grid-cols-2 divide-x"
                            style={{ borderColor: BDR }}
                          >
                            {item.values.slice(0, 2).map((v, vi) => (
                              <div key={vi} className="px-4 py-3">
                                <p
                                  className="text-[10px] font-medium uppercase tracking-widest mb-1.5"
                                  style={{ color: MUT }}
                                >
                                  {v.documentName}
                                  {v.pageNumber != null ? ` · p${v.pageNumber}` : ''}
                                </p>
                                <p
                                  className="text-xs"
                                  style={{
                                    fontFamily: 'monospace',
                                    color: INK,
                                    background: '#F5F5F5',
                                    padding: '4px 8px',
                                    borderRadius: '4px',
                                  }}
                                >
                                  {v.normalizedValue ?? v.value ?? '—'}
                                </p>
                                {v.evidenceSnippet && (
                                  <p
                                    className="text-[10px] mt-1 italic"
                                    style={{ color: MUT }}
                                  >
                                    "{v.evidenceSnippet}"
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Description + disclaimer */}
                        <div className="px-4 pb-3 pt-1">
                          {item.description && (
                            <p className="text-[11px] mb-1" style={{ color: '#555555' }}>
                              {item.description}
                            </p>
                          )}
                          <p className="text-[10px] italic" style={{ color: '#AAAAAA' }}>
                            Automated text comparison — does not indicate fraud or confirm
                            document authenticity.
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* Readiness panel */}
              {readiness && (
                <section className="space-y-3">
                  {/* Blockers */}
                  {readiness.mustFix.length > 0 ? (
                    <div
                      className="rounded-lg overflow-hidden"
                      style={{ border: `1px solid ${BDR}`, borderLeft: `3px solid ${OX}` }}
                    >
                      <div
                        className="px-4 py-2.5"
                        style={{ background: '#FAFAFA', borderBottom: `1px solid ${BDR}` }}
                      >
                        <p className="text-xs font-semibold" style={{ color: OX }}>
                          Required before submission
                        </p>
                      </div>
                      <ul className="divide-y px-4" style={{ borderColor: BDR }}>
                        {readiness.mustFix.map((item) => (
                          <li
                            key={`${item.code}:${item.requirementCode ?? item.title}`}
                            className="py-2.5"
                          >
                            <p className="text-xs font-medium" style={{ color: INK }}>
                              {item.title}
                            </p>
                            {item.detail && (
                              <p className="text-[11px] mt-0.5" style={{ color: MUT }}>
                                {item.detail}
                              </p>
                            )}
                            {item.requirementCode && (
                              <button
                                type="button"
                                onClick={() => setStep(2)}
                                className="mt-1 text-[11px] underline"
                                style={{ color: OX }}
                              >
                                Go to documents →
                              </button>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <CheckCircle2 size={13} style={{ color: PASS }} />
                      <span className="text-xs" style={{ color: '#555555' }}>
                        Nothing blocks submission
                      </span>
                    </div>
                  )}

                  {/* Warnings */}
                  {readiness.reviewRecommended.length > 0 && (
                    <div
                      className="rounded-lg overflow-hidden"
                      style={{ border: `1px solid ${BDR}`, borderLeft: `3px solid ${BRZ}` }}
                    >
                      <div
                        className="px-4 py-2.5"
                        style={{ background: '#FAFAFA', borderBottom: `1px solid ${BDR}` }}
                      >
                        <p className="text-xs font-semibold" style={{ color: BRZ }}>
                          Couldn't fully verify
                        </p>
                        <p className="text-[11px] mt-0.5" style={{ color: MUT }}>
                          Passed format checks but could not be confirmed by automated systems.
                        </p>
                      </div>
                      <ul className="divide-y px-4" style={{ borderColor: BDR }}>
                        {readiness.reviewRecommended.map((item) => (
                          <li key={`${item.code}:${item.title}`} className="py-2.5">
                            <p className="text-xs font-medium" style={{ color: INK }}>
                              {item.title}
                            </p>
                            {item.detail && (
                              <p className="text-[11px] mt-0.5 italic" style={{ color: MUT }}>
                                {item.detail}
                              </p>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Limitations — small collapsible */}
                  {readiness.limitations.length > 0 && (
                    <div>
                      <button
                        type="button"
                        onClick={() => setLimitationsOpen((o) => !o)}
                        className="flex items-center gap-1.5 text-[11px]"
                        style={{ color: MUT }}
                      >
                        <Info size={11} />
                        About these automated checks
                        {limitationsOpen ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                      </button>
                      {limitationsOpen && (
                        <div
                          className="mt-2 rounded-lg px-4 py-3"
                          style={{ background: '#FAFAFA', border: `1px solid ${BDR}` }}
                        >
                          <p className="text-[11px]" style={{ color: MUT }}>
                            {readiness.limitations.join(' ')}
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </section>
              )}

              {/* Document blockers (fallback, should not appear if go() guards correctly) */}
              {documentBlockers.length > 0 && (
                <Notice tone="warning" title="These must be fixed before you can submit">
                  <ul className="mt-1 space-y-1">
                    {documentBlockers.map((b) => (
                      <li key={b}>{b}</li>
                    ))}
                  </ul>
                </Notice>
              )}

              {/* Declarations */}
              <fieldset className="space-y-3">
                <legend className="text-xs font-semibold" style={{ color: INK }}>
                  Declarations
                </legend>
                {declarations.map((d, i) => (
                  <label
                    key={d}
                    className="flex cursor-pointer items-start gap-3"
                    style={{ minHeight: '22px' }}
                  >
                    <input
                      type="checkbox"
                      className="mt-0.5 shrink-0"
                      style={{ width: 15, height: 15 }}
                      checked={Boolean(confirmed[i])}
                      onChange={(e) => setConfirmed((c) => ({ ...c, [i]: e.target.checked }))}
                    />
                    <span className="text-sm" style={{ color: '#333333' }}>
                      {d}
                    </span>
                  </label>
                ))}
              </fieldset>

              {submitError && (
                <Notice tone="error" title="Could not submit">
                  {submitError}
                </Notice>
              )}
            </div>

            {/* Action bar */}
            <div
              className="flex justify-between px-6 py-3"
              style={{ borderTop: `1px solid ${BDR}` }}
            >
              <Button variant="outline" onClick={() => setStep(2)}>
                Back
              </Button>
              <Button
                onClick={() => void submit()}
                disabled={
                  submitting ||
                  !app ||
                  !readiness?.canSubmit ||
                  !allDeclared ||
                  documentBlockers.length > 0
                }
              >
                {submitting ? 'Submitting…' : 'Submit application'}
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Category-change confirmation dialog */}
      <Dialog
        open={pendingCategory !== null}
        onClose={() => setPendingCategory(null)}
        title="Change application purpose?"
        width="max-w-lg"
        footer={
          <>
            <Button variant="outline" onClick={() => setPendingCategory(null)}>
              Keep current purpose
            </Button>
            <Button onClick={() => void confirmCategoryChange()}>Change purpose</Button>
          </>
        }
      >
        <p className="text-sm" style={{ color: '#555555' }}>
          Files you have already uploaded are kept. They may no longer match the new checklist,
          and you may need to upload additional documents. Nothing is deleted.
        </p>
      </Dialog>
    </AppShell>
  )
}

// ─── Documents step (live upload rows) ──────────────────────────────────────
function DocumentsStep({
  app,
  config,
  filePolicy,
  intake,
  blocked,
  onBack,
  onNext,
  onChecked,
  onChanged,
}: {
  app: ApplicantApplication
  config: PublicCategoryConfig | null
  filePolicy: Parameters<typeof DocumentUploadControl>[0]['policy']
  intake: Record<string, CheckLine[]>
  blocked: boolean
  onBack: () => void
  onNext: () => void
  onChecked: (code: string, lines: CheckLine[]) => void
  onChanged: () => Promise<void>
}) {
  // Per-row upload phase — concurrent uploads are inherently supported
  // because each row tracks its own RowPhase independently.
  const [rowPhases, setRowPhases] = useState<Record<string, RowPhase>>({})

  const guidance = (req: ApplicantRequirement) =>
    config?.requirements.find((r) => r.code === req.code)

  const mandatoryCount = app.requirements.filter((r) => r.mandatory).length
  const uploadedMandatory = app.requirements.filter((r) => r.mandatory && r.document).length
  const progress =
    mandatoryCount > 0 ? Math.round((uploadedMandatory / mandatoryCount) * 100) : 0

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{ background: '#FFFFFF', border: `1px solid ${BDR}` }}
    >
      {/* Header + progress */}
      <div className="px-6 py-4" style={{ borderBottom: `1px solid ${BDR}` }}>
        <div className="flex items-center justify-between mb-2.5">
          <h2 className="text-sm font-semibold" style={{ color: INK }}>
            Documents
          </h2>
          <span className="text-[11px]" style={{ color: MUT }}>
            {uploadedMandatory} of {mandatoryCount} required uploaded
          </span>
        </div>
        <div className="h-[3px] rounded-full overflow-hidden" style={{ background: '#F0F0F0' }}>
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${progress}%`,
              background:
                uploadedMandatory === mandatoryCount && mandatoryCount > 0 ? PASS : INK,
            }}
          />
        </div>
      </div>

      {/* Document rows */}
      <ul className="divide-y" style={{ borderColor: BDR }}>
        {app.requirements.map((req) => {
          const g = guidance(req)
          const doc = req.document
          const rowPhase = rowPhases[req.code] ?? 'idle'
          const isProcessing = rowPhase !== 'idle'
          const checks = withServerCheck(intake[req.code] ?? [], doc?.documentCheck)
          const hasChecks =
            (intake[req.code]?.length ?? 0) > 0 || doc?.documentCheck != null
          const hasFail = hasChecks && checks.some((c) => c.status === 'fail')
          const allPass =
            hasChecks && checks.length > 0 && checks.every((c) => c.status === 'pass')

          const policy = (() => {
            const mb = g?.maxSizeMb ?? req.maxSizeMb ?? filePolicy?.maxUploadMb ?? 5
            const types =
              (g?.allowedTypes ?? req.allowedTypes).length > 0
                ? (g?.allowedTypes ?? req.allowedTypes)
                : filePolicy?.allowedExtensions ?? ['pdf']
            return {
              allowedExtensions: types,
              maxUploadMb: mb,
              maxUploadBytes: mb * 1024 * 1024,
            }
          })()

          const rowAccent = isProcessing
            ? TL
            : hasFail
              ? OX
              : allPass
                ? PASS
                : 'transparent'

          return (
            <li
              key={req.code}
              className="px-6 py-4 transition-colors"
              style={{
                borderLeft: `3px solid ${rowAccent}`,
                background: hasFail
                  ? `${OX}05`
                  : allPass
                    ? `${PASS}05`
                    : isProcessing
                      ? `${TL}04`
                      : '#FFFFFF',
              }}
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                {/* Left: doc info + live checks */}
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold leading-snug" style={{ color: INK }}>
                    {req.name}
                    {req.mandatory && (
                      <span
                        className="ml-1 text-xs"
                        style={{ color: OX }}
                        aria-label="required"
                        title="Mandatory document"
                      >
                        *
                      </span>
                    )}
                  </p>
                  {(g?.description || req.description) && (
                    <p className="mt-0.5 text-xs" style={{ color: MUT }}>
                      {g?.description || req.description}
                    </p>
                  )}
                  <p
                    className="mt-0.5 text-[10px]"
                    style={{ color: '#BBBBBB', fontFamily: 'monospace' }}
                  >
                    {(g?.allowedTypes ?? req.allowedTypes).map((t) => t.toUpperCase()).join(', ')}
                    {(g?.maxSizeMb ?? req.maxSizeMb) != null
                      ? ` · max ${g?.maxSizeMb ?? req.maxSizeMb} MB`
                      : ''}
                  </p>
                  {doc && (
                    <p
                      className="mt-1 text-[11px]"
                      style={{ color: MUT, fontFamily: 'monospace' }}
                    >
                      {doc.fileName} · {formatBytes(doc.sizeBytes)}
                      {doc.version > 1 ? ` · v${doc.version}` : ''} ·{' '}
                      {formatDateTime(doc.uploadedAt)}
                    </p>
                  )}

                  {/* Live check list */}
                  {(isProcessing || hasChecks) && (
                    <LiveCheckList
                      lines={isProcessing && checks.length === 0 ? [] : checks}
                      phase={rowPhase}
                    />
                  )}
                </div>

                {/* Right: status badge + upload button */}
                <div className="flex flex-col items-end gap-2 shrink-0">
                  {/* Status badge */}
                  {isProcessing ? (
                    <span
                      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium"
                      style={{
                        background: `${TL}12`,
                        color: TL,
                        border: `1px solid ${TL}40`,
                      }}
                    >
                      <Loader2 size={10} className="animate-spin" />
                      {rowPhase === 'uploading' ? 'Uploading…' : 'Checking…'}
                    </span>
                  ) : allPass ? (
                    <span
                      className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium"
                      style={{
                        background: `${PASS}12`,
                        color: PASS,
                        border: `1px solid ${PASS}40`,
                      }}
                    >
                      <CheckCircle2 size={10} />
                      Ready for review
                    </span>
                  ) : hasFail ? (
                    <span
                      className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium"
                      style={{
                        background: `${OX}10`,
                        color: OX,
                        border: `1px solid ${OX}40`,
                      }}
                    >
                      <AlertTriangle size={10} />
                      Action required
                    </span>
                  ) : (
                    <span
                      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px]"
                      style={{
                        background: '#F5F5F5',
                        color: MUT,
                        border: `1px solid ${BDR}`,
                      }}
                    >
                      {doc ? req.uploadStatusLabel : 'Not uploaded'}
                    </span>
                  )}

                  {/* Upload control — always mounted for concurrent uploads */}
                  {app.canUpload && (
                    <DocumentUploadControl
                      applicationId={app.id}
                      requirementCode={req.code}
                      requirementName={req.name}
                      hasDocument={Boolean(doc)}
                      policy={policy}
                      compact
                      onPhaseChange={(phase) =>
                        setRowPhases((cur) => ({ ...cur, [req.code]: phase }))
                      }
                      onChecked={(lines) => onChecked(req.code, lines)}
                      onUploaded={onChanged}
                    />
                  )}
                </div>
              </div>
            </li>
          )
        })}
      </ul>

      {/* Action bar */}
      <div
        className="flex justify-between px-6 py-3"
        style={{ borderTop: `1px solid ${BDR}` }}
      >
        <Button variant="outline" onClick={onBack}>
          Back
        </Button>
        <Button onClick={onNext} disabled={blocked}>
          {blocked ? 'Upload required documents to continue' : 'Continue to review'}
        </Button>
      </div>
    </div>
  )
}
