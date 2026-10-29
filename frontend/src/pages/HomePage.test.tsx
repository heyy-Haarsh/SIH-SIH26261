import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { RoleProvider } from '@/app/RoleContext'
import { DEMO_PASSWORD } from '@/lib/demoCredentials'
import { HomePage } from './HomePage'

afterEach(cleanup)
beforeEach(() => localStorage.clear())

function renderHome() {
  return render(
    <RoleProvider>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/officer" element={<p>Officer dashboard</p>} />
          <Route path="/applicant" element={<p>Applicant dashboard</p>} />
          <Route path="/admin" element={<p>Admin dashboard</p>} />
        </Routes>
      </MemoryRouter>
    </RoleProvider>,
  )
}

describe('HomePage', () => {
  it('shows AICTE letterhead, hero login, and key features', () => {
    renderHome()
    expect(screen.getByText('All India Council for Technical Education')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Login to PRAMAN' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Sign in to PRAMAN →' })).toBeTruthy()
    expect(screen.getByLabelText('Email')).toBeTruthy()
    expect(screen.getByText('Key Features')).toBeTruthy()
    expect(screen.getByRole('link', { name: /View video prototype/i })).toBeTruthy()
    expect(document.querySelector('section#login')?.getAttribute('style') ?? '').toContain(
      'aicte-hq.jpg',
    )
  })

  it('auto-fills demo credentials and signs in to the officer home', () => {
    renderHome()
    fireEvent.click(screen.getByRole('button', { name: /Scrutiny Officer 1/i }))
    expect((screen.getByLabelText('Email') as HTMLInputElement).value).toContain('officer.demo')
    expect((screen.getByLabelText('Password') as HTMLInputElement).value).toBe(DEMO_PASSWORD)
    fireEvent.click(screen.getByRole('button', { name: 'Sign in to PRAMAN →' }))
    expect(screen.getByText('Officer dashboard')).toBeTruthy()
    expect(localStorage.getItem('praman.demo.loggedIn')).toBe('1')
    expect(localStorage.getItem('praman.demo.role')).toBe('officer')
    expect(localStorage.getItem('praman.demo.persona')).toBe('officer')
  })

  it('signs in as the second scrutiny officer', () => {
    renderHome()
    fireEvent.click(screen.getByRole('button', { name: /Scrutiny Officer 2/i }))
    expect((screen.getByLabelText('Email') as HTMLInputElement).value).toContain('officer2.demo')
    fireEvent.click(screen.getByRole('button', { name: 'Sign in to PRAMAN →' }))
    expect(screen.getByText('Officer dashboard')).toBeTruthy()
    expect(localStorage.getItem('praman.demo.persona')).toBe('officer_2')
  })
})
