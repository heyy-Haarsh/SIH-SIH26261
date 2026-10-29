import { useEffect, useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Label, Select, Textarea } from '@/components/ui/Input'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import type { AdminCategory } from '@/types'

export function RequirementsPage() {
  const { role } = useRole()
  const [items, setItems] = useState<AdminCategory[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [docsJson, setDocsJson] = useState('[]')
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function load() {
    api
      .listCategories(role)
      .then((cats) => {
        setItems(cats)
        if (!selectedId && cats[0]) {
          setSelectedId(cats[0].id)
          setDocsJson(JSON.stringify(cats[0].requiredDocuments ?? [], null, 2))
        }
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : 'Failed to load categories'),
      )
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role])

  const selected = items.find((c) => c.id === selectedId)

  return (
    <AppShell title="Document Requirements" breadcrumbs={['Regional Officer', 'Requirements']}>
      <DemoBanner>
        Edit the checklist JSON for a category. Changes are audited with a reason. Prior applications
        keep their historical requirement snapshots on the application record where applicable.
      </DemoBanner>

      {error && (
        <div className="mb-4 rounded-[var(--radius-md)] border border-[#e3d8bd] bg-status-warning-bg px-3 py-2 text-xs text-status-warning">
          {error}
        </div>
      )}
      {msg && (
        <div className="mb-4 rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2 text-xs">
          {msg}
        </div>
      )}

      <Card>
        <CardHeader title="Requirement matrix" description="Per application category" />
        <div className="mb-3 max-w-md">
          <Label>Category</Label>
          <Select
            value={selectedId}
            onChange={(e) => {
              const id = e.target.value
              setSelectedId(id)
              const cat = items.find((c) => c.id === id)
              setDocsJson(JSON.stringify(cat?.requiredDocuments ?? [], null, 2))
            }}
          >
            {items.map((c) => (
              <option key={c.id} value={c.id}>
                {c.code} — {c.name}
              </option>
            ))}
          </Select>
        </div>
        <Label>required_documents JSON</Label>
        <Textarea rows={14} value={docsJson} onChange={(e) => setDocsJson(e.target.value)} />
        <div className="mt-3">
          <Button
            disabled={busy || !selected}
            onClick={async () => {
              if (!selected) return
              const reason = window.prompt('Reason for this requirements change?', 'Update checklist')
              if (!reason || reason.trim().length < 3) return
              setBusy(true)
              setMsg(null)
              try {
                const required_documents = JSON.parse(docsJson)
                await api.updateCategory(role, selected.id, {
                  required_documents,
                  change_reason: reason.trim(),
                })
                setMsg(`Updated requirements for ${selected.code}`)
                load()
              } catch (err) {
                setMsg(err instanceof Error ? err.message : 'Save failed')
              } finally {
                setBusy(false)
              }
            }}
          >
            Save requirements
          </Button>
        </div>
      </Card>
    </AppShell>
  )
}
