import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, Copy } from 'lucide-react'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Loading, Notice } from '@/components/ui/Notice'
import { EmptyState } from '@/components/ui/EmptyState'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import { RULE_STATUS, VERSION_STATUS, ruleTypeLabel } from '@/lib/configLabels'
import { formatDateTime } from '@/lib/format'
import type { ConfigRequirement, ConfigRule, RequirementRulesResponse, RuleVersionInfo } from '@/types'

/**
 * Rules of one document requirement. The readable view and the JSON view are both rendered
 * from the same saved version, so they cannot disagree.
 */
export function RulesDialog({
  open,
  onClose,
  requirement,
  categoryName,
  version,
  onAddRule,
  onEditDraft,
  onChanged,
}: {
  open: boolean
  onClose: () => void
  requirement: ConfigRequirement
  categoryName: string
  /** Bumped by the parent after the editor saves, so this list reloads. */
  version: number
  onAddRule: () => void
  onEditDraft: (rule: ConfigRule) => void
  onChanged: () => void
}) {
  const { role } = useRole()
  const [data, setData] = useState<RequirementRulesResponse | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<ConfigRule | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const loadList = useCallback(() => {
    setError(null)
    api
      .cfgRequirementRules(role, requirement.id)
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Rules could not be loaded.'))
  }, [role, requirement.id])

  const loadDetail = useCallback(
    (id: string) => {
      setError(null)
      api
        .cfgGetRule(role, id)
        .then(setDetail)
        .catch((err) => setError(err instanceof ApiError ? err.message : 'The rule could not be loaded.'))
    },
    [role],
  )

  useEffect(() => {
    if (!open) {
      setSelectedId(null)
      setDetail(null)
      setData(null)
      return
    }
    loadList()
  }, [open, loadList, version])

  useEffect(() => {
    if (selectedId) loadDetail(selectedId)
    else setDetail(null)
  }, [selectedId, loadDetail, version])

  async function act(fn: () => Promise<unknown>, failure: string) {
    setBusy(true)
    setError(null)
    try {
      await fn()
      onChanged()
      loadList()
      if (selectedId) loadDetail(selectedId)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : failure)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      width="max-w-3xl"
      title={detail ? `${detail.code}: ${detail.title}` : 'Rules'}
      subtitle={
        <>
          Category: <strong className="text-ink">{categoryName}</strong> · Document:{' '}
          <strong className="text-ink">{requirement.name}</strong>
        </>
      }
      footer={
        detail ? (
          <Button variant="ghost" leftIcon={<ArrowLeft size={16} strokeWidth={1.5} />} onClick={() => setSelectedId(null)}>
            All rules
          </Button>
        ) : (
          <>
            <Button variant="outline" onClick={onClose}>
              Close
            </Button>
            <Button onClick={onAddRule}>Add Rule</Button>
          </>
        )
      }
    >
      {error && (
        <Notice tone="error" className="mb-4" onRetry={selectedId ? () => loadDetail(selectedId) : loadList}>
          {error}
        </Notice>
      )}

      {!detail && !data && !error && <Loading label="Loading rules" />}

      {!detail && data && data.rules.length === 0 && (
        <EmptyState
          title="No rules for this document yet"
          description="Without rules, this document is only checked for presence, type and size."
          action={<Button onClick={onAddRule}>Add Rule</Button>}
        />
      )}

      {!detail && data && data.rules.length > 0 && (
        <ul className="divide-y divide-border rounded-[var(--radius-md)] border border-border">
          {data.rules.map((r) => {
            const st = RULE_STATUS[r.status]
            return (
              <li key={r.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(r.id)}
                  className="flex w-full items-start justify-between gap-4 px-4 py-3 text-left hover:bg-surface"
                >
                  <span className="min-w-0">
                    <span className="mono text-ink-muted">{r.code}</span>
                    <span className="block truncate text-sm font-medium text-ink">{r.title}</span>
                    <span className="block text-xs text-ink-muted">
                      {ruleTypeLabel(r.ruleType)}
                      {r.activeVersion != null && ` · active v${r.activeVersion}`}
                      {r.draftVersion != null && ` · draft v${r.draftVersion}`}
                    </span>
                  </span>
                  <Badge tone={st.tone}>{st.label}</Badge>
                </button>
              </li>
            )
          })}
        </ul>
      )}

      {detail && (
        <RuleDetail
          rule={detail}
          busy={busy}
          onEdit={() =>
            act(async () => {
              const edited = detail.draftVersion != null ? detail : await api.cfgEditRule(role, detail.id)
              onEditDraft(edited.versions ? edited : await api.cfgGetRule(role, edited.id))
            }, 'A draft could not be started.')
          }
          onDuplicate={() =>
            act(async () => {
              const copy = await api.cfgDuplicateRule(role, detail.id)
              setSelectedId(copy.id)
            }, 'The rule could not be duplicated.')
          }
          onDeactivate={() => act(() => api.cfgDeactivateRule(role, detail.id), 'The rule could not be deactivated.')}
          onDiscard={() => act(() => api.cfgDiscardRuleDraft(role, detail.id), 'The draft could not be discarded.')}
          onActivate={(v, confirm) =>
            act(() => api.cfgActivateRule(role, detail.id, v, confirm), 'The rule could not be activated.')
          }
        />
      )}
    </Dialog>
  )
}

function RuleDetail({
  rule,
  busy,
  onEdit,
  onDuplicate,
  onDeactivate,
  onDiscard,
  onActivate,
}: {
  rule: ConfigRule
  busy: boolean
  onEdit: () => void
  onDuplicate: () => void
  onDeactivate: () => void
  onDiscard: () => void
  onActivate: (version: number, confirmInterpretation: boolean) => void
}) {
  const versions = [...(rule.versions ?? [])].sort((a, b) => b.version - a.version)
  const [shownVersion, setShownVersion] = useState<number | null>(null)
  const [view, setView] = useState<'readable' | 'json'>('readable')
  const [copied, setCopied] = useState(false)
  const current: RuleVersionInfo | undefined =
    versions.find((v) => v.version === shownVersion) ??
    versions.find((v) => v.status === 'published') ??
    versions[0]
  const draft = versions.find((v) => v.status === 'draft')
  const st = RULE_STATUS[rule.status]

  useEffect(() => {
    setShownVersion(null)
  }, [rule.id])

  async function copy() {
    if (!current) return
    try {
      await navigator.clipboard.writeText(JSON.stringify(current.definition, null, 2))
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={st.tone}>{st.label}</Badge>
        <span className="text-xs text-ink-muted">{ruleTypeLabel(rule.ruleType)}</span>
        {rule.sourceReference ? (
          <span className="text-xs text-ink-muted">· Source: {rule.sourceReference}</span>
        ) : (
          <span className="text-xs text-ink-muted">· No source reference recorded</span>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" disabled={busy} onClick={onEdit}>
          {draft ? 'Continue editing draft' : 'Edit (creates a new version)'}
        </Button>
        <Button size="sm" variant="outline" disabled={busy} onClick={onDuplicate}>
          Duplicate
        </Button>
        {rule.status === 'active' && (
          <Button size="sm" variant="outline" disabled={busy} onClick={onDeactivate}>
            Deactivate
          </Button>
        )}
        {draft && (
          <>
            <Button
              size="sm"
              disabled={busy}
              onClick={() => onActivate(draft.version, draft.authoringMode === 'plain')}
              title={
                draft.authoringMode === 'plain'
                  ? 'Activating confirms you reviewed the structured interpretation'
                  : undefined
              }
            >
              Activate v{draft.version}
            </Button>
            <Button size="sm" variant="ghost" disabled={busy} onClick={onDiscard}>
              Discard draft
            </Button>
          </>
        )}
        {rule.status === 'inactive' && !draft && rule.latestVersion != null && (
          <Button size="sm" disabled={busy} onClick={() => onActivate(rule.latestVersion as number, true)}>
            Activate v{rule.latestVersion}
          </Button>
        )}
      </div>

      {current ? (
        <section className="rounded-[var(--radius-md)] border border-border">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-2">
            <div role="tablist" aria-label="Rule view" className="flex gap-1">
              {(['readable', 'json'] as const).map((v) => (
                <button
                  key={v}
                  role="tab"
                  aria-selected={view === v}
                  type="button"
                  onClick={() => setView(v)}
                  className={`px-2.5 py-1 text-xs ${
                    view === v ? 'border-b-2 border-ink font-medium text-ink' : 'text-ink-muted hover:text-ink'
                  }`}
                >
                  {v === 'readable' ? 'Human-readable' : 'Structured JSON'}
                </button>
              ))}
            </div>
            <span className="mono text-ink-muted">
              version {current.version} · {VERSION_STATUS[current.status]?.label ?? current.status}
            </span>
          </div>
          <div className="p-4">
            {view === 'readable' ? (
              current.explanation ? (
                <dl className="space-y-2 text-sm">
                  <div>
                    <dt className="text-xs font-semibold text-ink">What is checked</dt>
                    <dd className="text-ink-secondary">{current.explanation.condition}</dd>
                  </div>
                  <div>
                    <dt className="text-xs font-semibold text-ink">If it passes</dt>
                    <dd className="text-ink-secondary">{current.explanation.onPass}</dd>
                  </div>
                  <div>
                    <dt className="text-xs font-semibold text-ink">If it does not pass</dt>
                    <dd className="text-ink-secondary">{current.explanation.onFail}</dd>
                  </div>
                  <div>
                    <dt className="text-xs font-semibold text-ink">If it cannot be evaluated</dt>
                    <dd className="text-ink-secondary">{current.explanation.onUnable}</dd>
                  </div>
                  {current.naturalLanguage && (
                    <div>
                      <dt className="text-xs font-semibold text-ink">Original wording (not executed)</dt>
                      <dd className="text-ink-secondary">{current.naturalLanguage}</dd>
                    </div>
                  )}
                </dl>
              ) : (
                <p className="text-sm text-ink-muted">
                  This version has no structured definition, so it cannot be activated or run.
                </p>
              )
            ) : (
              <div>
                <pre className="mono max-h-72 overflow-auto rounded bg-surface p-3 text-xs">
                  {JSON.stringify(current.definition, null, 2)}
                </pre>
                <Button
                  size="sm"
                  variant="ghost"
                  className="mt-2"
                  leftIcon={<Copy size={16} strokeWidth={1.5} />}
                  onClick={copy}
                >
                  {copied ? 'Copied' : 'Copy JSON'}
                </Button>
              </div>
            )}
          </div>
        </section>
      ) : (
        <Notice>This rule has no saved versions.</Notice>
      )}

      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-muted">Version history</h3>
        <ul className="divide-y divide-border rounded-[var(--radius-md)] border border-border text-xs">
          {versions.map((v) => (
            <li key={v.id}>
              <button
                type="button"
                onClick={() => setShownVersion(v.version)}
                aria-current={current?.version === v.version}
                className={`flex w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-surface ${
                  current?.version === v.version ? 'bg-surface' : ''
                }`}
              >
                <span>
                  <span className="mono">v{v.version}</span>
                  <span className="ml-2 text-ink-secondary">{v.changeSummary || v.title}</span>
                </span>
                <span className="flex items-center gap-2">
                  <span className="text-ink-muted">{formatDateTime(v.publishedAt ?? v.updatedAt ?? v.createdAt)}</span>
                  <Badge tone={VERSION_STATUS[v.status]?.tone ?? 'neutral'}>
                    {VERSION_STATUS[v.status]?.label ?? v.status}
                  </Badge>
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
