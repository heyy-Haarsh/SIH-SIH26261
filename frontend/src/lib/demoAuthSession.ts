import type { UserRole } from '@/types'

export type DemoPersona = 'applicant' | 'officer' | 'officer_2' | 'regional_officer'

export interface DemoSession {
  persona: DemoPersona
  role: UserRole
  /** Value sent as X-Demo-User-Id (alias or id). */
  userId: string
}

const PERSONA_TO_SESSION: Record<DemoPersona, DemoSession> = {
  applicant: { persona: 'applicant', role: 'applicant', userId: 'demo-applicant' },
  officer: { persona: 'officer', role: 'officer', userId: 'demo-officer' },
  officer_2: { persona: 'officer_2', role: 'officer', userId: 'demo-officer-2' },
  regional_officer: {
    persona: 'regional_officer',
    role: 'regional_officer',
    userId: 'demo-regional_officer',
  },
}

const STORAGE_KEY = 'praman.demo.persona'

let session: DemoSession = PERSONA_TO_SESSION.officer

export function getDemoSession(): DemoSession {
  return session
}

export function setDemoSession(persona: DemoPersona): DemoSession {
  session = PERSONA_TO_SESSION[persona] ?? PERSONA_TO_SESSION.officer
  localStorage.setItem(STORAGE_KEY, session.persona)
  return session
}

export function clearDemoSession(): void {
  session = PERSONA_TO_SESSION.officer
  localStorage.removeItem(STORAGE_KEY)
}

export function personaFromStored(raw: string | null): DemoPersona {
  if (raw === 'applicant' || raw === 'officer' || raw === 'officer_2' || raw === 'regional_officer') {
    return raw
  }
  if (raw === 'admin') return 'regional_officer'
  return 'officer'
}

export function hydrateDemoSessionFromStorage(): DemoSession {
  const persona = personaFromStored(localStorage.getItem(STORAGE_KEY))
  session = PERSONA_TO_SESSION[persona]
  return session
}

export function sessionForPersona(persona: DemoPersona): DemoSession {
  return PERSONA_TO_SESSION[persona]
}

export function defaultPersonaForRole(role: UserRole): DemoPersona {
  if (role === 'officer') return 'officer'
  if (role === 'applicant') return 'applicant'
  return 'regional_officer'
}
