import { useState, type ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { clsx } from 'clsx'

export function AppShell({
  title,
  breadcrumbs,
  children,
  actions,
}: {
  title: string
  breadcrumbs?: string[]
  children: ReactNode
  actions?: ReactNode
}) {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="flex h-full bg-surface">
      <div className="hidden lg:block">
        <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />
      </div>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/30"
            aria-label="Close navigation"
            onClick={() => setMobileOpen(false)}
          />
          <div className="relative z-10 h-full">
            <Sidebar collapsed={false} onToggle={() => setMobileOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          title={title}
          breadcrumbs={breadcrumbs}
          onMenuClick={() => setMobileOpen(true)}
        />
        {actions && (
          <div className="flex items-center justify-end gap-2 border-b border-border bg-white px-4 py-2 md:px-6">
            {actions}
          </div>
        )}
        <main className={clsx('scrollbar-thin flex-1 overflow-y-auto p-4 md:p-6')}>{children}</main>
      </div>
    </div>
  )
}
