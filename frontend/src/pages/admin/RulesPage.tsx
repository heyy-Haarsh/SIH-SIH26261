import { useEffect, useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input, Label, Select, Textarea } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { Tabs } from '@/components/ui/Tabs'
import { RuleDraftPanel } from '@/components/admin/RuleDraftPanel'
import { RuleImportPanel } from '@/components/admin/RuleImportPanel'
import { errorText } from '@/components/scrutiny/scrutinyUi'
import { api } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import { formatDateTime } from '@/lib/format'
import type { AdminRule, AdminRuleVersion, RuleUsage } from '@/types'

const STATUS_TONE: Record<string, 'pass' | 'warning' | 'neutral' | 'info'> = {
  published: 'pass',
  draft: 'warning',
  retired: 'neutral',
  discarded: 'neutral',
}

const STATUS_HELP: Record<string, string> = {
  published: 'Active — used for new checks',
  draft: 'Not active — awaiting review',
  retired: 'Replaced — kept as history',
  discarded: 'Withdrawn draft',
}

export function RulesPage() {
  const { role } = useRole()
  const [tab, setTab] = useState('rules')
  const [rules, setRules] = useState<AdminRule[]>([])
  const [filter, setFilter] = useState<'all' | 'synthetic' | 'official'>('all')
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [usage, setUsage] = useState<RuleUsage | null>(null)
  const [reason, setReason] = useState('')
  const [newVersion, setNewVersion] = useState('v2')
  const [newDef, setNewDef] = useState('{"logic":"missing_mandatory","synthetic":true}')
  const [openDef, setOpenDef] = useState<string | null>(null)
  const [createForm, setCreateForm] = useState({
    code: 'SYN-RULE-',
    name: '',
    is_synthetic: true,
    handbook_ref: '',
    verified_source_ref: '',
    definition: '{"logic":"missing_mandatory","synthetic":true}',
  })

  async function load() {
    try {
      const rows = await api.listAdminRules(role, filter === 'all' ? undefined : { synthetic: filter === 'synthetic' })
      setRules(rows)
      setError(null)
    } catch (err) {
      setError(errorText(err, 'Failed to load rules'))
    }
  }

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role, filter])

  const selected = rules.find((r) => r.id === selectedId) ?? null

  useEffect(() => {
    setUsage(null)
    if (!selected) return
    api
      .getRuleUsage(role, selected.id)
      .then(setUsage)
      .catch(() => setUsage(null))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, selected?.currentVersion, role])

  async function act(label: string, fn: () => Promise<unknown>) {
    setBusy(true)
    setMsg(null)
    try {
      await fn()
      setMsg(label)
      await load()
    } catch (err) {
      setMsg(errorText(err, 'That did not work'))
    } finally {
      setBusy(false)
    }
  }

  function needReason(min = 5): string | null {
    const r = reason.trim()
    if (r.length < min) {
      setMsg(`Enter a reason (at least ${min} characters) in the "Reason" box first.`)
      return null
    }
    return r
  }

  function versionActions(rule: AdminRule, v: AdminRuleVersion) {
    const isCurrent = v.version === rule.currentVersion && v.status === 'published'
    if (v.status === 'draft') {
      return (
        <div className="flex gap-1.5">
          <Button
            size="sm"
            disabled={busy}
            onClick={() => {
              const r = needReason(3)
              if (r) void act(`Activated ${v.version}`, () => api.publishRuleVersion(role, rule.id, v.version, r))
            }}
          >
            Activate
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() => {
              const r = needReason(3)
              if (r) void act(`Discarded draft ${v.version}`, () => api.discardRuleDraft(role, rule.id, v.version, r))
            }}
          >
            Discard
          </Button>
        </div>
      )
    }
    if (v.status === 'retired' || (v.status === 'published' && !isCurrent)) {
      return (
        <Button
          size="sm"
          variant="outline"
          disabled={busy}
          onClick={() => {
            const r = needReason(5)
            if (r) void act(`Reactivated ${v.version}`, () => api.reactivateRuleVersion(role, rule.id, v.version, r))
          }}
        >
          Reactivate
        </Button>
      )
    }
    return null
  }

  return (
    <AppShell title="Regulatory rules" breadcrumbs={['Administrator', 'Rules']}>
      <DemoBanner>
        Rules shipped with the demo are synthetic and labelled so. Official rules need a verified source
        citation. Activating a version only affects future checks — results already recorded keep the
        version that produced them.
      </DemoBanner>

      <div className="mb-4">
        <Tabs
          active={tab}
          onChange={setTab}
          tabs={[
            { id: 'rules', label: 'Rules & versions', count: rules.length },
            { id: 'import', label: 'Import JSON' },
            { id: 'draft', label: 'Draft from description' },
          ]}
        />
      </div>

      {error && (
        <p role="alert" className="mb-3 text-sm text-status-failed">
          {error}
        </p>
      )}
      {msg && (
        <div role="status" className="mb-4 rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2 text-xs">
          {msg}
        </div>
      )}

      {tab === 'import' && (
        <RuleImportPanel
          role={role}
          onSaved={() => {
            void load()
            setTab('rules')
          }}
        />
      )}
      {tab === 'draft' && (
        <RuleDraftPanel
          role={role}
          onSaved={() => {
            void load()
            setTab('rules')
          }}
        />
      )}

      {tab === 'rules' && (
        <>
          <div className="mb-4 flex flex-wrap gap-2">
            {(['all', 'synthetic', 'official'] as const).map((f) => (
              <Button key={f} size="sm" variant={filter === f ? 'primary' : 'outline'} onClick={() => setFilter(f)}>
                {f}
              </Button>
            ))}
          </div>

          <div className="grid gap-4 xl:grid-cols-3">
            <Card>
              <CardHeader title="Create rule" description="Validated before it is saved" />
              <div className="space-y-2 text-sm">
                <div>
                  <Label>Code</Label>
                  <Input value={createForm.code} onChange={(e) => setCreateForm((f) => ({ ...f, code: e.target.value }))} />
                </div>
                <div>
                  <Label>Name</Label>
                  <Input value={createForm.name} onChange={(e) => setCreateForm((f) => ({ ...f, name: e.target.value }))} />
                </div>
                <div>
                  <Label>Kind</Label>
                  <Select
                    value={createForm.is_synthetic ? 'synthetic' : 'official'}
                    onChange={(e) => setCreateForm((f) => ({ ...f, is_synthetic: e.target.value === 'synthetic' }))}
                  >
                    <option value="synthetic">Synthetic demo</option>
                    <option value="official">Official (verified source required)</option>
                  </Select>
                </div>
                {!createForm.is_synthetic && (
                  <>
                    <div>
                      <Label>Handbook reference</Label>
                      <Input
                        value={createForm.handbook_ref}
                        onChange={(e) => setCreateForm((f) => ({ ...f, handbook_ref: e.target.value }))}
                      />
                    </div>
                    <div>
                      <Label>Verified source citation</Label>
                      <Input
                        value={createForm.verified_source_ref}
                        onChange={(e) => setCreateForm((f) => ({ ...f, verified_source_ref: e.target.value }))}
                        placeholder="Document / gazette / verified handbook citation"
                      />
                    </div>
                  </>
                )}
                <div>
                  <Label>Definition (JSON)</Label>
                  <Textarea
                    rows={4}
                    className="font-mono text-xs"
                    value={createForm.definition}
                    onChange={(e) => setCreateForm((f) => ({ ...f, definition: e.target.value }))}
                  />
                </div>
                <Button
                  disabled={busy}
                  onClick={() =>
                    void act('Rule created and published as v1.', async () => {
                      let definition: unknown
                      try {
                        definition = JSON.parse(createForm.definition)
                      } catch (e) {
                        throw new Error(`The definition is not valid JSON: ${(e as Error).message}`)
                      }
                      const payload = {
                        code: createForm.code,
                        name: createForm.name,
                        is_synthetic: createForm.is_synthetic,
                        handbook_ref: createForm.handbook_ref,
                        verified_source_ref: createForm.verified_source_ref,
                        definition,
                        version: 'v1',
                        change_reason: 'Created from admin UI',
                      }
                      const check = await api.validateAdminRule(role, payload)
                      if (!check.valid) throw new Error(`Validation failed: ${check.errors.join('; ')}`)
                      await api.createAdminRule(role, payload)
                    })
                  }
                >
                  Validate & create
                </Button>
              </div>
            </Card>

            <Card>
              <CardHeader title="Rules" description={`${rules.length} listed`} />
              <ul className="max-h-[32rem] space-y-2 overflow-auto">
                {rules.map((r) => {
                  const drafts = r.versions.filter((v) => v.status === 'draft').length
                  return (
                    <li key={r.id}>
                      <button
                        type="button"
                        className={`w-full rounded-[var(--radius-md)] border px-3 py-2 text-left ${
                          selectedId === r.id ? 'border-accent bg-accent/5' : 'border-border'
                        }`}
                        onClick={() => setSelectedId(r.id)}
                      >
                        <div className="flex flex-wrap items-center gap-1">
                          <span className="text-sm font-medium text-ink">{r.ruleCode}</span>
                          <Badge tone={r.isSynthetic ? 'info' : 'warning'}>{r.isSynthetic ? 'synthetic' : 'official'}</Badge>
                          <Badge tone={r.isActive ? 'pass' : 'neutral'}>{r.isActive ? 'on' : 'off'}</Badge>
                          {drafts > 0 && <Badge tone="warning">{drafts} draft</Badge>}
                        </div>
                        <div className="text-xs text-ink-muted">
                          {r.name} · current {r.currentVersion}
                        </div>
                      </button>
                    </li>
                  )
                })}
              </ul>
            </Card>

            <Card>
              <CardHeader title={selected ? selected.ruleCode : 'Versions'} description={selected ? selected.name : 'Select a rule'} />
              {!selected ? (
                <p className="text-xs text-ink-muted">Select a rule to see and manage its versions.</p>
              ) : (
                <div className="space-y-3">
                  <div>
                    <Label>Reason (used for the action you click)</Label>
                    <Input
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      placeholder="Why are you making this change?"
                    />
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy}
                    onClick={() => {
                      const r = needReason(3)
                      if (r)
                        void act(selected.isActive ? 'Rule switched off' : 'Rule switched on', () =>
                          api.updateAdminRule(role, selected.id, { is_active: !selected.isActive, change_reason: r }),
                        )
                    }}
                  >
                    {selected.isActive ? 'Switch rule off' : 'Switch rule on'}
                  </Button>

                  <div>
                    <div className="mb-1 text-xs font-semibold text-ink">Version history</div>
                    <ul className="max-h-72 space-y-1.5 overflow-auto text-xs">
                      {[...selected.versions].reverse().map((v) => {
                        const isCurrent = v.version === selected.currentVersion && v.status === 'published'
                        const used = usage?.findingsByVersion?.[v.version]
                        return (
                          <li key={v.id} className="rounded border border-border px-2 py-1.5">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div className="flex flex-wrap items-center gap-1.5">
                                <span className="font-medium">{v.version}</span>
                                <Badge tone={STATUS_TONE[v.status] ?? 'neutral'}>{v.status}</Badge>
                                {isCurrent && <Badge tone="info">in use</Badge>}
                              </div>
                              {versionActions(selected, v)}
                            </div>
                            <div className="mt-0.5 text-ink-muted">{STATUS_HELP[v.status] ?? v.status}</div>
                            <div className="text-ink-muted">{v.changeReason || '—'}</div>
                            <div className="text-[11px] text-ink-muted">
                              {v.effectiveFrom ? `From ${formatDateTime(v.effectiveFrom)}` : 'Not yet effective'}
                              {v.effectiveTo ? ` to ${formatDateTime(v.effectiveTo)}` : ''}
                              {used ? ` · produced ${used} recorded finding(s)` : ''}
                            </div>
                            <button
                              type="button"
                              className="mt-1 text-[11px] text-accent underline"
                              onClick={() => setOpenDef(openDef === v.id ? null : v.id)}
                            >
                              {openDef === v.id ? 'Hide definition' : 'Show definition'}
                            </button>
                            {openDef === v.id && (
                              <pre className="mt-1 max-h-32 overflow-auto rounded bg-surface px-2 py-1 text-[11px]">
                                {JSON.stringify(v.definition, null, 2)}
                              </pre>
                            )}
                          </li>
                        )
                      })}
                    </ul>
                    {usage && <p className="mt-1 text-[11px] text-ink-muted">{usage.note}</p>}
                  </div>

                  <div className="border-t border-border pt-3">
                    <div className="mb-2 text-xs font-semibold text-ink">New version (history is never edited)</div>
                    <Label>Version name</Label>
                    <Input className="mb-2" value={newVersion} onChange={(e) => setNewVersion(e.target.value)} />
                    <Label>Definition (JSON)</Label>
                    <Textarea
                      className="mb-2 font-mono text-xs"
                      rows={3}
                      value={newDef}
                      onChange={(e) => setNewDef(e.target.value)}
                    />
                    <div className="flex flex-wrap gap-2">
                      {([false, true] as const).map((publish) => (
                        <Button
                          key={String(publish)}
                          size="sm"
                          variant={publish ? 'primary' : 'outline'}
                          disabled={busy}
                          onClick={() => {
                            const r = needReason(5)
                            if (!r) return
                            void act(publish ? `Published ${newVersion}` : `Saved ${newVersion} as a draft`, async () => {
                              let definition: unknown
                              try {
                                definition = JSON.parse(newDef)
                              } catch (e) {
                                throw new Error(`The definition is not valid JSON: ${(e as Error).message}`)
                              }
                              await api.createRuleVersion(role, selected.id, {
                                version: newVersion,
                                definition,
                                change_reason: r,
                                publish,
                              })
                              setReason('')
                            })
                          }}
                        >
                          {publish ? 'Publish now' : 'Save as draft'}
                        </Button>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </Card>
          </div>
        </>
      )}
    </AppShell>
  )
}
