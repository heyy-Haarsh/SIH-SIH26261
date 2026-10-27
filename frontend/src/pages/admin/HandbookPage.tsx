import { useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { Card, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input, Label, Textarea } from '@/components/ui/Input'
import { errorText } from '@/components/scrutiny/scrutinyUi'
import { useRole } from '@/app/RoleContext'
import { useRefreshable } from '@/hooks/useRefreshable'
import { formatDateTime } from '@/lib/format'
import { api } from '@/services/api'
import type { HandbookReferenceAdmin } from '@/types'

interface Form {
  reference_key: string
  edition: string
  section: string
  page: string
  title: string
  source_note: string
  verified: boolean
}

const BLANK: Form = {
  reference_key: '',
  edition: '',
  section: '',
  page: '',
  title: '',
  source_note: '',
  verified: false,
}

export function HandbookPage() {
  const { role } = useRole()
  const { data, loading, error, reload } = useRefreshable<HandbookReferenceAdmin[]>(
    () => api.listHandbookReferences(role),
    role,
  )
  const [form, setForm] = useState<Form>(BLANK)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  const complete = Boolean(form.edition.trim() && form.section.trim() && form.page.trim())

  function edit(ref: HandbookReferenceAdmin) {
    setForm({
      reference_key: ref.referenceKey,
      edition: ref.edition,
      section: ref.section,
      page: ref.page,
      title: ref.title,
      source_note: ref.sourceNote,
      verified: ref.verified,
    })
    setMsg(null)
  }

  async function save() {
    setBusy(true)
    setMsg(null)
    try {
      await api.saveHandbookReference(role, form)
      setMsg(`Saved ${form.reference_key}.`)
      setForm(BLANK)
      await reload()
    } catch (err) {
      setMsg(errorText(err, 'Could not save the reference'))
    } finally {
      setBusy(false)
    }
  }

  async function remove(ref: HandbookReferenceAdmin) {
    if (!window.confirm(`Delete the reference for ${ref.referenceKey}?`)) return
    setBusy(true)
    try {
      await api.deleteHandbookReference(role, ref.id)
      await reload()
    } catch (err) {
      setMsg(errorText(err, 'Could not delete the reference'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AppShell title="Handbook references" breadcrumbs={['Administrator', 'Handbook references']}>
      <DemoBanner>
        Officers and applicants only see a handbook edition, section and page for a finding when a
        reference below is complete <strong>and</strong> marked verified. Enter a reference only after
        checking it against the printed AICTE Approval Process Handbook. The system never invents one.
      </DemoBanner>
      {error && !data && (
        <p role="alert" className="mb-3 text-sm text-status-failed">
          {error}
        </p>
      )}
      {msg && (
        <div role="status" className="mb-4 rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2 text-xs">
          {msg}
        </div>
      )}
      <div className="grid gap-4 xl:grid-cols-3">
        <Card>
          <CardHeader
            title="Add or update a reference"
            description="Key is the rule code (e.g. SYN-RULE-003) or a document-check code"
          />
          <div className="space-y-2">
            <div>
              <Label>Reference key</Label>
              <Input
                value={form.reference_key}
                onChange={(e) => setForm((f) => ({ ...f, reference_key: e.target.value }))}
                placeholder="Rule or check code"
              />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div>
                <Label>Edition</Label>
                <Input
                  value={form.edition}
                  onChange={(e) => setForm((f) => ({ ...f, edition: e.target.value }))}
                  placeholder="e.g. 2025-26"
                />
              </div>
              <div>
                <Label>Section</Label>
                <Input value={form.section} onChange={(e) => setForm((f) => ({ ...f, section: e.target.value }))} />
              </div>
              <div>
                <Label>Page</Label>
                <Input value={form.page} onChange={(e) => setForm((f) => ({ ...f, page: e.target.value }))} />
              </div>
            </div>
            <div>
              <Label>Title</Label>
              <Input value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} />
            </div>
            <div>
              <Label>Where you checked it</Label>
              <Textarea
                rows={2}
                value={form.source_note}
                onChange={(e) => setForm((f) => ({ ...f, source_note: e.target.value }))}
                placeholder="Handbook title, copy or URL you verified against"
              />
            </div>
            <label className="flex items-start gap-2 text-xs text-ink-secondary">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={form.verified}
                disabled={!complete}
                onChange={(e) => setForm((f) => ({ ...f, verified: e.target.checked }))}
              />
              <span>
                I checked this reference against the handbook and it is correct.
                {!complete && ' (Edition, section and page are required first.)'}
              </span>
            </label>
            <div className="flex gap-2">
              <Button disabled={busy || !form.reference_key.trim()} onClick={() => void save()}>
                Save reference
              </Button>
              <Button variant="outline" onClick={() => setForm(BLANK)}>
                Clear
              </Button>
            </div>
          </div>
        </Card>

        <Card className="xl:col-span-2" padding={false}>
          <div className="px-5 pt-5">
            <CardHeader title="References" description={`${data?.length ?? 0} on file`} />
          </div>
          {loading && <p className="px-5 pb-5 text-sm text-ink-muted">Loading…</p>}
          <ul className="divide-y divide-border">
            {(data ?? []).map((ref) => (
              <li key={ref.id} className="flex flex-wrap items-start justify-between gap-3 px-5 py-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <code className="text-sm font-medium text-ink">{ref.referenceKey}</code>
                    <Badge tone={ref.verified ? 'pass' : 'warning'}>
                      {ref.verified ? 'Verified' : 'Not verified — not shown to users'}
                    </Badge>
                  </div>
                  <p className="text-xs text-ink-secondary">
                    {[ref.edition, ref.section && `§${ref.section}`, ref.page && `p. ${ref.page}`]
                      .filter(Boolean)
                      .join(' · ') || 'Incomplete'}
                    {ref.title ? ` — ${ref.title}` : ''}
                  </p>
                  {ref.verified && ref.verifiedBy && (
                    <p className="text-[11px] text-ink-muted">
                      Verified by {ref.verifiedBy}
                      {ref.verifiedAt ? ` on ${formatDateTime(ref.verifiedAt)}` : ''}
                    </p>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => edit(ref)}>
                    Edit
                  </Button>
                  <Button size="sm" variant="outline" disabled={busy} onClick={() => void remove(ref)}>
                    Delete
                  </Button>
                </div>
              </li>
            ))}
            {data && data.length === 0 && (
              <li className="px-5 pb-6 text-sm text-ink-muted">
                No references yet. Until you add verified ones, every finding says its handbook reference is
                not verified.
              </li>
            )}
          </ul>
        </Card>
      </div>
    </AppShell>
  )
}
