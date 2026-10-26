import { useEffect, useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input, Label, Select, Textarea } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import type { AdminRule } from '@/types'

export function RulesPage() {
  const { role } = useRole()
  const [rules, setRules] = useState<AdminRule[]>([])
  const [filter, setFilter] = useState<'all' | 'synthetic' | 'official'>('all')
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [newVersion, setNewVersion] = useState('v2')
  const [newDef, setNewDef] = useState('{"logic":"missing_mandatory","synthetic":true}')
  const [changeReason, setChangeReason] = useState('')
  const [createForm, setCreateForm] = useState({
    code: 'SYN-RULE-',
    name: '',
    is_synthetic: true,
    handbook_ref: 'Demo handbook (placeholder — not official AICTE APH)',
    verified_source_ref: '',
    definition: '{"logic":"missing_mandatory","synthetic":true}',
  })

  function load() {
    const opts =
      filter === 'all'
        ? undefined
        : { synthetic: filter === 'synthetic' }
    api
      .listAdminRules(role, opts)
      .then((rows) => {
        setRules(rows)
        setError(null)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Failed to load rules'))
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role, filter])

  const selected = rules.find((r) => r.id === selectedId) ?? null

  return (
    <AppShell title="Regulatory Rules" breadcrumbs={['Administrator', 'Rules']}>
      <DemoBanner>
        Synthetic demo rules are labeled clearly. Official rules require a verified source citation —
        never invent AICTE clauses. Publishing validates configuration; historical versions are never
        overwritten.
      </DemoBanner>

      {error && (
        <div className="mb-4 rounded-[var(--radius-md)] border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          {error}
        </div>
      )}
      {msg && (
        <div className="mb-4 rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2 text-xs">
          {msg}
        </div>
      )}

      <div className="mb-4 flex flex-wrap gap-2">
        {(['all', 'synthetic', 'official'] as const).map((f) => (
          <Button
            key={f}
            size="sm"
            variant={filter === f ? 'primary' : 'outline'}
            onClick={() => setFilter(f)}
          >
            {f}
          </Button>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-1">
          <CardHeader title="Create rule" description="Validated before save" />
          <div className="space-y-2 text-sm">
            <div>
              <Label>Code</Label>
              <Input
                value={createForm.code}
                onChange={(e) => setCreateForm((f) => ({ ...f, code: e.target.value }))}
              />
            </div>
            <div>
              <Label>Name</Label>
              <Input
                value={createForm.name}
                onChange={(e) => setCreateForm((f) => ({ ...f, name: e.target.value }))}
              />
            </div>
            <div>
              <Label>Kind</Label>
              <Select
                value={createForm.is_synthetic ? 'synthetic' : 'official'}
                onChange={(e) =>
                  setCreateForm((f) => ({
                    ...f,
                    is_synthetic: e.target.value === 'synthetic',
                  }))
                }
              >
                <option value="synthetic">Synthetic demo</option>
                <option value="official">Official (verified source required)</option>
              </Select>
            </div>
            {!createForm.is_synthetic && (
              <div>
                <Label>Verified source citation</Label>
                <Input
                  value={createForm.verified_source_ref}
                  onChange={(e) =>
                    setCreateForm((f) => ({ ...f, verified_source_ref: e.target.value }))
                  }
                  placeholder="Document / gazette / verified handbook citation"
                />
              </div>
            )}
            <div>
              <Label>Definition JSON</Label>
              <Textarea
                rows={4}
                value={createForm.definition}
                onChange={(e) => setCreateForm((f) => ({ ...f, definition: e.target.value }))}
              />
            </div>
            <Button
              disabled={busy}
              onClick={async () => {
                setBusy(true)
                setMsg(null)
                try {
                  const definition = JSON.parse(createForm.definition)
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
                  if (!check.valid) {
                    setMsg(`Validation failed: ${check.errors.join('; ')}`)
                    return
                  }
                  await api.createAdminRule(role, payload)
                  setMsg('Rule created and published as v1.')
                  load()
                } catch (err) {
                  setMsg(err instanceof Error ? err.message : 'Create failed')
                } finally {
                  setBusy(false)
                }
              }}
            >
              Validate & create
            </Button>
          </div>
        </Card>

        <Card className="xl:col-span-1">
          <CardHeader title="Rules" description={`${rules.length} listed`} />
          <ul className="max-h-[28rem] space-y-2 overflow-auto">
            {rules.map((r) => (
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
                    <Badge tone={r.isSynthetic ? 'info' : 'warning'}>
                      {r.isSynthetic ? 'synthetic' : 'official'}
                    </Badge>
                    <Badge tone={r.isActive ? 'pass' : 'neutral'}>
                      {r.isActive ? 'on' : 'off'}
                    </Badge>
                  </div>
                  <div className="text-xs text-ink-muted">
                    {r.name} · current {r.currentVersion}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </Card>

        <Card className="xl:col-span-1">
          <CardHeader
            title={selected ? selected.ruleCode : 'Versioning'}
            description={selected ? selected.name : 'Select a rule'}
          />
          {!selected ? (
            <p className="text-xs text-ink-muted">Select a rule to manage versions.</p>
          ) : (
            <div className="space-y-3">
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy}
                  onClick={async () => {
                    const reason = window.prompt(
                      selected.isActive ? 'Reason to disable?' : 'Reason to enable?',
                      selected.isActive ? 'Disable rule' : 'Re-enable rule',
                    )
                    if (!reason || reason.trim().length < 3) return
                    setBusy(true)
                    try {
                      await api.updateAdminRule(role, selected.id, {
                        is_active: !selected.isActive,
                        change_reason: reason.trim(),
                      })
                      load()
                    } catch (err) {
                      setMsg(err instanceof Error ? err.message : 'Update failed')
                    } finally {
                      setBusy(false)
                    }
                  }}
                >
                  {selected.isActive ? 'Disable' : 'Enable'}
                </Button>
              </div>

              <div>
                <div className="mb-1 text-xs font-semibold text-ink">Version history</div>
                <ul className="max-h-40 space-y-1 overflow-auto text-xs">
                  {selected.versions.map((v) => (
                    <li
                      key={v.id}
                      className="flex items-center justify-between gap-2 rounded border border-border px-2 py-1.5"
                    >
                      <div>
                        <span className="font-medium">{v.version}</span>{' '}
                        <Badge tone={v.status === 'published' ? 'pass' : 'neutral'}>{v.status}</Badge>
                        {v.version === selected.currentVersion && (
                          <Badge tone="info">current</Badge>
                        )}
                        <div className="text-ink-muted">{v.changeReason || '—'}</div>
                      </div>
                      {v.version !== selected.currentVersion && v.status === 'published' && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={busy}
                          onClick={async () => {
                            const reason = window.prompt(
                              'Reason to reactivate this version?',
                              'Rollback to prior published version',
                            )
                            if (!reason || reason.trim().length < 5) return
                            setBusy(true)
                            try {
                              await api.reactivateRuleVersion(
                                role,
                                selected.id,
                                v.version,
                                reason.trim(),
                              )
                              setMsg(`Reactivated ${v.version}`)
                              load()
                            } catch (err) {
                              setMsg(err instanceof Error ? err.message : 'Reactivate failed')
                            } finally {
                              setBusy(false)
                            }
                          }}
                        >
                          Reactivate
                        </Button>
                      )}
                    </li>
                  ))}
                </ul>
              </div>

              <div className="border-t border-border pt-3">
                <div className="mb-2 text-xs font-semibold text-ink">New version (immutable)</div>
                <Label>Version id</Label>
                <Input className="mb-2" value={newVersion} onChange={(e) => setNewVersion(e.target.value)} />
                <Label>Definition JSON</Label>
                <Textarea
                  className="mb-2"
                  rows={3}
                  value={newDef}
                  onChange={(e) => setNewDef(e.target.value)}
                />
                <Label>Change reason</Label>
                <Input
                  className="mb-2"
                  value={changeReason}
                  onChange={(e) => setChangeReason(e.target.value)}
                  placeholder="Why this version?"
                />
                <Button
                  size="sm"
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true)
                    setMsg(null)
                    try {
                      const definition = JSON.parse(newDef)
                      await api.createRuleVersion(role, selected.id, {
                        version: newVersion,
                        definition,
                        change_reason: changeReason,
                        publish: true,
                      })
                      setMsg(`Published ${newVersion}`)
                      setChangeReason('')
                      load()
                    } catch (err) {
                      setMsg(err instanceof Error ? err.message : 'Version failed')
                    } finally {
                      setBusy(false)
                    }
                  }}
                >
                  Publish new version
                </Button>
              </div>
            </div>
          )}
        </Card>
      </div>
    </AppShell>
  )
}
