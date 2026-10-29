import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Plus, Search } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Dialog } from '@/components/ui/Dialog'
import { EmptyState } from '@/components/ui/EmptyState'
import { Input, Label, Select, Textarea } from '@/components/ui/Input'
import { Loading, Notice } from '@/components/ui/Notice'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import { CONFIG_STATE } from '@/lib/configLabels'
import { formatDateTime } from '@/lib/format'
import type { ConfigCategorySummary } from '@/types'

export function CategoriesPage() {
  const { role } = useRole()
  const navigate = useNavigate()
  const [items, setItems] = useState<ConfigCategorySummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const [state, setState] = useState('')
  const [creating, setCreating] = useState(false)

  const load = useCallback(() => {
    setError(null)
    api
      .cfgListCategories(role, { q, status, state })
      .then(setItems)
      .catch((err) => {
        setItems(null)
        setError(err instanceof ApiError ? err.message : 'Categories could not be loaded.')
      })
  }, [role, q, status, state])

  useEffect(() => {
    const t = window.setTimeout(load, 200)
    return () => window.clearTimeout(t)
  }, [load])

  const filtered = Boolean(q || status || state)

  return (
    <AppShell
      title="Application Categories"
      description="Each category is an application purpose. Its information fields, documents and rules are configured here."
      breadcrumbs={['Administration', 'Application Categories']}
      actions={
        <Button leftIcon={<Plus size={16} strokeWidth={1.5} />} onClick={() => setCreating(true)}>
          Create Category
        </Button>
      }
    >
      <div className="mx-auto max-w-7xl space-y-4">
        <Card padding={false}>
          <div className="grid gap-3 border-b border-border p-4 md:grid-cols-[1fr_180px_220px]">
            <div className="relative">
              <Label htmlFor="cat-search">Search by name or identifier</Label>
              <Search size={16} strokeWidth={1.5} className="pointer-events-none absolute left-3 top-[34px] text-ink-muted" />
              <Input
                id="cat-search"
                className="pl-9"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="e.g. EOA or Extension"
              />
            </div>
            <div>
              <Label htmlFor="cat-status">Status</Label>
              <Select id="cat-status" value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="">All</option>
                <option value="active">Available to institutions</option>
                <option value="inactive">Not available</option>
              </Select>
            </div>
            <div>
              <Label htmlFor="cat-state">Configuration state</Label>
              <Select id="cat-state" value={state} onChange={(e) => setState(e.target.value)}>
                <option value="">All</option>
                <option value="published">Published</option>
                <option value="unpublished_changes">Unpublished changes</option>
                <option value="unpublished">Not published</option>
              </Select>
            </div>
          </div>

          {error && (
            <div className="p-4">
              <Notice tone="error" title="Could not load categories" onRetry={load}>
                {error}
              </Notice>
            </div>
          )}
          {!error && items === null && <SkeletonTable rows={5} cols={5} />}
          {!error && items?.length === 0 && (
            <div className="p-4">
              <EmptyState
                title={filtered ? 'No categories match these filters' : 'No categories yet'}
                description={
                  filtered
                    ? 'Clear the search or filters to see every category.'
                    : 'Create the first category to define an application purpose.'
                }
                action={
                  filtered ? (
                    <Button
                      variant="outline"
                      onClick={() => {
                        setQ('')
                        setStatus('')
                        setState('')
                      }}
                    >
                      Clear filters
                    </Button>
                  ) : (
                    <Button onClick={() => setCreating(true)}>Create Category</Button>
                  )
                }
              />
            </div>
          )}

          {!error && items && items.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border text-xs text-ink-muted">
                  <tr>
                    <th className="px-4 py-2.5 font-medium">Category</th>
                    <th className="px-3 py-2.5 font-medium">Information fields</th>
                    <th className="px-3 py-2.5 font-medium">Documents</th>
                    <th className="px-3 py-2.5 font-medium">Rules</th>
                    <th className="px-3 py-2.5 font-medium">Configuration</th>
                    <th className="px-3 py-2.5 font-medium">Updated</th>
                    <th className="px-4 py-2.5" />
                  </tr>
                </thead>
                <tbody>
                  {items.map((c) => {
                    const st = CONFIG_STATE[c.configState]
                    return (
                      <tr key={c.id} className="h-11 border-b border-border last:border-0 hover:bg-surface">
                        <td className="px-4 py-3 align-top">
                          <Link to={`/admin/categories/${c.id}`} className="font-medium text-ink hover:underline">
                            {c.name}
                          </Link>
                          <div className="mono text-ink-muted">{c.code}</div>
                          {c.description && (
                            <p className="mt-0.5 max-w-sm truncate text-xs text-ink-muted" title={c.description}>
                              {c.description}
                            </p>
                          )}
                        </td>
                        <td className="px-3 py-3 align-top">{c.infoFieldCount}</td>
                        <td className="px-3 py-3 align-top text-xs">
                          {c.requiredDocuments} required
                          <br />
                          {c.optionalDocuments} optional
                        </td>
                        <td className="px-3 py-3 align-top text-xs">
                          {c.activeRules} active
                          <br />
                          {c.draftRules} draft
                          <span className="text-ink-muted"> · {c.totalRules} total</span>
                        </td>
                        <td className="px-3 py-3 align-top">
                          <div className="flex flex-wrap items-center gap-1.5">
                            <Badge tone={st.tone} title={st.hint}>
                              {st.label}
                            </Badge>
                            {c.configVersion != null && <span className="mono text-ink-muted">v{c.configVersion}</span>}
                          </div>
                          <div className="mt-1 text-[11px] text-ink-muted">
                            {c.isActive ? 'Available to institutions' : 'Not available to institutions'}
                          </div>
                        </td>
                        <td className="px-3 py-3 align-top text-xs text-ink-muted">{formatDateTime(c.updatedAt)}</td>
                        <td className="px-4 py-3 text-right align-top">
                          <Button size="sm" variant="outline" onClick={() => navigate(`/admin/categories/${c.id}`)}>
                            Open
                          </Button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      <CreateCategoryDialog
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={(id) => navigate(`/admin/categories/${id}`)}
      />
    </AppShell>
  )
}

function CreateCategoryDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean
  onClose: () => void
  onCreated: (id: string) => void
}) {
  const { role } = useRole()
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      const created = await api.cfgCreateCategory(role, { code: code.trim(), name: name.trim(), description })
      onCreated(created.id)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The category could not be created.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      dismissible={!busy}
      title="Create Category"
      subtitle="A new category starts unpublished and is not offered to institutions until you publish and enable it."
      width="max-w-lg"
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={busy || code.trim().length < 2 || name.trim().length < 2}>
            {busy ? 'Creating' : 'Create Category'}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div>
          <Label htmlFor="new-code">Identifier</Label>
          <Input
            id="new-code"
            className="mono uppercase"
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            placeholder="NEW-COLLEGE"
          />
          <p className="mt-1 text-[11px] text-ink-muted">
            Permanent. 2 to 64 characters: A–Z, 0–9, hyphen, underscore.
          </p>
        </div>
        <div>
          <Label htmlFor="new-name">Name</Label>
          <Input id="new-name" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="new-desc">Application purpose</Label>
          <Textarea
            id="new-desc"
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What an institution applies for with this category."
          />
        </div>
        {error && (
          <Notice tone="error" title="Could not create the category">
            {error}
          </Notice>
        )}
      </div>
    </Dialog>
  )
}
