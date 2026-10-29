import { useEffect, useState } from 'react'
import { clsx } from 'clsx'
import { Settings, HelpCircle } from 'lucide-react'
import { AicteMark } from './AicteMark'
import { NavLink, useLocation } from 'react-router-dom'
import { useRole } from '@/app/RoleContext'
import { NAV_BY_ROLE, ROLE_HOME } from '@/lib/nav'
import { api } from '@/services/api'

/**
 * Lintel-style sidebar: white background, light gray active state (pill),
 * Settings + Support pinned to the bottom.
 */
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
          const metrics = await api.applicationMetrics(role)
          const myQueue = (metrics.byStage?.awaiting_scrutiny ?? 0) + (metrics.byStage?.under_scrutiny ?? 0)
          const openClarifications = metrics.openClarifications ?? 0
          if (!cancelled) setBadges({ myQueue, openClarifications })
        } else if (role === 'applicant') {
          const [overview, notes] = await Promise.all([
            api.getApplicantOverview(role),
            api.listNotifications(role),
          ])
          if (!cancelled)
            setBadges({ clarifications: overview.actionRequired, notifications: notes.unreadCount })
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

  // Separate main nav items from bottom utility items
  const mainItems = items.filter(
    (i) => i.path !== '#settings' && i.path !== '#support',
  )

  return (
    <aside
      aria-label="Primary"
      style={{ borderRight: '1px solid #F0F0F0' }}
      className={clsx(
        'flex h-full flex-col bg-white transition-[width] duration-200',
        collapsed ? 'w-[64px]' : 'w-[280px]',
      )}
    >
      <div
        className={clsx(
          'flex shrink-0 items-center py-3',
          collapsed ? 'justify-center px-2' : 'px-3',
        )}
        style={{ borderBottom: '1px solid #F0F0F0' }}
      >
        <AicteMark compact={collapsed} />
      </div>

      {/* Main nav */}
      <nav className="scrollbar-thin flex-1 overflow-y-auto px-2 py-3">
        {mainItems.map((item, index) => (
          <div key={item.path}>
            {/* Section label */}
            {item.section && !collapsed && (
              <div
                className={clsx(
                  'px-2 pb-1 text-[10px] font-semibold uppercase tracking-widest',
                  index === 0 ? 'pt-1' : 'pt-5',
                )}
                style={{ color: '#AAAAAA' }}
              >
                {item.section}
              </div>
            )}
            {item.section && collapsed && index > 0 && (
              <div className="mx-2 my-2" style={{ borderTop: '1px solid #F0F0F0' }} />
            )}
            <NavLink
              to={item.path}
              end={item.path === ROLE_HOME[role] || item.path === '/applicant/applications'}
              title={collapsed ? item.label : undefined}
              className={({ isActive }) =>
                clsx(
                  'flex h-9 items-center gap-2.5 rounded-lg px-2.5 text-sm transition-colors mb-0.5',
                  collapsed && 'justify-center px-0',
                  isActive
                    ? 'bg-[#F5F5F5] font-semibold text-black'
                    : 'text-[#555555] hover:bg-[#F8F8F8] hover:text-black',
                )
              }
            >
              <item.icon
                size={16}
                strokeWidth={1.75}
                className="shrink-0"
              />
              {!collapsed && (
                <span className="flex min-w-0 flex-1 items-center justify-between gap-2">
                  <span className="truncate">{item.label}</span>
                  {item.badgeKey && (badges[item.badgeKey] ?? 0) > 0 && (
                    <span
                      className="rounded-full px-1.5 py-0.5 text-[10px] font-semibold leading-none"
                      style={{ background: '#F0F0F0', color: '#333333' }}
                      aria-label={`${badges[item.badgeKey]} pending`}
                    >
                      {badges[item.badgeKey]}
                    </span>
                  )}
                </span>
              )}
            </NavLink>
          </div>
        ))}
      </nav>

      {/* Bottom: Settings + Support */}
      <div className="px-2 pb-3 pt-2" style={{ borderTop: '1px solid #F0F0F0' }}>
        <button
          type="button"
          title="Settings"
          className={clsx(
            'flex h-9 w-full items-center gap-2.5 rounded-lg px-2.5 text-sm transition-colors mb-0.5',
            'text-[#777777] hover:bg-[#F5F5F5] hover:text-black',
            collapsed && 'justify-center px-0',
          )}
        >
          <Settings size={16} strokeWidth={1.75} className="shrink-0" />
          {!collapsed && <span>Settings</span>}
        </button>
        <button
          type="button"
          title="Support"
          className={clsx(
            'flex h-9 w-full items-center gap-2.5 rounded-lg px-2.5 text-sm transition-colors',
            'text-[#777777] hover:bg-[#F5F5F5] hover:text-black',
            collapsed && 'justify-center px-0',
          )}
        >
          <HelpCircle size={16} strokeWidth={1.75} className="shrink-0" />
          {!collapsed && <span>Support</span>}
        </button>
        {/* Collapse toggle */}
        <button
          type="button"
          onClick={onToggle}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className={clsx(
            'mt-1 flex h-8 w-full items-center gap-2 rounded-lg px-2.5 text-xs transition-colors',
            'text-[#AAAAAA] hover:bg-[#F5F5F5] hover:text-black',
            collapsed && 'justify-center px-0',
          )}
        >
          <span className="text-base leading-none">{collapsed ? '›' : '‹'}</span>
          {!collapsed && <span>Collapse</span>}
        </button>
      </div>
    </aside>
  )
}
