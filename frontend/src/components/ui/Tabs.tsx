import { clsx } from 'clsx'

export interface TabItem {
  id: string
  label: string
  count?: number
}

export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: TabItem[]
  active: string
  onChange: (id: string) => void
}) {
  return (
    <div className="flex gap-1 overflow-x-auto border-b border-border">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onChange(tab.id)}
          className={clsx(
            'relative whitespace-nowrap px-3 py-2.5 text-sm font-medium transition-colors',
            active === tab.id ? 'text-brand' : 'text-ink-muted hover:text-ink-secondary',
          )}
        >
          {tab.label}
          {typeof tab.count === 'number' && (
            <span className="ml-1.5 rounded bg-surface-muted px-1.5 py-0.5 text-[10px] text-ink-secondary">
              {tab.count}
            </span>
          )}
          {active === tab.id && (
            <span className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-brand" />
          )}
        </button>
      ))}
    </div>
  )
}
