import { Menu } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useRole } from '@/app/RoleContext'
import { ROLE_HOME } from '@/lib/nav'
import type { UserRole } from '@/types'
import { Select } from '@/components/ui/Input'
import { NotificationBell } from './NotificationBell'

const ROLE_LABELS: Record<UserRole, string> = {
  applicant: 'Institution / Applicant',
  officer: 'Scrutiny Officer',
  regional_officer: 'Regional Officer',
}

const ROLE_SECTION: Record<UserRole, string> = {
  applicant: 'SmartBuild',
  officer: 'SmartBuild',
  regional_officer: 'SmartBuild',
}

export function TopBar({
  title,
  breadcrumbs,
  onMenuClick,
}: {
  title?: string
  description?: string
  breadcrumbs?: string[]
  onMenuClick?: () => void
}) {
  const { role, user, setRole } = useRole()
  const navigate = useNavigate()

  function onRoleChange(next: UserRole) {
    setRole(next)
    navigate(ROLE_HOME[next], { replace: true })
  }

  const initials = user.name
    .split(' ')
    .map((n) => n[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()

  return (
    <header
      className="flex h-14 shrink-0 items-center justify-between gap-4 bg-[#F5F5F5] px-6"
      style={{ borderBottom: '1px solid #F0F0F0' }}
    >
      {/* Left: mobile menu + breadcrumbs */}
      <div className="flex min-w-0 items-center gap-3">
        {onMenuClick && (
          <button
            type="button"
            className="rounded-lg p-1.5 text-[#888888] hover:bg-white lg:hidden"
            onClick={onMenuClick}
            aria-label="Open navigation"
          >
            <Menu size={18} />
          </button>
        )}

        {/* Breadcrumbs */}
        <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-sm">
          <span className="font-medium text-[#888888]">{ROLE_SECTION[role]}</span>
          <span className="text-[#CCCCCC] mx-1">/</span>
          {breadcrumbs && breadcrumbs.length > 0
            ? breadcrumbs.map((crumb, i) => (
                <span key={`${crumb}-${i}`} className="flex items-center gap-1">
                  {i > 0 && <span className="text-[#CCCCCC]">/</span>}
                  <span
                    className={
                      i === breadcrumbs.length - 1
                        ? 'font-semibold text-[#111111]'
                        : 'text-[#888888]'
                    }
                  >
                    {crumb}
                  </span>
                </span>
              ))
            : title && (
                <span className="font-semibold text-[#111111]">{title}</span>
              )}
        </nav>
      </div>

      {/* Right: demo role switcher, bell, avatar */}
      <div className="flex items-center gap-3">
        {/* Demo role switcher */}
        <label className="flex items-center gap-2 text-[11px] text-[#888888]">
          <span className="hidden sm:inline">Demo role</span>
          <Select
            aria-label="Demo role switcher (not secure authentication)"
            className="!h-8 w-[160px] !text-xs !border-[#E0E0E0] !bg-white !rounded-lg"
            value={role}
            onChange={(e) => onRoleChange(e.target.value as UserRole)}
          >
            <option value="officer">Scrutiny Officer</option>
            <option value="applicant">Applicant</option>
            <option value="regional_officer">Regional Officer</option>
          </Select>
        </label>

        {/* Notification bell */}
        <NotificationBell />

        {/* User avatar */}
        <div className="flex items-center gap-2.5">
          <div
            className="flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold text-white"
            style={{ background: '#2D2D2D' }}
            title={user.name}
          >
            {initials}
          </div>
          <div className="hidden min-w-0 md:block">
            <div className="truncate text-[13px] font-medium text-[#111111]">{user.name}</div>
            <div className="truncate text-[11px] text-[#888888]">{ROLE_LABELS[role]}</div>
          </div>
        </div>
      </div>
    </header>
  )
}
