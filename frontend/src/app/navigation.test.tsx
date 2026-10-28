import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import appSource from '@/App.tsx?raw'
import { NAV_BY_ROLE, ROLE_HOME } from '@/lib/nav'
import { Sidebar } from '@/components/layout/Sidebar'
import { RoleProvider } from '@/app/RoleContext'
import { RequireRole } from '@/app/RequireRole'
import type { UserRole } from '@/types'

const ROLES: UserRole[] = ['applicant', 'officer', 'regional_officer']

afterEach(cleanup)
beforeEach(() => localStorage.clear())

describe('role navigation', () => {
  it.each(ROLES)('every %s menu entry stays inside that role and has a real route', (role) => {
    const items = NAV_BY_ROLE[role]
    expect(items.length).toBeGreaterThan(0)
    const paths = items.map((i) => i.path)
    expect(new Set(paths).size).toBe(paths.length)
    for (const path of paths) {
      expect(path.startsWith(ROLE_HOME[role])).toBe(true)
      expect(appSource).toContain(`path="${path}"`)
    }
  })

  it('no menu entry points at a placeholder page', () => {
    expect(appSource).not.toContain('PlaceholderPage')
    const retired = [
      '/applicant/checklist',
      '/applicant/precheck',
      '/applicant/history',
      '/officer/documents',
      '/officer/extracted',
      '/officer/findings',
      '/officer/verification',
      '/officer/decisions',
      '/officer/reports',
    ]
    const all = ROLES.flatMap((r) => NAV_BY_ROLE[r].map((i) => i.path))
    for (const path of retired) expect(all).not.toContain(path)
  })

  it('regional officers can reach handbook and delegation from the menu', () => {
    const paths = NAV_BY_ROLE.regional_officer.map((i) => i.path)
    expect(paths).toContain('/admin/handbook')
    expect(paths).toContain('/admin/delegation')
  })

  it('applicant menu has no scrutiny or admin entries and vice versa', () => {
    const applicant = NAV_BY_ROLE.applicant.map((i) => i.label.toLowerCase()).join('|')
    expect(applicant).not.toMatch(/extracted|finding|forensic|rule|audit|queue/)
    const officer = NAV_BY_ROLE.officer.map((i) => i.path).join('|')
    expect(officer).not.toMatch(/admin|applicant/)
  })

  it('sidebar renders group headings and the active role entries only', () => {
    localStorage.setItem('praman.demo.role', 'regional_officer')
    render(
      <RoleProvider>
        <MemoryRouter initialEntries={['/admin']}>
          <Sidebar collapsed={false} onToggle={() => {}} />
        </MemoryRouter>
      </RoleProvider>,
    )
    expect(screen.getByText('Operations')).toBeTruthy()
    expect(screen.getByText('Handbook References')).toBeTruthy()
    expect(screen.queryByText('Application Queue')).toBeNull()
  })
})

describe('RequireRole', () => {
  function renderAt(path: string, stored: UserRole) {
    localStorage.setItem('praman.demo.role', stored)
    return render(
      <RoleProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route element={<RequireRole role="regional_officer" />}>
              <Route path="/admin" element={<div>admin area</div>} />
            </Route>
            <Route path="/applicant" element={<div>applicant home</div>} />
            <Route path="/officer" element={<div>officer home</div>} />
          </Routes>
        </MemoryRouter>
      </RoleProvider>,
    )
  }

  it('lets the matching role in', () => {
    renderAt('/admin', 'regional_officer')
    expect(screen.getByText('admin area')).toBeTruthy()
  })

  it('sends an applicant who opens an admin URL back to their own home', () => {
    renderAt('/admin', 'applicant')
    expect(screen.queryByText('admin area')).toBeNull()
    expect(screen.getByText('applicant home')).toBeTruthy()
  })

  it('sends an officer who opens an admin URL back to the officer home', () => {
    renderAt('/admin', 'officer')
    expect(screen.getByText('officer home')).toBeTruthy()
  })
})
