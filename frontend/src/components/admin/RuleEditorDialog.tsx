import { useEffect, useMemo, useState } from 'react'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Input, Label, Textarea } from '@/components/ui/Input'
import { Notice } from '@/components/ui/Notice'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import { RULE_TYPE_LABEL, SEVERITY_LABEL } from '@/lib/configLabels'
import type {
  ConfigRequirement,
  ConfigRule,
  RuleDefinitionSchema,
  RuleDryRunResult,
  RuleExplanation,
  RuleSuggestion,
  RuleValidationReport,
} from '@/types'

type Mode = 'plain' | 'json'

function pretty(value: unknown): string {
  return value ? JSON.stringify(value, null, 2) : ''
}

function Explanation({ e }: { e: RuleExplanation }) {
  return (
    <dl className="space-y-1.5 text-xs">
      <div>
        <dt className="font-semibold text-ink">What is checked</dt>
        <dd className="text-ink-secondary">{e.condition}</dd>
      </div>
      <div>
        <dt className="font-semibold text-ink">If it passes</dt>
        <dd className="text-ink-secondary">{e.onPass}</dd>
      </div>
      <div>
        <dt className="font-semibold text-ink">If it does not pass</dt>
        <dd className="text-ink-secondary">{e.onFail}</dd>
      </div>
      <div>
        <dt className="font-semibold text-ink">If it cannot be evaluated</dt>
        <dd className="text-ink-secondary">{e.onUnable}</dd>
      </div>
    </dl>
  )
}

/**
 * Authoring dialog for one rule on one document requirement. The saved JSON definition is the
 * only thing the engine executes; plain language can only propose that definition, and the
 * administrator has to confirm the interpretation before activation.
 */
export function RuleEditorDialog({
  open,
  onClose,
  categoryName,
  requirement,
  rule,
  onSaved,
}: {
  open: boolean
  onClose: () => void
  categoryName: string
  requirement: ConfigRequirement
  /** When set, edits that rule's draft version instead of creating a new rule. */
  rule?: ConfigRule | null
  onSaved: () => void
}) {
  const { role } = useRole()
  const draft = useMemo(() => rule?.versions?.find((v) => v.status === 'draft') ?? null, [rule])

  const [mode, setMode] = useState<Mode>('json')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [sourceReference, setSourceReference] = useState('')
  const [notes, setNotes] = useState('')
  const [plainText, setPlainText] = useState('')
  const [jsonText, setJsonText] = useState('')
  const [suggestion, setSuggestion] = useState<RuleSuggestion | null>(null)
  const [interpretationConfirmed, setInterpretationConfirmed] = useState(false)
  const [report, setReport] = useState<RuleValidationReport | null>(null)
  const [schema, setSchema] = useState<RuleDefinitionSchema | null>(null)
  const [sampleText, setSampleText] = useState('{\n  "registration_number": "ABC12345"\n}')
  const [dryRun, setDryRun] = useState<RuleDryRunResult | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [savedNote, setSavedNote] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setError(null)
    setSavedNote(null)
    setReport(null)
    setSuggestion(null)
    setDryRun(null)
    setInterpretationConfirmed(false)
    setTitle(draft?.title ?? rule?.title ?? '')
    setDescription(draft?.description ?? rule?.description ?? '')
    setSourceReference(draft?.sourceReference ?? rule?.sourceReference ?? '')
    setNotes(draft?.notes ?? rule?.notes ?? '')
    setPlainText(draft?.naturalLanguage ?? '')
    setJsonText(pretty(draft?.definition))
    setMode(draft?.authoringMode ?? 'json')
  }, [open, rule, draft])

  useEffect(() => {
    if (open && !schema) {
      api
        .cfgDefinitionSchema(role)
        .then(setSchema)
        .catch(() => undefined)
    }
  }, [open, schema, role])

  const parsed = useMemo(() => {
    if (!jsonText.trim()) return { value: null as unknown, error: null as string | null }
    try {
      return { value: JSON.parse(jsonText) as unknown, error: null }
    } catch (err) {
      return { value: null, error: err instanceof Error ? err.message : 'Not valid JSON' }
    }
  }, [jsonText])

  const hasDefinition = parsed.value !== null && parsed.error === null
  const explanation = report?.explanation ?? suggestion?.explanation ?? null

  function message(err: unknown, fallback: string) {
    return err instanceof ApiError ? err.message : fallback
  }

  async function interpret() {
    setBusy('interpret')
    setError(null)
    setReport(null)
    setInterpretationConfirmed(false)
    try {
      const s = await api.cfgSuggestDefinition(role, plainText)
      setSuggestion(s)
      if (s.definition) setJsonText(pretty(s.definition))
      if (s.validation) setReport(s.validation)
    } catch (err) {
      setError(message(err, 'The text could not be interpreted.'))
    } finally {
      setBusy(null)
    }
  }

  async function validate() {
    setBusy('validate')
    setError(null)
    try {
      if (!hasDefinition) {
        setReport({
          valid: false,
          errors: [
            parsed.error
              ? `The definition is not valid JSON: ${parsed.error}`
              : 'There is no structured definition yet. ' +
                (mode === 'plain' ? 'Choose “Interpret text” first.' : 'Enter the JSON definition.'),
          ],
          warnings: [],
          unsupported: [],
          requiresSource: false,
          requiredInputs: [],
        })
        return
      }
      setReport(
        await api.cfgValidateDefinition(role, {
          definition: parsed.value,
          source_reference: sourceReference,
          requirement_id: requirement.id,
        }),
      )
    } catch (err) {
      setError(message(err, 'Validation could not run.'))
    } finally {
      setBusy(null)
    }
  }

  async function runDryRun() {
    setBusy('dry')
    setError(null)
    try {
      const sample = JSON.parse(sampleText || '{}') as Record<string, unknown>
      setDryRun(
        await api.cfgDryRun(role, requirement.id, {
          definition: parsed.value,
          source_reference: sourceReference,
          sample,
        }),
      )
    } catch (err) {
      setError(err instanceof SyntaxError ? 'The sample values are not valid JSON.' : message(err, 'Dry run failed.'))
    } finally {
      setBusy(null)
    }
  }

  function body() {
    return {
      title,
      description,
      definition: hasDefinition ? parsed.value : null,
      authoring_mode: mode,
      natural_language: mode === 'plain' ? plainText : '',
      source_reference: sourceReference,
      notes,
    }
  }

  async function save(): Promise<ConfigRule | null> {
    setBusy('save')
    setError(null)
    try {
      const saved = rule
        ? await api.cfgSaveRuleDraft(role, rule.id, body())
        : await api.cfgCreateRule(role, requirement.id, body())
      setSavedNote(`Draft saved as ${saved.code}.`)
      return saved
    } catch (err) {
      setError(message(err, 'The draft could not be saved.'))
      return null
    } finally {
      setBusy(null)
    }
  }

  async function saveDraft() {
    const saved = await save()
    if (saved) {
      onSaved()
      onClose()
    }
  }

  async function activate() {
    const saved = await save()
    if (!saved) return
    setBusy('activate')
    try {
      const version = saved.draftVersion ?? saved.latestVersion ?? 1
      await api.cfgActivateRule(role, saved.id, version, mode === 'plain' ? interpretationConfirmed : true)
      onSaved()
      onClose()
    } catch (err) {
      // The draft stays saved so nothing the administrator typed is lost.
      setError(message(err, 'The rule could not be activated.'))
      onSaved()
    } finally {
      setBusy(null)
    }
  }

  const canActivate =
    hasDefinition &&
    title.trim().length > 0 &&
    (mode !== 'plain' || interpretationConfirmed) &&
    (report?.valid ?? false)

  return (
    <Dialog
      open={open}
      onClose={onClose}
      dismissible={busy === null}
      width="max-w-3xl"
      title={rule ? `Edit Rule ${rule.code}` : 'Add Rule'}
      subtitle={
        <>
          Category: <strong className="text-ink">{categoryName}</strong> · Document:{' '}
          <strong className="text-ink">{requirement.name}</strong>
          {draft && <span className="ml-2">Editing draft version {draft.version}</span>}
        </>
      }
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy !== null}>
            Cancel
          </Button>
          <Button variant="outline" onClick={validate} disabled={busy !== null}>
            {busy === 'validate' ? 'Validating' : 'Validate'}
          </Button>
          <Button variant="outline" onClick={saveDraft} disabled={busy !== null || title.trim().length === 0}>
            {busy === 'save' ? 'Saving' : 'Save Draft'}
          </Button>
          <Button onClick={activate} disabled={busy !== null || !canActivate} title={canActivate ? undefined : 'Validate first'}>
            {busy === 'activate' ? 'Activating' : 'Activate'}
          </Button>
        </>
      }
    >
      <div className="space-y-5">
        <Notice tone="neutral">
          Activating marks this version as eligible. It reaches applicants when the category is published.
          Only published rules are ever run against applications.
        </Notice>

        <section className="grid gap-4 md:grid-cols-2">
          <div className="md:col-span-2">
            <Label htmlFor="rule-title">Rule title</Label>
            <Input id="rule-title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="md:col-span-2">
            <Label htmlFor="rule-desc">Description</Label>
            <Textarea id="rule-desc" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="md:col-span-2">
            <Label htmlFor="rule-source">Source reference</Label>
            <Input
              id="rule-source"
              value={sourceReference}
              onChange={(e) => setSourceReference(e.target.value)}
              placeholder="Citation you have verified, e.g. the clause of the applicable regulation"
            />
            <p className="mt-1 text-[11px] text-ink-muted">
              Required for checks that compare against a threshold. Nothing is filled in for you.
            </p>
          </div>
          <div className="md:col-span-2">
            <Label htmlFor="rule-notes">Internal notes</Label>
            <Textarea id="rule-notes" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
        </section>

        <section>
          <div role="tablist" aria-label="Authoring mode" className="mb-3 flex gap-1 border-b border-border">
            {(['plain', 'json'] as Mode[]).map((m) => (
              <button
                key={m}
                role="tab"
                aria-selected={mode === m}
                type="button"
                onClick={() => setMode(m)}
                className={`-mb-px border-b-2 px-3 py-2 text-sm ${
                  mode === m ? 'border-ink font-medium text-ink' : 'border-transparent text-ink-muted hover:text-ink'
                }`}
              >
                {m === 'plain' ? 'Plain Language' : 'JSON'}
              </button>
            ))}
          </div>

          {mode === 'plain' && (
            <div className="space-y-3">
              <div>
                <Label htmlFor="rule-plain">Describe the check in your own words</Label>
                <Textarea
                  id="rule-plain"
                  rows={3}
                  value={plainText}
                  onChange={(e) => setPlainText(e.target.value)}
                  placeholder="e.g. The registration number must be present and the certificate must not be expired."
                />
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <Button variant="outline" onClick={interpret} disabled={busy !== null || plainText.trim().length < 5}>
                  {busy === 'interpret' ? 'Interpreting' : 'Interpret text'}
                </Button>
                <p className="text-[11px] text-ink-muted">
                  This text is never run. It only proposes a structured definition, shown below for you to review.
                </p>
              </div>
              {suggestion && (
                <div className="space-y-2 rounded-[var(--radius-md)] border border-border bg-surface p-3 text-xs">
                  {suggestion.assumptions.length > 0 && (
                    <div>
                      <p className="font-semibold text-ink">Assumptions made</p>
                      <ul className="ml-4 list-disc text-ink-secondary">
                        {suggestion.assumptions.map((a) => (
                          <li key={a}>{a}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {suggestion.unsupported.length > 0 && (
                    <div>
                      <p className="font-semibold text-status-warning">Not understood or not supported</p>
                      <ul className="ml-4 list-disc text-ink-secondary">
                        {suggestion.unsupported.map((a) => (
                          <li key={a}>{a}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {!suggestion.definition && (
                    <p className="text-ink-secondary">
                      No structured check could be proposed. Switch to JSON to write the definition yourself.
                    </p>
                  )}
                </div>
              )}
              {hasDefinition && (
                <label className="flex items-start gap-2 text-xs text-ink-secondary">
                  <input
                    type="checkbox"
                    className="mt-0.5"
                    checked={interpretationConfirmed}
                    onChange={(e) => setInterpretationConfirmed(e.target.checked)}
                  />
                  <span>
                    I have reviewed the structured definition and the preview below, and it matches what I intend.
                  </span>
                </label>
              )}
            </div>
          )}

          {(mode === 'json' || hasDefinition) && (
            <div className="mt-3">
              <Label htmlFor="rule-json">Structured definition {mode === 'plain' && '(proposed, editable)'}</Label>
              <Textarea
                id="rule-json"
                rows={9}
                className="mono text-xs"
                spellCheck={false}
                value={jsonText}
                onChange={(e) => {
                  setJsonText(e.target.value)
                  setReport(null)
                  setInterpretationConfirmed(false)
                }}
                placeholder={pretty(schema?.example)}
              />
              {parsed.error && <p className="mt-1 text-xs text-status-failed">Not valid JSON: {parsed.error}</p>}
              {schema && (
                <details className="mt-2 text-xs text-ink-muted">
                  <summary className="cursor-pointer">Supported check types</summary>
                  <ul className="mt-1 space-y-0.5">
                    {schema.checkTypes.map((c) => (
                      <li key={c.type}>
                        <span className="mono text-ink">{c.type}</span>: {RULE_TYPE_LABEL[c.type] ?? c.label}
                        {c.needsSource && ' (needs a source reference)'}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          )}
        </section>

        {report && (
          <section aria-live="polite" className="space-y-2">
            <div className="flex items-center gap-2">
              <Badge tone={report.valid ? 'pass' : 'failed'}>{report.valid ? 'Valid' : 'Needs changes'}</Badge>
              {report.explanation && <span className="text-xs text-ink-muted">{report.explanation.summary}</span>}
            </div>
            {report.errors.length > 0 && (
              <Notice tone="error" title="Fix before activating">
                <ul className="ml-4 list-disc">
                  {report.errors.map((e) => (
                    <li key={e}>{e}</li>
                  ))}
                </ul>
              </Notice>
            )}
            {report.warnings.length > 0 && (
              <Notice tone="warning" title="Please note">
                <ul className="ml-4 list-disc">
                  {report.warnings.map((e) => (
                    <li key={e}>{e}</li>
                  ))}
                </ul>
              </Notice>
            )}
          </section>
        )}

        {explanation && (
          <section className="rounded-[var(--radius-md)] border border-border p-3">
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-muted">
              Preview: what applicants will see checked
            </h3>
            <Explanation e={explanation} />
            {explanation.severity && (
              <p className="mt-2 text-[11px] text-ink-muted">
                {SEVERITY_LABEL[explanation.severity] ?? explanation.severity}. A check that cannot be evaluated is
                never recorded as non-compliance.
              </p>
            )}
          </section>
        )}

        <details className="rounded-[var(--radius-md)] border border-border p-3 text-xs">
          <summary className="cursor-pointer font-medium text-ink">Optional dry run on sample values</summary>
          <div className="mt-3 space-y-2">
            <Label htmlFor="rule-sample">Sample extracted fields (JSON)</Label>
            <Textarea
              id="rule-sample"
              rows={4}
              className="mono text-xs"
              value={sampleText}
              onChange={(e) => setSampleText(e.target.value)}
            />
            <Button size="sm" variant="outline" onClick={runDryRun} disabled={busy !== null || !hasDefinition}>
              {busy === 'dry' ? 'Running' : 'Run on sample'}
            </Button>
            {dryRun && (
              <div className="rounded border border-border bg-surface p-2">
                {dryRun.result ? (
                  <>
                    <Badge tone={dryRun.result.state === 'passed' ? 'pass' : 'neutral'}>{dryRun.result.state}</Badge>
                    <p className="mt-1 text-ink-secondary">{dryRun.result.message}</p>
                  </>
                ) : (
                  <p className="text-ink-secondary">The definition is not valid, so it was not run.</p>
                )}
                <p className="mt-1 text-[11px] text-ink-muted">
                  A dry run changes nothing and is not recorded against any application.
                </p>
              </div>
            )}
          </div>
        </details>

        {savedNote && <Notice tone="success">{savedNote}</Notice>}
        {error && (
          <Notice tone="error" title="Something went wrong">
            {error}
          </Notice>
        )}
      </div>
    </Dialog>
  )
}
