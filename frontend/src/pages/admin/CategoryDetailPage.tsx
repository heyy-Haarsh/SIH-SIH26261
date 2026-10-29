import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowDown, ArrowUp, ChevronLeft, Plus } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Dialog } from '@/components/ui/Dialog'
import { Input, Label, Textarea } from '@/components/ui/Input'
import { Loading, Notice } from '@/components/ui/Notice'
import { SkeletonDetailLayout } from '@/components/ui/Skeleton'
import { InfoFieldsEditor } from '@/components/admin/InfoFieldsEditor'
import { RequirementDialog } from '@/components/admin/RequirementDialog'
import { RuleEditorDialog } from '@/components/admin/RuleEditorDialog'
import { RulesDialog } from '@/components/admin/RulesDialog'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import { CONFIG_STATE } from '@/lib/configLabels'
import { formatDateTime } from '@/lib/format'
import type { ConfigCategoryDetail, ConfigRequirement, ConfigRule } from '@/types'

interface EditorTarget {
  requirement: ConfigRequirement
  rule: ConfigRule | null
  fromList: boolean
}

export function CategoryDetailPage() {
  const { id = '' } = useParams()
  const { role } = useRole()
  const [cat, setCat] = useState<ConfigCategoryDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [isActive, setIsActive] = useState(false)
  const [savingMeta, setSavingMeta] = useState(false)

  const [requirementDialog, setRequirementDialog] = useState<{ requirement: ConfigRequirement | null } | null>(null)
  const [rulesFor, setRulesFor] = useState<ConfigRequirement | null>(null)
  const [editor, setEditor] = useState<EditorTarget | null>(null)
  const [ruleTick, setRuleTick] = useState(0)
  const [publishing, setPublishing] = useState(false)
  const [deactivate, setDeactivate] = useState<{ requirement: ConfigRequirement; message: string | null } | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    setError(null)
    api
      .cfgGetCategory(role, id)
      .then((c) => {
        setCat(c)
        setName(c.name)
        setDescription(c.description)
        setIsActive(c.isActive)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'The category could not be loaded.'))
  }, [role, id])

  useEffect(load, [load])

  const reloadAfterRule = useCallback(() => {
    setRuleTick((t) => t + 1)
    load()
  }, [load])

  async function saveMeta() {
    setSavingMeta(true)
    setActionError(null)
    try {
      await api.cfgUpdateCategory(role, id, { name, description, is_active: isActive })
      load()
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'The details could not be saved.')
    } finally {
      setSavingMeta(false)
    }
  }

  async function move(index: number, delta: number) {
    if (!cat) return
    const ids = cat.requirements.map((r) => r.id)
    const j = index + delta
    if (j < 0 || j >= ids.length) return
    ;[ids[index], ids[j]] = [ids[j], ids[index]]
    setBusy(true)
    setActionError(null)
    try {
      await api.cfgReorderRequirements(role, id, ids)
      load()
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'The order could not be saved.')
    } finally {
      setBusy(false)
    }
  }

  async function setRequirementActive(req: ConfigRequirement, active: boolean, acknowledge: boolean) {
    setBusy(true)
    setActionError(null)
    try {
      await api.cfgUpdateRequirement(role, req.id, { is_active: active, acknowledge_impact: acknowledge })
      setDeactivate(null)
      load()
    } catch (err) {
      if (err instanceof ApiError && err.code === 'impact_not_acknowledged') {
        setDeactivate({ requirement: req, message: err.message })
      } else {
        setDeactivate(null)
        setActionError(err instanceof ApiError ? err.message : 'The requirement could not be changed.')
      }
    } finally {
      setBusy(false)
    }
  }

  if (error) {
    return (
      <AppShell title="Category" breadcrumbs={['Administration', 'Application Categories']}>
        <div className="mx-auto max-w-3xl space-y-3">
          <Notice tone="error" title="Could not load this category" onRetry={load}>
            {error}
          </Notice>
          <Link to="/admin/categories" className="text-sm text-ink-secondary underline">
            Back to categories
          </Link>
        </div>
      </AppShell>
    )
  }
  if (!cat) {
    return (
      <AppShell title="Category Details" breadcrumbs={['Administration', 'Application Categories']}>
        <SkeletonDetailLayout />
      </AppShell>
    )
  }

  const state = CONFIG_STATE[cat.configState]
  const metaDirty = name !== cat.name || description !== cat.description || isActive !== cat.isActive
  const canPublish = cat.validation.valid && cat.pendingChanges.length > 0

  return (
    <AppShell
      title={cat.name}
      description="Information, documents and rules for this application purpose."
      breadcrumbs={['Administration', 'Application Categories', cat.code]}
      actions={
        <>
          <Link to="/admin/categories" className="mr-auto inline-flex items-center gap-1 text-sm text-ink-secondary hover:text-ink">
            <ChevronLeft size={16} strokeWidth={1.5} /> All categories
          </Link>
          <Button onClick={() => setPublishing(true)} disabled={!canPublish} title={canPublish ? undefined : cat.validation.valid ? 'Nothing to publish' : 'Resolve validation errors first'}>
            Publish Configuration
          </Button>
        </>
      }
    >
      <div className="mx-auto max-w-7xl space-y-6">
        {actionError && (
          <Notice tone="error" title="That did not work">
            {actionError}
          </Notice>
        )}

        <Card>
          <CardHeader title="Category details" />
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <Label htmlFor="cat-name">Name</Label>
              <Input id="cat-name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="cat-code">Identifier</Label>
              <Input id="cat-code" className="mono" value={cat.code} disabled />
            </div>
            <div className="md:col-span-2">
              <Label htmlFor="cat-desc">Application purpose</Label>
              <Textarea id="cat-desc" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
            </div>
            <label className="flex items-center gap-2 text-sm md:col-span-2">
              <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
              Available to institutions (requires a published configuration)
            </label>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button onClick={saveMeta} disabled={savingMeta || !metaDirty || name.trim().length < 2}>
              {savingMeta ? 'Saving' : 'Save details'}
            </Button>
            <div className="flex items-center gap-2 text-xs text-ink-muted">
              <Badge tone={state.tone}>{state.label}</Badge>
              {cat.configVersion != null && <span className="mono">version {cat.configVersion}</span>}
              <span>{state.hint}</span>
            </div>
          </div>
        </Card>

        <Card>
          <CardHeader title="Required information" description="Collected from the institution in the first step of the application." />
          <InfoFieldsEditor
            categoryId={cat.id}
            fields={cat.infoFields}
            supportedTypes={cat.supportedFieldTypes}
            onSaved={load}
          />
        </Card>

        <Card padding={false}>
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4">
            <div>
              <h2 className="text-sm font-semibold text-ink">Required documents</h2>
              <p className="text-xs text-ink-muted">One row per document requirement. Rules attach to a requirement.</p>
            </div>
            <Button variant="outline" leftIcon={<Plus size={16} strokeWidth={1.5} />} onClick={() => setRequirementDialog({ requirement: null })}>
              Add Document Requirement
            </Button>
          </div>
          {cat.requirements.length === 0 ? (
            <p className="px-5 py-8 text-sm text-ink-muted">
              No documents are configured. Institutions can only be asked for documents you add here.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border text-xs text-ink-muted">
                  <tr>
                    <th className="px-5 py-2.5 font-medium">Document</th>
                    <th className="px-3 py-2.5 font-medium">Need</th>
                    <th className="px-3 py-2.5 font-medium">Type and size</th>
                    <th className="px-3 py-2.5 font-medium">Rules</th>
                    <th className="px-3 py-2.5 font-medium">Status</th>
                    <th className="px-5 py-2.5 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {cat.requirements.map((r, i) => (
                    <tr key={r.id} className={`border-b border-border last:border-0 ${r.isActive ? '' : 'bg-surface text-ink-muted'}`}>
                      <td className="px-5 py-3 align-top">
                        <div className="font-medium text-ink">{r.name}</div>
                        <div className="mono text-ink-muted">{r.code}</div>
                      </td>
                      <td className="px-3 py-3 align-top">{r.mandatory ? 'Required' : 'Optional'}</td>
                      <td className="px-3 py-3 align-top text-xs">
                        <span className="mono">{r.allowedTypes.join(', ')}</span>
                        <br />
                        {r.maxSizeMb != null ? `up to ${r.maxSizeMb} MB` : 'platform size limit'}
                      </td>
                      <td className="px-3 py-3 align-top text-xs">
                        {r.activeRules} active · {r.draftRules} draft
                      </td>
                      <td className="px-3 py-3 align-top">
                        <Badge tone={r.isActive ? 'pass' : 'pending'}>{r.isActive ? 'Active' : 'Inactive'}</Badge>
                      </td>
                      <td className="px-5 py-3 align-top">
                        <div className="flex flex-wrap justify-end gap-1.5">
                          <Button size="sm" variant="outline" onClick={() => setRulesFor(r)}>
                            View Rules
                          </Button>
                          <Button size="sm" variant="outline" disabled={!r.isActive} onClick={() => setEditor({ requirement: r, rule: null, fromList: false })}>
                            Add Rule
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => setRequirementDialog({ requirement: r })}>
                            Edit Requirement
                          </Button>
                          {r.isActive ? (
                            <Button size="sm" variant="ghost" disabled={busy} onClick={() => setRequirementActive(r, false, false)}>
                              Deactivate
                            </Button>
                          ) : (
                            <Button size="sm" variant="ghost" disabled={busy} onClick={() => setRequirementActive(r, true, false)}>
                              Reactivate
                            </Button>
                          )}
                          <Button size="sm" variant="ghost" aria-label={`Move ${r.name} up`} disabled={busy || i === 0} onClick={() => move(i, -1)}>
                            <ArrowUp size={16} strokeWidth={1.5} />
                          </Button>
                          <Button size="sm" variant="ghost" aria-label={`Move ${r.name} down`} disabled={busy || i === cat.requirements.length - 1} onClick={() => move(i, 1)}>
                            <ArrowDown size={16} strokeWidth={1.5} />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader title="Validation summary" />
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <Badge tone={cat.validation.valid ? 'pass' : 'failed'}>
                  {cat.validation.valid ? 'Ready to publish' : 'Cannot be published yet'}
                </Badge>
                <span className="text-xs text-ink-muted">
                  {cat.validation.counts.infoFields} fields · {cat.validation.counts.requirements} documents ·{' '}
                  {cat.validation.counts.activeRules} active rules
                </span>
              </div>
              {cat.validation.errors.map((e) => (
                <Notice key={e} tone="error">
                  {e}
                </Notice>
              ))}
              {cat.validation.warnings.map((e) => (
                <Notice key={e} tone="warning">
                  {e}
                </Notice>
              ))}
              {cat.pendingChanges.length > 0 && (
                <div>
                  <p className="mt-2 text-xs font-semibold text-ink">Unpublished changes</p>
                  <ul className="ml-4 list-disc text-xs text-ink-secondary">
                    {cat.pendingChanges.map((c) => (
                      <li key={c}>{c}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </Card>

          <Card padding={false}>
            <div className="border-b border-border px-5 py-4">
              <h2 className="text-sm font-semibold text-ink">Version history</h2>
              <p className="text-xs text-ink-muted">Applications keep the version they were created under.</p>
            </div>
            {cat.versions.length === 0 ? (
              <p className="px-5 py-6 text-sm text-ink-muted">Nothing has been published yet.</p>
            ) : (
              <ul className="divide-y divide-border text-xs">
                {cat.versions.map((v) => (
                  <li key={v.id} className="px-5 py-3">
                    <div className="flex items-center justify-between">
                      <span className="mono font-medium text-ink">v{v.version}</span>
                      <Badge tone={v.status === 'published' ? 'pass' : 'pending'}>
                        {v.status === 'published' ? 'Published' : 'Superseded'}
                      </Badge>
                    </div>
                    <p className="mt-1 text-ink-secondary">{v.summary || 'No summary recorded'}</p>
                    <p className="mt-0.5 text-ink-muted">
                      {formatDateTime(v.publishedAt)} · {v.publishedBy ?? 'unknown'} · {v.requirementCount} documents,{' '}
                      {v.ruleCount} rules
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>

      <RequirementDialog
        open={requirementDialog !== null}
        onClose={() => setRequirementDialog(null)}
        categoryId={cat.id}
        categoryName={cat.name}
        requirement={requirementDialog?.requirement ?? null}
        onSaved={load}
      />

      {rulesFor && (
        <RulesDialog
          open
          onClose={() => setRulesFor(null)}
          requirement={rulesFor}
          categoryName={cat.name}
          version={ruleTick}
          onChanged={load}
          onAddRule={() => {
            setEditor({ requirement: rulesFor, rule: null, fromList: true })
            setRulesFor(null)
          }}
          onEditDraft={(rule) => {
            setEditor({ requirement: rulesFor, rule, fromList: true })
            setRulesFor(null)
          }}
        />
      )}

      {editor && (
        <RuleEditorDialog
          open
          onClose={() => {
            if (editor.fromList) setRulesFor(cat.requirements.find((r) => r.id === editor.requirement.id) ?? editor.requirement)
            setEditor(null)
          }}
          categoryName={cat.name}
          requirement={editor.requirement}
          rule={editor.rule}
          onSaved={reloadAfterRule}
        />
      )}

      <Dialog
        open={deactivate !== null}
        onClose={() => setDeactivate(null)}
        title="Deactivate this document requirement?"
        width="max-w-lg"
        footer={
          <>
            <Button variant="outline" onClick={() => setDeactivate(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              disabled={busy}
              onClick={() => deactivate && setRequirementActive(deactivate.requirement, false, true)}
            >
              Deactivate
            </Button>
          </>
        }
      >
        <p className="text-sm text-ink-secondary">{deactivate?.message}</p>
      </Dialog>

      <PublishDialog
        open={publishing}
        onClose={() => setPublishing(false)}
        category={cat}
        onPublished={() => {
          setPublishing(false)
          load()
        }}
      />
    </AppShell>
  )
}

function PublishDialog({
  open,
  onClose,
  category,
  onPublished,
}: {
  open: boolean
  onClose: () => void
  category: ConfigCategoryDetail
  onPublished: () => void
}) {
  const { role } = useRole()
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setNote('')
      setError(null)
    }
  }, [open])

  async function publish() {
    setBusy(true)
    setError(null)
    try {
      await api.cfgPublish(role, category.id, note)
      onPublished()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Publishing failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      dismissible={!busy}
      title={`Publish ${category.name}`}
      subtitle={`This creates version ${(category.configVersion ?? 0) + 1}`}
      width="max-w-lg"
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={publish} disabled={busy}>
            {busy ? 'Publishing' : 'Publish'}
          </Button>
        </>
      }
    >
      <div className="space-y-4 text-sm">
        <div>
          <p className="text-xs font-semibold text-ink">What changes</p>
          <ul className="ml-4 list-disc text-xs text-ink-secondary">
            {category.pendingChanges.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
        <p className="text-xs text-ink-secondary">
          New applications will use this version, including only active documents and active rules. Draft rules are not
          included. Applications that already exist keep the version they were pinned to.
        </p>
        <div>
          <Label htmlFor="pub-note">Note (optional)</Label>
          <Textarea id="pub-note" rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
        </div>
        {error && <Notice tone="error">{error}</Notice>}
      </div>
    </Dialog>
  )
}
