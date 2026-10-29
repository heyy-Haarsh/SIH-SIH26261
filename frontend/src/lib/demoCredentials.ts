import type { DemoPersona } from '@/lib/demoAuthSession'
import { DEMO_USERS } from '@/mocks/demoData'
import type { UserRole } from '@/types'

/** Shared demo password for every role — intentionally public for the SIH demo. */
export const DEMO_PASSWORD = 'demo@123'

export interface DemoCredential {
  persona: DemoPersona
  role: UserRole
  label: string
  email: string
  password: string
  hint: string
}

export const DEMO_CREDENTIALS: DemoCredential[] = [
  {
    persona: 'applicant',
    role: 'applicant',
    label: 'Institution / Applicant',
    email: DEMO_USERS.applicant.email,
    password: DEMO_PASSWORD,
    hint: DEMO_USERS.applicant.name,
  },
  {
    persona: 'officer',
    role: 'officer',
    label: 'Scrutiny Officer 1',
    email: DEMO_USERS.officer.email,
    password: DEMO_PASSWORD,
    hint: DEMO_USERS.officer.name,
  },
  {
    persona: 'officer_2',
    role: 'officer',
    label: 'Scrutiny Officer 2',
    email: DEMO_USERS.officer_2.email,
    password: DEMO_PASSWORD,
    hint: DEMO_USERS.officer_2.name,
  },
  {
    persona: 'regional_officer',
    role: 'regional_officer',
    label: 'Regional Officer',
    email: DEMO_USERS.regional_officer.email,
    password: DEMO_PASSWORD,
    hint: DEMO_USERS.regional_officer.name,
  },
]

export function matchDemoCredential(email: string, password: string): DemoCredential | null {
  const normalized = email.trim().toLowerCase()
  return (
    DEMO_CREDENTIALS.find(
      (c) => c.email.toLowerCase() === normalized && c.password === password,
    ) ?? null
  )
}
