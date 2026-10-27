import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { RoleProvider } from '@/app/RoleContext'
import { api } from '@/services/api'
import type { ApplicationSummary } from '@/types'
import { OfficerDashboard } from './OfficerDashboard'

vi.mock('@/services/api', () => ({
  api: {
    listApplications: vi.fn(),
    applicationMetrics: vi.fn(),
  },
  ApiError: class ApiError extends Error {},
}))

function summary(over: Partial<ApplicationSummary>): ApplicationSummary {
  return {
    id: 'a',
    applicationNumber: 'PRM-1',
    institutionId: 'i',
    institutionName: 'Inst',
    category: 'Cat',
    categoryCode: 'C',
    submittedAt: null,
    status: 'submitted',
    priority: 'low',
    deficiencyCount: 0,
    findingCount: 0,
    stage: 'awaiting_scrutiny',
    stageLabel: 'Awaiting scrutiny',
    requiresManualReview: false,
    ...over,
  }
}

afterEach(cleanup)
beforeEach(() => {
  localStorage.setItem('praman.demo.role', 'officer')
  vi.mocked(api.listApplications).mockReset()
  vi.mocked(api.applicationMetrics).mockReset()
})

describe('OfficerDashboard', () => {
  it('shows the backend metrics and keeps applications waiting on the applicant out of the queue', async () => {
    vi.mocked(api.listApplications).mockResolvedValue([
      summary({ id: '1', applicationNumber: 'PRM-QUEUED' }),
      summary({
        id: '2',
        applicationNumber: 'PRM-WAITING',
        status: 'clarification_required',
        stage: 'awaiting_applicant',
        stageLabel: 'Awaiting applicant',
      }),
    ])
    vi.mocked(api.applicationMetrics).mockResolvedValue({
      total: 2,
      inOfficerQueue: 1,
      byStage: {
        draft: 0,
        awaiting_scrutiny: 1,
        under_scrutiny: 0,
        awaiting_applicant: 1,
        decided: 0,
      },
      stageLabels: {
        draft: 'Draft',
        awaiting_scrutiny: 'Awaiting scrutiny',
        under_scrutiny: 'Under scrutiny',
        awaiting_applicant: 'Awaiting applicant',
        decided: 'Decided',
      },
      byStatus: { submitted: 1, clarification_required: 1 },
      requiresManualReview: 0,
      openClarifications: 1,
    })

    render(
      <RoleProvider>
        <MemoryRouter>
          <OfficerDashboard />
        </MemoryRouter>
      </RoleProvider>,
    )

    await waitFor(() => expect(screen.getAllByText('PRM-QUEUED').length).toBeGreaterThan(0))
    expect(screen.queryByText('PRM-WAITING')).toBeNull()
    expect(screen.getByText('Waiting on applicant')).toBeTruthy()
    expect(api.applicationMetrics).toHaveBeenCalledWith('officer')
  })
})
