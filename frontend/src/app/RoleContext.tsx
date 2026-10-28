import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { DEMO_USERS } from '@/mocks/demoData'
import type { User, UserRole } from '@/types'

interface RoleContextValue {
  role: UserRole
  user: User
  setRole: (role: UserRole) => void
  /** Demo-only role switching — not secure authentication */
  isDemoAuth: true
}

const RoleContext = createContext<RoleContextValue | null>(null)

const STORAGE_KEY = 'praman.demo.role'

function readStoredRole(): UserRole {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'admin') return 'regional_officer' // legacy
  if (stored === 'applicant' || stored === 'officer' || stored === 'regional_officer') return stored
  return 'officer'
}

export function RoleProvider({ children }: { children: ReactNode }) {
  const [role, setRoleState] = useState<UserRole>(readStoredRole)

  const setRole = useCallback((next: UserRole) => {
    setRoleState(next)
    localStorage.setItem(STORAGE_KEY, next)
  }, [])

  const value = useMemo<RoleContextValue>(
    () => ({
      role,
      user: DEMO_USERS[role],
      setRole,
      isDemoAuth: true,
    }),
    [role, setRole],
  )

  return <RoleContext.Provider value={value}>{children}</RoleContext.Provider>
}

export function useRole() {
  const ctx = useContext(RoleContext)
  if (!ctx) throw new Error('useRole must be used within RoleProvider')
  return ctx
}
