import { useEffect, useState } from 'react'
import { clsx } from 'clsx'
import { ChevronLeft, ChevronRight, ShieldCheck } from 'lucide-react'
import { NavLink, useLocation } from 'react-router-dom'
import { useRole } from '@/app/RoleContext'
import { NAV_BY_ROLE, ROLE_HOME } from '@/lib/nav'
import { api } from '@/services/api'

export function Sidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean
  onToggle: () => void
}) {
  const { role } = useRole()
  const items = NAV_BY_ROLE[role]
  const location = useLocation()
  const [badges, setBadges] = useState<Record<string, number>>({})

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        if (role === 'regional_officer') {
          const queue = await api.getDelegationQueue(role)
          if (!cancelled) setBadges({ unassigned: queue.length })
        } else if (role === 'officer') {
          const apps = await api.listApplications(role)
          const mine = apps.filter(
            (a) =>
              a.stage === 'awaiting_scrutiny' ||
              a.stage === 'under_scrutiny' ||
              a.status === 'submitted' ||
              a.status === 'processing',
          )
          if (!cancelled) setBadges({ myQueue: mine.length })
        } else if (!cancelled) {
          setBadges({})
        }
      } catch {
        if (!cancelled) setBadges({})
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [role, location.pathname])

  return (
    <aside
      className={clsx(
        'flex h-full flex-col border-r border-border bg-white transition-[width] duration-200',
        collapsed ? 'w-[72px]' : 'w-[240px]',
      )}
    >
      <div className={clsx('flex h-14 items-center border-b border-border px-4', collapsed && 'justify-center px-2')}>
        <div className="flex items-center gap-2.5 overflow-hidden">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand text-white">
            <ShieldCheck size={16} />
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold tracking-tight text-ink">PRAMAN</div>
              <div className="truncate text-[10px] uppercase tracking-wider text-ink-muted">
                Compliance Platform
              </div>
            </div>
          )}
        </div>
      </div>

      <nav className="scrollbar-thin flex-1 space-y-0.5 overflow-y-auto p-2">
        {items.map((item, index) => (
          <div key={item.path}>
            {item.section && !collapsed && (
              <div
                className={clsx(
                  'px-2.5 pb-1 text-[10px] font-semibold uppercase tracking-wider text-ink-muted',
                  index === 0 ? 'pt-1' : 'pt-3',
                )}
              >
                {item.section}
              </div>
            )}
            {item.section && collapsed && index > 0 && (
              <div className="mx-2 my-2 border-t border-border" />
            )}
            <NavLink
              to={item.path}
              end={item.path === ROLE_HOME[role]}
              title={collapsed ? item.label : undefined}
              className={({ isActive }) => {
                const active =
                  item.path === '/applicant/applications'
                    ? isActive && location.pathname !== '/applicant/applications/new'
                    : isActive
                return clsx(
                  'flex items-center gap-2.5 rounded-[var(--radius-md)] px-2.5 py-2 text-sm font-medium transition-colors',
                  collapsed && 'justify-center px-0',
                  active
                    ? 'bg-brand-soft text-brand'
                    : 'text-ink-secondary hover:bg-surface-muted hover:text-ink',
                )
              }}
            >
              <item.icon size={18} className="shrink-0" />
              {!collapsed && (
                <span className="flex min-w-0 flex-1 items-center justify-between gap-2">
                  <span className="truncate">{item.label}</span>
                  {item.badgeKey && (badges[item.badgeKey] ?? 0) > 0 && (
                    <span className="rounded-full bg-brand px-1.5 py-0.5 text-[10px] font-semibold text-white">
                      {badges[item.badgeKey]}
                    </span>
                  )}
                </span>
              )}
              {collapsed && item.badgeKey && (badges[item.badgeKey] ?? 0) > 0 && (
                <span className="absolute ml-5 mt-[-18px] h-2 w-2 rounded-full bg-brand" />
              )}
            </NavLink>
          </div>
        ))}
      </nav>

      <div className="border-t border-border p-2">
        <button
          type="button"
          onClick={onToggle}
          className="flex w-full items-center justify-center gap-2 rounded-[var(--radius-md)] px-2 py-2 text-xs text-ink-muted hover:bg-surface-muted"
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          {!collapsed && <span>Collapse</span>}
        </button>
      </div>
    </aside>
  )
}
