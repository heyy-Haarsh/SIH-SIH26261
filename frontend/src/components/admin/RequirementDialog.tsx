import { useEffect, useState } from 'react'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { Input, Label, Textarea } from '@/components/ui/Input'
import { Notice } from '@/components/ui/Notice'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import type { ConfigRequirement } from '@/types'

const FILE_TYPES = ['pdf', 'png', 'jpg', 'jpeg']

/** Add a document requirement, or edit one. The identifier is permanent once created. */
export function RequirementDialog({
  open,
  onClose,
  categoryId,
  categoryName,
  requirement,
  onSaved,
}: {
  open: boolean
  onClose: () => void
  categoryId: string
  categoryName: string
  requirement: ConfigRequirement | null
  onSaved: () => void
}) {
  const { role } = useRole()
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [mandatory, setMandatory] = useState(true)
  const [types, setTypes] = useState<string[]>(['pdf'])
  const [maxSize, setMaxSize] = useState('')
  const [expected, setExpected] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [impactMessage, setImpactMessage] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setError(null)
    setImpactMessage(null)
    setCode(requirement?.code ?? '')
    setName(requirement?.name ?? '')
    setDescription(requirement?.description ?? '')
    setMandatory(requirement?.mandatory ?? true)
    setTypes(requirement?.allowedTypes?.length ? requirement.allowedTypes : ['pdf'])
    setMaxSize(requirement?.maxSizeMb != null ? String(requirement.maxSizeMb) : '')
    setExpected((requirement?.expectedFields ?? []).join(', '))
  }, [open, requirement])

  function toggleType(t: string) {
    setTypes((cur) => (cur.includes(t) ? cur.filter((x) => x !== t) : [...cur, t]))
  }

  async function save(acknowledgeImpact: boolean) {
    setBusy(true)
    setError(null)
    const payload: Record<string, unknown> = {
      name: name.trim(),
      description: description.trim(),
      mandatory,
      allowed_types: types,
      max_size_mb: maxSize.trim() === '' ? null : Number(maxSize),
      expected_fields: expected
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
    }
    try {
      if (requirement) {
        await api.cfgUpdateRequirement(role, requirement.id, { ...payload, acknowledge_impact: acknowledgeImpact })
      } else {
        await api.cfgCreateRequirement(role, categoryId, { ...payload, code: code.trim().toUpperCase() })
      }
      onSaved()
      onClose()
    } catch (err) {
      if (err instanceof ApiError && err.code === 'impact_not_acknowledged') {
        setImpactMessage(err.message)
      } else {
        setError(err instanceof ApiError ? err.message : 'The document requirement could not be saved.')
      }
    } finally {
      setBusy(false)
    }
  }

  const sizeInvalid = maxSize.trim() !== '' && !/^\d{1,3}$/.test(maxSize.trim())
  const invalid = name.trim().length < 2 || types.length === 0 || sizeInvalid || (!requirement && code.trim().length < 2)

  return (
    <Dialog
      open={open}
      onClose={onClose}
      dismissible={!busy}
      title={requirement ? 'Edit Document Requirement' : 'Add Document Requirement'}
      subtitle={<>Category: {categoryName}</>}
      width="max-w-xl"
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          {impactMessage ? (
            <Button onClick={() => save(true)} disabled={busy}>
              Confirm and save
            </Button>
          ) : (
            <Button onClick={() => save(false)} disabled={busy || invalid}>
              {busy ? 'Saving' : 'Save'}
            </Button>
          )}
        </>
      }
    >
      <div className="space-y-4">
        {impactMessage && (
          <Notice tone="warning" title="Existing applications are affected">
            {impactMessage}
          </Notice>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="req-code">Identifier</Label>
            <Input
              id="req-code"
              className="mono uppercase"
              value={code}
              disabled={Boolean(requirement)}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              placeholder="FIRE_NOC"
            />
            <p className="mt-1 text-[11px] text-ink-muted">Permanent. Results and applications refer to it.</p>
          </div>
          <div>
            <Label htmlFor="req-name">Document name</Label>
            <Input id="req-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
        </div>
        <div>
          <Label htmlFor="req-desc">Guidance shown to the institution</Label>
          <Textarea id="req-desc" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
        <fieldset>
          <legend className="mb-1.5 text-xs font-medium text-ink-secondary">Requirement</legend>
          <div className="flex gap-4 text-sm">
            <label className="flex items-center gap-2">
              <input type="radio" name="mandatory" checked={mandatory} onChange={() => setMandatory(true)} />
              Required
            </label>
            <label className="flex items-center gap-2">
              <input type="radio" name="mandatory" checked={!mandatory} onChange={() => setMandatory(false)} />
              Optional
            </label>
          </div>
        </fieldset>
        <fieldset>
          <legend className="mb-1.5 text-xs font-medium text-ink-secondary">Accepted file types</legend>
          <div className="flex flex-wrap gap-4 text-sm">
            {FILE_TYPES.map((t) => (
              <label key={t} className="flex items-center gap-2">
                <input type="checkbox" checked={types.includes(t)} onChange={() => toggleType(t)} />
                <span className="mono">{t}</span>
              </label>
            ))}
          </div>
        </fieldset>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="req-size">Maximum file size (MB)</Label>
            <Input
              id="req-size"
              inputMode="numeric"
              value={maxSize}
              onChange={(e) => setMaxSize(e.target.value)}
              placeholder="Platform default"
            />
            {sizeInvalid && <p className="mt-1 text-[11px] text-status-failed">Enter a whole number of MB.</p>}
          </div>
          <div>
            <Label htmlFor="req-fields">Fields to extract</Label>
            <Input
              id="req-fields"
              value={expected}
              onChange={(e) => setExpected(e.target.value)}
              placeholder="registration_number, valid_until"
            />
            <p className="mt-1 text-[11px] text-ink-muted">Comma separated. Rules can only check these fields.</p>
          </div>
        </div>
        {error && (
          <Notice tone="error" title="Could not save">
            {error}
          </Notice>
        )}
      </div>
    </Dialog>
  )
}
