import { Navigate, Outlet } from 'react-router-dom'
import { useRole } from '@/app/RoleContext'
import { ROLE_HOME } from '@/lib/nav'
import type { UserRole } from '@/types'

/**
 * Keeps each role inside its own area. This is a usability guard only — the backend enforces
 * the same boundaries independently, so hiding a page here is never the security control.
 *
 * Switching role while on another role's page sends you to that role's home rather than
 * leaving a page whose API calls would now be rejected.
 */
export function RequireRole({ role: required }: { role: UserRole }) {
  const { role } = useRole()

  if (role !== required) return <Navigate to={ROLE_HOME[role]} replace />

  return <Outlet />
}

