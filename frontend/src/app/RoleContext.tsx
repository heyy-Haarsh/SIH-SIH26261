import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  clearDemoSession,
  defaultPersonaForRole,
  hydrateDemoSessionFromStorage,
  setDemoSession,
  type DemoPersona,
} from '@/lib/demoAuthSession'
import { DEMO_USERS } from '@/mocks/demoData'
import type { User, UserRole } from '@/types'

interface RoleContextValue {
  role: UserRole
  persona: DemoPersona
  user: User
  setRole: (role: UserRole) => void
  setPersona: (persona: DemoPersona) => void
  isLoggedIn: boolean
  login: (persona: DemoPersona) => void
  logout: () => void
  /** Demo-only role switching — not secure authentication */
  isDemoAuth: true
}

const RoleContext = createContext<RoleContextValue | null>(null)

const ROLE_STORAGE_KEY = 'praman.demo.role'
const AUTH_KEY = 'praman.demo.loggedIn'

function readLoggedIn(): boolean {
  return localStorage.getItem(AUTH_KEY) === '1'
}

function initialPersona(): DemoPersona {
  if (localStorage.getItem('praman.demo.persona')) {
    return hydrateDemoSessionFromStorage().persona
  }
  const storedRole = localStorage.getItem(ROLE_STORAGE_KEY)
  let persona: DemoPersona = 'officer'
  if (storedRole === 'applicant' || storedRole === 'officer' || storedRole === 'regional_officer') {
    persona = defaultPersonaForRole(storedRole)
  } else if (storedRole === 'admin') {
    persona = 'regional_officer'
  }
  return setDemoSession(persona).persona
}

export function RoleProvider({ children }: { children: ReactNode }) {
  const [persona, setPersonaState] = useState<DemoPersona>(initialPersona)
  const [isLoggedIn, setLoggedIn] = useState(readLoggedIn)

  const applyPersona = useCallback((next: DemoPersona) => {
    const session = setDemoSession(next)
    setPersonaState(session.persona)
    localStorage.setItem(ROLE_STORAGE_KEY, session.role)
  }, [])

  const setPersona = useCallback(
    (next: DemoPersona) => {
      applyPersona(next)
    },
    [applyPersona],
  )

  const setRole = useCallback(
    (next: UserRole) => {
      applyPersona(defaultPersonaForRole(next))
    },
    [applyPersona],
  )

  const login = useCallback(
    (next: DemoPersona) => {
      applyPersona(next)
      localStorage.setItem(AUTH_KEY, '1')
      setLoggedIn(true)
    },
    [applyPersona],
  )

  const logout = useCallback(() => {
    localStorage.removeItem(AUTH_KEY)
    clearDemoSession()
    setLoggedIn(false)
  }, [])

  const role = (DEMO_USERS[persona]?.role ?? 'officer') as UserRole
  const user = DEMO_USERS[persona] ?? DEMO_USERS.officer

  const value = useMemo<RoleContextValue>(
    () => ({
      role,
      persona,
      user,
      setRole,
      setPersona,
      isLoggedIn,
      login,
      logout,
      isDemoAuth: true,
    }),
    [role, persona, user, setRole, setPersona, isLoggedIn, login, logout],
  )

  return <RoleContext.Provider value={value}>{children}</RoleContext.Provider>
}

export function useRole() {
  const ctx = useContext(RoleContext)
  if (!ctx) throw new Error('useRole must be used within RoleProvider')
  return ctx
}
