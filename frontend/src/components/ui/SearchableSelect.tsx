import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { ChevronDown } from 'lucide-react'

export type SearchOption = {
  value: string
  label: string
  hint?: string
}

/** Filterable list. Choosing an option closes the menu and shows that label. */
export function SearchableSelect({
  id,
  label,
  options,
  value,
  onChange,
  placeholder = 'Search…',
  empty = 'No matches.',
}: {
  id?: string
  label: string
  options: SearchOption[]
  value: string
  onChange: (value: string) => void
  placeholder?: string
  empty?: string
}) {
  const autoId = useId()
  const fieldId = id ?? autoId
  const listId = `${fieldId}-list`
  const root = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const selected = options.find((o) => o.value === value)

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return options
    return options.filter(
      (o) => o.label.toLowerCase().includes(q) || (o.hint ?? '').toLowerCase().includes(q),
    )
  }, [options, query])

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!root.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  return (
    <div ref={root} className="relative">
      <label htmlFor={fieldId} className="mb-1.5 block text-xs font-medium text-ink-secondary">
        {label}
      </label>
      <div className="relative">
        <input
          id={fieldId}
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          value={open ? query : (selected?.label ?? '')}
          placeholder={selected && !open ? selected.label : placeholder}
          onClick={() => setOpen(true)}
          onFocus={() => {
            setOpen(true)
            setQuery('')
          }}
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(true)
          }}
          onKeyDown={(e) => {
            if (e.key === 'Escape') setOpen(false)
            if (e.key === 'Enter' && matches[0]) {
              e.preventDefault()
              onChange(matches[0].value)
              setOpen(false)
            }
          }}
          className="h-10 w-full rounded-[var(--radius-md)] border border-border-strong bg-white px-3 pr-9 text-sm text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand/15"
        />
        <ChevronDown size={16} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink-muted" />
      </div>
      {open && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-20 mt-1 max-h-64 w-full overflow-y-auto rounded-[var(--radius-md)] border border-border-strong bg-white py-1 shadow-[0_8px_24px_rgba(0,0,0,0.08)]"
        >
          {matches.length === 0 && <li className="px-3 py-2 text-sm text-ink-muted">{empty}</li>}
          {matches.map((o) => (
            <li key={o.value}>
              <button
                type="button"
                role="option"
                aria-selected={o.value === value}
                className={`w-full px-3 py-2 text-left hover:bg-surface ${o.value === value ? 'bg-brand-soft' : ''}`}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  onChange(o.value)
                  setOpen(false)
                  setQuery('')
                }}
              >
                <span className="block text-sm font-medium text-ink">{o.label}</span>
                {o.hint && <span className="mt-0.5 block text-xs text-ink-muted">{o.hint}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
