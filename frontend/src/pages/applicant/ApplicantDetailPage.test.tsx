import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ApplicantApplication, Readiness } from '@/types'
import { ApplicantDetailPage } from './ApplicantDetailPage'

const mocks = vi.hoisted(() => ({
  getMyApplication: vi.fn(),
  getReadiness: vi.fn(),
  submitApplication: vi.fn(),
}))

vi.mock('@/services/api', () => ({
  api: mocks,
  ApiError: class ApiError extends Error {},
}))
vi.mock('@/app/RoleContext', () => ({ useRole: () => ({ role: 'applicant' }) }))
vi.mock('@/hooks/useUploadPolicy', () => ({ useUploadPolicy: () => ({ policy: null, filePolicy: null }) }))
vi.mock('@/components/applicant/DocumentUploadControl', () => ({ DocumentUploadControl: () => null }))
vi.mock('@/components/layout/AppShell', () => ({
  AppShell: ({ children, description }: { children: React.ReactNode; description?: string }) => (
    <div>
      <p data-testid="description">{description}</p>
      {children}
    </div>
  ),
}))

function application(over: Partial<ApplicantApplication> = {}): ApplicantApplication {
  return {
    id: 'app-1',
    applicationNumber: 'PRM-2025-2001',
    institutionName: 'Test Institute',
    category: 'New Institution',
    categoryCode: 'NEW-ENG',
    programName: 'B.Tech',
    academicYear: '2025-26',
    status: 'draft',
    statusLabel: 'Draft',
    statusMessage: 'Not submitted yet.',
    submittedAt: null,
    requirements: [],
    deficiencies: [],
    history: [],
    canUpload: true,
    canResubmit: false,
    resubmitBlockers: [],
    requiredTotal: 2,
    requiredUploaded: 1,
    ...over,
  }
}

function readiness(over: Partial<Readiness> = {}): Readiness {
  return {
    applicationId: 'app-1',
    status: 'draft',
    isDraft: true,
    mustFix: [],
    reviewRecommended: [],
    limitations: ['Pre-check only; not a compliance verdict.'],
    canSubmit: true,
    ...over,
  }
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/applicant/applications/app-1']}>
      <Routes>
        <Route path="/applicant/applications/:id" element={<ApplicantDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.getMyApplication.mockResolvedValue(application())
})
afterEach(cleanup)

describe('ApplicantDetailPage — draft submission', () => {
  it('keeps Submit disabled until the confirmation checkbox is checked', async () => {
    mocks.getReadiness.mockResolvedValue(
      readiness({
        canSubmit: false,
        mustFix: [
          {
            code: 'missing_document',
            title: 'Fire Safety Certificate has not been uploaded',
            detail: 'This document is mandatory for your application category.',
            requirementCode: 'FIRE_NOC',
          },
        ],
      }),
    )
    renderPage()
    expect(
      await screen.findByText(/accurate and complete to the best of my knowledge/i),
    ).toBeTruthy()
    expect(screen.queryByText('Must fix before submitting')).toBeNull()
    const button = screen.getByRole('button', { name: 'Submit for scrutiny' }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
    fireEvent.click(button)
    expect(mocks.submitApplication).not.toHaveBeenCalled()
  })

  it('submits exactly once when ready and reports the server result', async () => {
    mocks.getReadiness.mockResolvedValue(readiness())
    mocks.submitApplication.mockResolvedValue({
      applicationId: 'app-1',
      status: 'under_scrutiny',
      alreadySubmitted: false,
      submittedAt: '2026-10-28T10:00:00Z',
      message: 'Application submitted for scrutiny.',
      warnings: [],
    })
    renderPage()
    const button = (await screen.findByRole('button', { name: 'Submit for scrutiny' })) as HTMLButtonElement
    expect(button.disabled).toBe(true)
    fireEvent.click(screen.getByRole('checkbox'))
    await waitFor(() => expect(button.disabled).toBe(false))
    fireEvent.click(button)
    fireEvent.click(button)
    expect(await screen.findByText('Application submitted for scrutiny.')).toBeTruthy()
    expect(mocks.submitApplication).toHaveBeenCalledTimes(1)
    expect(mocks.submitApplication).toHaveBeenCalledWith('applicant', 'app-1', true)
  })

  it('does not offer submission for an application that is already submitted', async () => {
    mocks.getMyApplication.mockResolvedValue(
      application({ status: 'under_scrutiny', statusLabel: 'Under scrutiny' }),
    )
    mocks.getReadiness.mockResolvedValue(readiness({ isDraft: false, status: 'under_scrutiny', canSubmit: false }))
    renderPage()
    await screen.findByText('Readiness review')
    expect(screen.queryByRole('button', { name: 'Submit for scrutiny' })).toBeNull()
  })
})
