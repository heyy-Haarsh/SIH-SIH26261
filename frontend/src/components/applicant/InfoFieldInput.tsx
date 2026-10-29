import { Input, Label, Select, Textarea } from '@/components/ui/Input'
import type { PublicInfoField } from '@/types'

/** Renders one configured information field. The server remains the authority on validity. */
export function InfoFieldInput({
  field,
  value,
  error,
  disabled,
  onChange,
}: {
  field: PublicInfoField
  value: unknown
  error?: string
  disabled?: boolean
  onChange: (value: unknown) => void
}) {
  const id = `info-${field.key}`
  const helpId = `${id}-help`
  const text = value == null ? '' : String(value)
  const common = {
    id,
    disabled,
    'aria-invalid': Boolean(error),
    'aria-describedby': helpId,
  }

  return (
    <div>
      {field.type === 'boolean' ? (
        <label className="flex items-start gap-2 text-sm text-ink">
          <input
            type="checkbox"
            className="mt-0.5"
            checked={value === true}
            disabled={disabled}
            onChange={(e) => onChange(e.target.checked)}
            aria-describedby={helpId}
          />
          <span>
            {field.label}
            {field.required && <span className="text-status-failed"> *</span>}
          </span>
        </label>
      ) : (
        <>
          <Label htmlFor={id}>
            {field.label}
            {field.required && <span className="text-status-failed"> *</span>}
          </Label>
          {field.type === 'textarea' && (
            <Textarea {...common} rows={3} value={text} maxLength={field.maxLength ?? undefined} onChange={(e) => onChange(e.target.value)} />
          )}
          {field.type === 'select' && (
            <Select {...common} value={text} onChange={(e) => onChange(e.target.value)}>
              <option value="">Select</option>
              {field.options.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </Select>
          )}
          {field.type === 'number' && (
            <Input
              {...common}
              type="number"
              inputMode="decimal"
              min={field.min ?? undefined}
              max={field.max ?? undefined}
              value={text}
              onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))}
            />
          )}
          {field.type === 'date' && (
            <Input {...common} type="date" value={text} onChange={(e) => onChange(e.target.value)} />
          )}
          {(field.type === 'text' || field.type === 'email') && (
            <Input
              {...common}
              type={field.type === 'email' ? 'email' : 'text'}
              value={text}
              maxLength={field.maxLength ?? undefined}
              onChange={(e) => onChange(e.target.value)}
            />
          )}
        </>
      )}
      <p id={helpId} className={`mt-1 text-[11px] ${error ? 'text-status-failed' : 'text-ink-muted'}`}>
        {error ?? field.helpText}
      </p>
    </div>
  )
}

/** Client-side hints only (required and empty). Everything else is validated by the server. */
export function missingRequired(fields: PublicInfoField[], values: Record<string, unknown>): Record<string, string> {
  const out: Record<string, string> = {}
  for (const f of fields) {
    if (!f.required) continue
    const v = values[f.key]
    const empty = v == null || v === '' || (f.type === 'boolean' && v !== true)
    if (empty) out[f.key] = f.type === 'boolean' ? 'This confirmation is required.' : 'This information is required.'
  }
  return out
}
