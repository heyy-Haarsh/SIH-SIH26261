import { useState, type ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'

export function AppShell({
  title,
  description,
  breadcrumbs,
  children,
  actions,
}: {
  title: string
  description?: string
  breadcrumbs?: string[]
  children: ReactNode
  actions?: ReactNode
}) {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="flex h-full" style={{ background: '#F5F5F5' }}>
      {/* Desktop sidebar */}
      <div className="hidden lg:block">
        <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />
      </div>

      {/* Mobile sidebar overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/20"
            aria-label="Close navigation"
            onClick={() => setMobileOpen(false)}
          />
          <div className="relative z-10 h-full">
            <Sidebar collapsed={false} onToggle={() => setMobileOpen(false)} />
          </div>
        </div>
      )}

      {/* Main content column */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top bar with breadcrumbs */}
        <TopBar
          title={title}
          description={description}
          breadcrumbs={breadcrumbs}
          onMenuClick={() => setMobileOpen(true)}
        />

        {/* Scrollable page area */}
        <main className="scrollbar-thin flex-1 overflow-y-auto">
          {/* Page header: big title + primary action */}
          <div
            className="flex items-start justify-between gap-4 px-8 pb-5 pt-8"
            style={{ background: '#F5F5F5' }}
          >
            <div className="min-w-0">
              <h1
                className="text-[28px] font-bold leading-tight tracking-tight"
                style={{ color: '#111111' }}
              >
                {title}
              </h1>
              {description && (
                <p className="mt-1 text-sm" style={{ color: '#888888' }}>
                  {description}
                </p>
              )}
            </div>
            {actions && (
              <div className="flex shrink-0 items-center gap-2 pt-1">{actions}</div>
            )}
          </div>

          {/* Page content */}
          <div className="px-8 pb-8">{children}</div>
        </main>
      </div>
    </div>
  )
}
