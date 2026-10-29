import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ScrutinyIssue } from '@/types'
import { FindingLifecycleControls } from './FindingLifecycle'

const mocks = vi.hoisted(() => ({
  transitionFinding: vi.fn(),
  getFindingHistory: vi.fn(),
}))
vi.mock('@/services/api', () => ({ api: mocks }))

function issue(over: Partial<ScrutinyIssue> = {}): ScrutinyIssue {
  return {
    key: 'doc-1:expired',
    title: 'Affidavit has expired',
    explanation: '',
    severity: 'failed',
    status: 'open',
    lifecycleStatus: 'open',
    source: 'rule',
    layer: 'layer1',
    documentId: 'doc-1',
    documentName: 'Sworn Affidavit',
    relatedDocuments: [],
    handbook: { status: 'unverified', note: '' },
    findingIds: ['f-1', 'f-2'],
    checkIds: [],
    occurrences: 1,
    evidence: [],
    ...over,
  } as ScrutinyIssue
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.transitionFinding.mockResolvedValue({})
  mocks.getFindingHistory.mockImplementation((_role: string, id: string) =>
    Promise.resolve([
      {
        id: `h-${id}`,
        findingId: id,
        fromStatus: 'open',
        toStatus: 'under_review',
        actorName: 'Rajesh Iyer',
        actorRole: 'officer',
        reason: '',
        createdAt: id === 'f-1' ? '2026-10-28T10:00:00Z' : '2026-10-28T11:00:00Z',
      },
    ]),
  )
})
afterEach(cleanup)

describe('FindingLifecycleControls', () => {
  it('moves every finding behind the issue to under review', async () => {
    const onChanged = vi.fn()
    render(<FindingLifecycleControls issue={issue()} role="officer" canAct onChanged={onChanged} />)
    fireEvent.click(screen.getByRole('button', { name: 'Mark under review' }))
    await waitFor(() => expect(onChanged).toHaveBeenCalled())
    expect(mocks.transitionFinding).toHaveBeenCalledTimes(2)
    expect(mocks.transitionFinding).toHaveBeenCalledWith('officer', 'f-1', { status: 'under_review', reason: '' })
    expect(mocks.transitionFinding).toHaveBeenCalledWith('officer', 'f-2', { status: 'under_review', reason: '' })
  })

  it('does not offer "under review" when it already is, and offers nothing to non-staff', () => {
    const { rerender } = render(
      <FindingLifecycleControls
        issue={issue({ lifecycleStatus: 'under_review' })}
        role="officer"
        canAct
        onChanged={() => {}}
      />,
    )
    expect(screen.queryByRole('button', { name: 'Mark under review' })).toBeNull()
    rerender(<FindingLifecycleControls issue={issue()} role="applicant" canAct={false} onChanged={() => {}} />)
    expect(screen.queryByRole('button', { name: 'Mark under review' })).toBeNull()
  })

  it('requires a reason to reopen a closed finding', async () => {
    const onChanged = vi.fn()
    render(
      <FindingLifecycleControls
        issue={issue({ status: 'resolved', lifecycleStatus: 'resolved' })}
        role="officer"
        canAct
        onChanged={onChanged}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Reopen…' }))
    const submit = screen.getByRole('button', { name: 'Reopen finding' }) as HTMLButtonElement
    expect(submit.disabled).toBe(true)
    fireEvent.change(screen.getByLabelText('Reason for reopening'), {
      target: { value: 'New discrepancy found' },
    })
    expect(submit.disabled).toBe(false)
    fireEvent.click(submit)
    await waitFor(() =>
      expect(mocks.transitionFinding).toHaveBeenCalledWith('officer', 'f-1', {
        status: 'reopened',
        reason: 'New discrepancy found',
      }),
    )
  })

  it('shows the recorded history in time order and surfaces server errors', async () => {
    render(<FindingLifecycleControls issue={issue()} role="officer" canAct onChanged={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'History' }))
    const list = await screen.findByLabelText('Finding history')
    const rows = list.querySelectorAll('li')
    expect(rows).toHaveLength(2)
    expect(rows[0].textContent).toContain('Rajesh Iyer')

    mocks.transitionFinding.mockRejectedValueOnce(new Error('A finding that is open cannot move to resolved.'))
    fireEvent.click(screen.getByRole('button', { name: 'Mark under review' }))
    expect((await screen.findByRole('alert')).textContent).toContain('cannot move')
  })
})
