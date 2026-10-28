import { useEffect, useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input, Label, Textarea } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import type { AdminCategory } from '@/types'

const DEFAULT_DOCS_JSON = `[
  {"code": "AFFIDAVIT", "name": "Sworn Affidavit", "mandatory": true, "allowed_types": ["pdf"]}
]`

export function CategoriesPage() {
  const { role } = useRole()
  const [items, setItems] = useState<AdminCategory[]>([])
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [docsJson, setDocsJson] = useState(DEFAULT_DOCS_JSON)

  function load() {
    api
      .listCategories(role)
      .then(setItems)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : 'Failed to load categories'),
      )
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role])

  return (
    <AppShell title="Application Categories" breadcrumbs={['Regional Officer', 'Categories']}>
      <DemoBanner>
        Categories drive the applicant document checklist. Edits are versioned via audit events; use
        Document Requirements to adjust checklist JSON per category.
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

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Create category" description="Code must be unique" />
          <div className="space-y-3">
            <div>
              <Label>Code</Label>
              <Input value={code} onChange={(e) => setCode(e.target.value)} placeholder="NEW-ENG" />
            </div>
            <div>
              <Label>Name</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div>
              <Label>Required documents (JSON)</Label>
              <Textarea rows={8} value={docsJson} onChange={(e) => setDocsJson(e.target.value)} />
            </div>
            <Button
              disabled={busy}
              onClick={async () => {
                setBusy(true)
                setMsg(null)
                try {
                  const required_documents = JSON.parse(docsJson)
                  await api.createCategory(role, { code, name, required_documents })
                  setMsg('Category created.')
                  setCode('')
                  setName('')
                  load()
                } catch (err) {
                  setMsg(err instanceof Error ? err.message : 'Create failed')
                } finally {
                  setBusy(false)
                }
              }}
            >
              Create
            </Button>
          </div>
        </Card>

        <Card>
          <CardHeader title="Configured categories" description={`${items.length} total`} />
          <ul className="space-y-3">
            {items.map((c) => (
              <li key={c.id} className="rounded-[var(--radius-md)] border border-border p-3">
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold text-ink">{c.name}</span>
                  <Badge tone="info">{c.code}</Badge>
                  <Badge tone={c.isActive ? 'pass' : 'neutral'}>
                    {c.isActive ? 'active' : 'inactive'}
                  </Badge>
                </div>
                <p className="mb-2 text-xs text-ink-muted">
                  {(c.requiredDocuments ?? []).length} document requirement(s)
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy}
                  onClick={async () => {
                    const reason = window.prompt(
                      c.isActive ? 'Reason to disable category?' : 'Reason to re-enable?',
                      c.isActive ? 'Disable unused category' : 'Re-enable category',
                    )
                    if (!reason || reason.trim().length < 3) return
                    setBusy(true)
                    try {
                      await api.updateCategory(role, c.id, {
                        is_active: !c.isActive,
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
                  {c.isActive ? 'Disable' : 'Enable'}
                </Button>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </AppShell>
  )
}
