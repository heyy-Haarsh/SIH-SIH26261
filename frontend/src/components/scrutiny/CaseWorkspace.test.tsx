import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ScrutinyIssue, ScrutinyReview } from '@/types'
import { CaseWorkspace, parsePage } from './CaseWorkspace'

const mocks = vi.hoisted(() => ({
  getDocumentReport: vi.fn(),
  resolveFinding: vi.fn(),
  resolveDocVerificationCheck: vi.fn(),
  transitionFinding: vi.fn(),
  getFindingHistory: vi.fn(),
  preview: vi.fn(),
}))
vi.mock('@/services/api', () => ({ api: mocks }))
vi.mock('./DocumentPreview', () => ({
  DocumentPreview: (props: Record<string, unknown>) => {
    mocks.preview(props)
    return <div data-testid="preview">{String(props.documentId)}</div>
  },
}))

const unverified = { status: 'unverified' as const, note: '' }

function issue(over: Partial<ScrutinyIssue> = {}): ScrutinyIssue {
  return {
    key: 'k1',
    title: 'Land area is below the minimum',
    explanation: 'The area on the land record is smaller than required.',
    severity: 'failed',
    status: 'open',
    lifecycleStatus: 'open',
    source: 'rule',
    layer: 'layer1',
    documentId: 'doc-2',
    documentName: 'Land Record',
    relatedDocuments: [],
    handbook: unverified,
    findingIds: ['f-1'],
    checkIds: [],
    occurrences: 1,
    evidence: [{ text: 'Area is 0.4 acre', documentId: 'doc-2', documentName: 'Land Record', pageReference: 'Page 3' }],
    ...over,
  } as ScrutinyIssue
}

function doc(id: string, name: string) {
  return {
    id,
    name,
    requirementCode: id,
    fileName: `${id}.pdf`,
    version: 1,
    mimeType: 'application/pdf',
    sizeBytes: 1,
    uploadedAt: '2026-10-27T00:00:00Z',
    openIssueCount: id === 'doc-2' ? 1 : 0,
    canPreview: true,
    ruleValidationStatus: 'failed',
    externalVerificationStatus: 'verification_unavailable',
    reviewStatus: 'pending',
    documentCheck: { typeMatch: 'matched', clarity: 'clear' },
  }
}

function review(): ScrutinyReview {
  return {
    applicationId: 'app-1',
    documents: [doc('doc-1', 'Affidavit'), doc('doc-2', 'Land Record')],
    missingDocuments: [{ code: 'FIRE', name: 'Fire NOC', mandatory: true }],
    issueGroups: [{ documentId: 'doc-2', documentName: 'Land Record', scope: 'document', issues: [issue()], openCount: 1 }],
    openIssueCount: 1,
    limitations: [],
  } as unknown as ScrutinyReview
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.getDocumentReport.mockResolvedValue({
    extractedFields: [
      {
        id: 'fld-1',
        fieldName: 'Land area',
        value: '0.4 acre',
        pageNumber: 3,
        bbox: { x0: 1, y0: 2, x1: 3, y1: 4 },
      },
      { id: 'fld-2', fieldName: 'Owner', value: 'Trust', pageNumber: 1, bbox: null },
    ],
  })
  mocks.getFindingHistory.mockResolvedValue([])
})
afterEach(cleanup)

const lastPreview = () => mocks.preview.mock.calls.at(-1)![0] as Record<string, unknown>

describe('parsePage', () => {
  it('reads common page citations', () => {
    expect(parsePage('Page 3')).toBe(3)
    expect(parsePage('p. 12')).toBe(12)
    expect(parsePage('page: 2, line 4')).toBe(2)
  })
  it('returns null when no page is cited', () => {
    expect(parsePage('Section B')).toBeNull()
    expect(parsePage(null)).toBeNull()
  })
})

describe('CaseWorkspace', () => {
  it('opens the finding’s document at the cited page', async () => {
    render(<CaseWorkspace review={review()} applicationId="app-1" role="officer" onChanged={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /Land area is below the minimum/ }))

    await waitFor(() => expect(lastPreview().documentId).toBe('doc-2'))
    expect(lastPreview().highlightPage).toBe(3)
    // A finding cites a page only, so no region may be drawn for it.
    expect(lastPreview().highlightBBox).toBeNull()
    expect(screen.getByText(/Showing page 3/)).toBeTruthy()
    expect(screen.getByText(/Area is 0.4 acre/)).toBeTruthy()
  })

  it('highlights a region only for a field that has coordinates', async () => {
    render(<CaseWorkspace review={review()} applicationId="app-1" role="officer" onChanged={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /Land area is below the minimum/ }))
    await waitFor(() => expect(screen.getByRole('button', { name: /Land area: 0.4 acre/ })).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: /Land area: 0.4 acre/ }))
    await waitFor(() => expect(lastPreview().highlightBBox).toEqual({ x0: 1, y0: 2, x1: 3, y1: 4 }))

    fireEvent.click(screen.getByRole('button', { name: /Owner: Trust/ }))
    await waitFor(() => expect(lastPreview().highlightBBox).toBeNull())
  })

  it('lists missing documents and the separate verification dimensions', () => {
    render(<CaseWorkspace review={review()} applicationId="app-1" role="officer" onChanged={vi.fn()} />)
    expect(screen.getByText(/Not uploaded: Fire NOC/)).toBeTruthy()
    expect(screen.getByText('Rule validation')).toBeTruthy()
    expect(screen.getByText('External verification')).toBeTruthy()
    expect(screen.getByText('Human review')).toBeTruthy()
  })

  it('switching documents clears the selected finding', async () => {
    render(<CaseWorkspace review={review()} applicationId="app-1" role="officer" onChanged={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /Land area is below the minimum/ }))
    expect(screen.getByRole('heading', { name: 'Land area is below the minimum' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /^Affidavit/ }))
    await waitFor(() => expect(lastPreview().documentId).toBe('doc-1'))
    expect(screen.queryByRole('heading', { name: 'Land area is below the minimum' })).toBeNull()
  })
})
