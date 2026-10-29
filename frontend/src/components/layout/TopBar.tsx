import { Menu } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useRole } from '@/app/RoleContext'
import type { DemoPersona } from '@/lib/demoAuthSession'
import { ROLE_HOME } from '@/lib/nav'
import { Select } from '@/components/ui/Input'
import { NotificationBell } from './NotificationBell'

const PERSONA_LABELS: Record<DemoPersona, string> = {
  applicant: 'Institution / Applicant',
  officer: 'Scrutiny Officer 1',
  officer_2: 'Scrutiny Officer 2',
  regional_officer: 'Regional Officer',
}

const ROLE_SECTION: Record<string, string> = {
  applicant: 'SmartBuild',
  officer: 'SmartBuild',
  officer_2: 'SmartBuild',
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
  const { role, persona, user, setPersona, logout } = useRole()
  const navigate = useNavigate()

  function onPersonaChange(next: DemoPersona) {
    setPersona(next)
    const homeRole = next === 'officer_2' ? 'officer' : next
    navigate(ROLE_HOME[homeRole], { replace: true })
  }

  function onSignOut() {
    logout()
    navigate('/', { replace: true })
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

        <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-sm">
          <span className="font-medium text-[#888888]">{ROLE_SECTION[persona] ?? ROLE_SECTION[role]}</span>
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

      <div className="flex items-center gap-3">
        <label className="flex items-center gap-2 text-[11px] text-[#888888]">
          <span className="hidden sm:inline">Demo account</span>
          <Select
            aria-label="Demo account switcher (not secure authentication)"
            className="!h-8 w-[180px] !text-xs !border-[#E0E0E0] !bg-white !rounded-lg"
            value={persona}
            onChange={(e) => onPersonaChange(e.target.value as DemoPersona)}
          >
            <option value="officer">Scrutiny Officer 1</option>
            <option value="officer_2">Scrutiny Officer 2</option>
            <option value="applicant">Applicant</option>
            <option value="regional_officer">Regional Officer</option>
          </Select>
        </label>

        <NotificationBell />

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
            <div className="truncate text-[11px] text-[#888888]">{PERSONA_LABELS[persona]}</div>
          </div>
          <button
            type="button"
            onClick={onSignOut}
            className="rounded-lg px-2 py-1 text-[11px] font-medium text-[#888888] hover:bg-white hover:text-[#111111]"
          >
            Sign out
          </button>
        </div>
      </div>
    </header>
  )
}
