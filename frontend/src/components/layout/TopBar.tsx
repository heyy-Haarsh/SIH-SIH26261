import { Bell, ChevronDown, Menu } from 'lucide-react'
import { useRole } from '@/app/RoleContext'
import type { UserRole } from '@/types'
import { Badge } from '@/components/ui/Badge'
import { Select } from '@/components/ui/Input'

const ROLE_LABELS: Record<UserRole, string> = {
  applicant: 'Institution / Applicant',
  officer: 'Scrutiny Officer',
  admin: 'System Administrator',
}

export function TopBar({
  title,
  breadcrumbs,
  onMenuClick,
}: {
  title: string
  breadcrumbs?: string[]
  onMenuClick?: () => void
}) {
  const { role, user, setRole } = useRole()

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-border bg-white px-4 md:px-6">
      <div className="flex min-w-0 items-center gap-3">
        {onMenuClick && (
          <button
            type="button"
            className="rounded-md p-1.5 text-ink-muted hover:bg-surface-muted lg:hidden"
            onClick={onMenuClick}
            aria-label="Open navigation"
          >
            <Menu size={18} />
          </button>
        )}
        <div className="min-w-0">
          {breadcrumbs && breadcrumbs.length > 0 && (
            <div className="mb-0.5 flex items-center gap-1 text-[11px] text-ink-muted">
              {breadcrumbs.map((crumb, i) => (
                <span key={crumb} className="flex items-center gap-1">
                  {i > 0 && <span>/</span>}
                  <span>{crumb}</span>
                </span>
              ))}
            </div>
          )}
          <h1 className="truncate text-sm font-semibold text-ink md:text-base">{title}</h1>
        </div>
      </div>

      <div className="flex items-center gap-2 md:gap-3">
        <div className="hidden items-center gap-2 rounded-[var(--radius-md)] border border-amber-200 bg-amber-50 px-2.5 py-1 sm:flex">
          <Badge tone="warning">Demo</Badge>
          <span className="text-[11px] text-amber-800">Role switcher — not secure auth</span>
        </div>

        <div className="w-[160px] md:w-[200px]">
          <Select
            aria-label="Demo role switcher"
            value={role}
            onChange={(e) => setRole(e.target.value as UserRole)}
          >
            <option value="officer">Scrutiny Officer</option>
            <option value="applicant">Applicant</option>
            <option value="admin">Administrator</option>
          </Select>
        </div>

        <button
          type="button"
          className="relative rounded-md p-2 text-ink-muted hover:bg-surface-muted"
          aria-label="Notifications"
        >
          <Bell size={18} />
          <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-status-failed" />
        </button>

        <div className="hidden items-center gap-2 border-l border-border pl-3 md:flex">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-soft text-xs font-semibold text-brand">
            {user.name
              .split(' ')
              .map((n) => n[0])
              .slice(0, 2)
              .join('')}
          </div>
          <div className="min-w-0">
            <div className="truncate text-xs font-medium text-ink">{user.name}</div>
            <div className="truncate text-[10px] text-ink-muted">{ROLE_LABELS[role]}</div>
          </div>
          <ChevronDown size={14} className="text-ink-muted" />
        </div>
      </div>
    </header>
  )
}
