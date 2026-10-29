import { useEffect, useState } from 'react'
import { ArrowDown, ArrowUp, Plus, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input, Label, Select } from '@/components/ui/Input'
import { Notice } from '@/components/ui/Notice'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import { FIELD_TYPE_LABEL } from '@/lib/configLabels'
import type { InfoFieldDef, InfoFieldType } from '@/types'

const RESERVED = ['institution_name', 'program_name', 'academic_year', 'category_code', 'contact_email']

function keyFromLabel(label: string): string {
  return label
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 48)
}

/** Edits the category's information-field schema. Keys of already-saved fields stay fixed. */
export function InfoFieldsEditor({
  categoryId,
  fields,
  supportedTypes,
  onSaved,
}: {
  categoryId: string
  fields: InfoFieldDef[]
  supportedTypes: InfoFieldType[]
  onSaved: () => void
}) {
  const { role } = useRole()
  const [draft, setDraft] = useState<InfoFieldDef[]>(fields)
  const [saved, setSaved] = useState<Set<string>>(new Set(fields.map((f) => f.key)))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)

  useEffect(() => {
    setDraft(fields)
    setSaved(new Set(fields.map((f) => f.key)))
  }, [fields])

  const dirty = JSON.stringify(draft) !== JSON.stringify(fields)
  const keys = draft.map((f) => f.key)
  const problems: string[] = []
  draft.forEach((f, i) => {
    if (!f.label.trim()) problems.push(`Field ${i + 1} needs a label.`)
    if (!/^[a-z][a-z0-9_]{1,47}$/.test(f.key)) problems.push(`Field ${i + 1} needs a valid key.`)
    if (RESERVED.includes(f.key)) problems.push(`“${f.key}” is reserved by the platform.`)
    if (keys.indexOf(f.key) !== i) problems.push(`Key “${f.key}” is used twice.`)
    if (f.type === 'select' && !(f.options ?? []).length) problems.push(`“${f.label || f.key}” needs at least one option.`)
  })

  function update(i: number, patch: Partial<InfoFieldDef>) {
    setNote(null)
    setDraft((cur) => cur.map((f, idx) => (idx === i ? { ...f, ...patch } : f)))
  }

  function move(i: number, delta: number) {
    setDraft((cur) => {
      const next = [...cur]
      const j = i + delta
      if (j < 0 || j >= next.length) return cur
      ;[next[i], next[j]] = [next[j], next[i]]
      return next
    })
  }

  async function save() {
    setBusy(true)
    setError(null)
    try {
      await api.cfgSetInfoFields(role, categoryId, draft)
      setNote('Information fields saved to the working copy. Publish to make them visible to institutions.')
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The fields could not be saved.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      {draft.length === 0 && (
        <p className="text-sm text-ink-muted">
          No additional information is collected for this category. Institution name, programme, academic year and
          contact email are always collected.
        </p>
      )}
      {draft.map((f, i) => {
        const locked = saved.has(f.key)
        return (
          <div key={i} className="rounded-[var(--radius-md)] border border-border p-3">
            <div className="grid gap-3 md:grid-cols-[1.4fr_1fr_1fr_auto]">
              <div>
                <Label htmlFor={`f-label-${i}`}>Label</Label>
                <Input
                  id={`f-label-${i}`}
                  value={f.label}
                  onChange={(e) =>
                    update(i, locked ? { label: e.target.value } : { label: e.target.value, key: keyFromLabel(e.target.value) })
                  }
                />
              </div>
              <div>
                <Label htmlFor={`f-key-${i}`}>Key</Label>
                <Input id={`f-key-${i}`} className="mono text-xs" value={f.key} disabled={locked} onChange={(e) => update(i, { key: e.target.value })} />
              </div>
              <div>
                <Label htmlFor={`f-type-${i}`}>Type</Label>
                <Select id={`f-type-${i}`} value={f.type} onChange={(e) => update(i, { type: e.target.value as InfoFieldType })}>
                  {supportedTypes.map((t) => (
                    <option key={t} value={t}>
                      {FIELD_TYPE_LABEL[t] ?? t}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="flex items-end gap-1">
                <Button size="sm" variant="ghost" aria-label="Move up" disabled={i === 0} onClick={() => move(i, -1)}>
                  <ArrowUp size={16} strokeWidth={1.5} />
                </Button>
                <Button size="sm" variant="ghost" aria-label="Move down" disabled={i === draft.length - 1} onClick={() => move(i, 1)}>
                  <ArrowDown size={16} strokeWidth={1.5} />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  aria-label={`Remove ${f.label || 'field'}`}
                  onClick={() => setDraft((cur) => cur.filter((_, idx) => idx !== i))}
                >
                  <Trash2 size={16} strokeWidth={1.5} />
                </Button>
              </div>
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-[1fr_auto]">
              <div>
                <Label htmlFor={`f-help-${i}`}>Help text</Label>
                <Input id={`f-help-${i}`} value={f.help_text ?? ''} onChange={(e) => update(i, { help_text: e.target.value })} />
              </div>
              <label className="flex items-end gap-2 pb-2 text-sm">
                <input type="checkbox" checked={Boolean(f.required)} onChange={(e) => update(i, { required: e.target.checked })} />
                Required
              </label>
            </div>
            {f.type === 'select' && (
              <div className="mt-3">
                <Label htmlFor={`f-opt-${i}`}>Options (one per line)</Label>
                <textarea
                  id={`f-opt-${i}`}
                  rows={3}
                  className="w-full rounded-[var(--radius-md)] border border-border px-3 py-2 text-sm"
                  value={(f.options ?? []).join('\n')}
                  onChange={(e) => update(i, { options: e.target.value.split('\n').map((s) => s.trim()).filter(Boolean) })}
                />
              </div>
            )}
            {(f.type === 'text' || f.type === 'textarea') && (
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <div>
                  <Label htmlFor={`f-minl-${i}`}>Minimum length</Label>
                  <Input id={`f-minl-${i}`} inputMode="numeric" value={f.min_length ?? ''} onChange={(e) => update(i, { min_length: e.target.value ? Number(e.target.value) : undefined })} />
                </div>
                <div>
                  <Label htmlFor={`f-maxl-${i}`}>Maximum length</Label>
                  <Input id={`f-maxl-${i}`} inputMode="numeric" value={f.max_length ?? ''} onChange={(e) => update(i, { max_length: e.target.value ? Number(e.target.value) : undefined })} />
                </div>
              </div>
            )}
            {f.type === 'number' && (
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <div>
                  <Label htmlFor={`f-min-${i}`}>Minimum value</Label>
                  <Input id={`f-min-${i}`} inputMode="decimal" value={f.min ?? ''} onChange={(e) => update(i, { min: e.target.value !== '' ? Number(e.target.value) : undefined })} />
                </div>
                <div>
                  <Label htmlFor={`f-max-${i}`}>Maximum value</Label>
                  <Input id={`f-max-${i}`} inputMode="decimal" value={f.max ?? ''} onChange={(e) => update(i, { max: e.target.value !== '' ? Number(e.target.value) : undefined })} />
                </div>
              </div>
            )}
          </div>
        )
      })}

      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="outline"
          leftIcon={<Plus size={16} strokeWidth={1.5} />}
          onClick={() => setDraft((cur) => [...cur, { key: '', label: '', type: 'text', required: false }])}
        >
          Add field
        </Button>
        <Button onClick={save} disabled={busy || !dirty || problems.length > 0}>
          {busy ? 'Saving' : 'Save fields'}
        </Button>
        {dirty && <span className="text-xs text-status-warning">Unsaved changes</span>}
      </div>

      {problems.length > 0 && dirty && (
        <Notice tone="warning" title="Resolve before saving">
          <ul className="ml-4 list-disc">
            {Array.from(new Set(problems)).map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </Notice>
      )}
      {note && <Notice tone="success">{note}</Notice>}
      {error && <Notice tone="error">{error}</Notice>}
    </div>
  )
}
