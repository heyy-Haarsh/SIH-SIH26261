import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/services/api'
import type { ApplicationDetail, ScrutinyIssue, ScrutinyReview } from '@/types'
import { DecisionPanel } from './DecisionPanel'
import { DocumentCards } from './DocumentCards'
import { HandbookBadge } from './HandbookBadge'
import { IssuesPanel } from './IssuesPanel'

vi.mock('@/services/api', () => ({
  api: {
    resolveFinding: vi.fn().mockResolvedValue({}),
    resolveDocVerificationCheck: vi.fn().mockResolvedValue({}),
    requestClarification: vi.fn().mockResolvedValue({}),
  },
}))

const unverified = { status: 'unverified' as const, note: 'No verified reference.' }

function issue(over: Partial<ScrutinyIssue> = {}): ScrutinyIssue {
  return {
    key: 'doc-1:l1:missing',
    title: 'Institution name is missing',
    explanation: 'The name could not be found in the document.',
    severity: 'failed',
    status: 'open',
    source: 'document_rule',
    layer: 'layer1',
    documentId: 'doc-1',
    documentName: 'Sworn Affidavit',
    requirementCode: 'AFFIDAVIT',
    relatedDocuments: [],
    applicantAction: 'Make sure the institution name is clearly shown, then upload it again.',
    handbook: unverified,
    findingIds: ['f-1'],
    checkIds: [],
    occurrences: 1,
    evidence: [],
    ...over,
  }
}

function review(over: Partial<ScrutinyReview> = {}): ScrutinyReview {
  return {
    applicationId: 'app-1',
    applicationNumber: 'AIC-1',
    institutionName: 'Test Institute',
    status: 'under_scrutiny',
    generatedAt: '2026-10-27T00:00:00Z',
    validationRunId: 'run-1',
    documents: [
      {
        id: 'doc-1',
        name: 'Sworn Affidavit',
        requirementCode: 'AFFIDAVIT',
        fileName: 'affidavit.pdf',
        version: 2,
        mimeType: 'application/pdf',
        sizeBytes: 2048,
        uploadedAt: '2026-10-27T00:00:00Z',
        openIssueCount: 1,
        highestSeverity: 'failed',
        canPreview: true,
        documentCheck: {
          typeMatch: 'matched',
          typeMatchMessage: 'ok',
          expectedType: 'Sworn Affidavit',
          clarity: 'clear',
          clarityMessage: 'ok',
          needsAttention: false,
        },
      },
    ],
    missingDocuments: [{ code: 'FIRE_NOC', name: 'Fire Safety Certificate', mandatory: true }],
    issueGroups: [
      {
        documentId: 'doc-1',
        documentName: 'Sworn Affidavit',
        requirementCode: 'AFFIDAVIT',
        scope: 'document',
        openCount: 1,
        highestSeverity: 'failed',
        issues: [
          issue(),
          issue({ key: 'doc-1:old', title: 'Old resolved issue', status: 'resolved', findingIds: ['f-2'] }),
        ],
      },
    ],
    openIssueCount: 1,
    resolvedIssueCount: 1,
    historicalFindingCount: 4,
    limitations: [],
    decision: {
      status: 'under_scrutiny',
      clarificationRequests: [],
      mustCorrect: ['Sworn Affidavit: Make sure the institution name is clearly shown.'],
      clarificationDraftTitle: 'Corrections needed for AIC-1',
      clarificationDraftBody: 'Please correct the following and resubmit:\n1. Sworn Affidavit: ...',
      rejectionDraftBody: 'The application cannot be recommended because ...',
    },
    disclaimer: 'Decision support only.',
    ...over,
  }
}

beforeEach(() => vi.clearAllMocks())
afterEach(cleanup)

describe('HandbookBadge', () => {
  it('shows edition, section and page only for a verified reference', () => {
    render(
      <HandbookBadge
        reference={{ status: 'verified', edition: '2024-27', section: '3.1', page: '12', note: '' }}
      />,
    )
    expect(screen.getByText(/2024-27 · §3\.1 · p\. 12/)).toBeTruthy()
  })

  it('never renders a clause for an unverified reference', () => {
    render(<HandbookBadge reference={{ ...unverified, section: '9.9' }} />)
    expect(screen.getByText('Handbook reference not verified')).toBeTruthy()
    expect(screen.queryByText(/9\.9/)).toBeNull()
  })
})

describe('IssuesPanel', () => {
  it('lists one plain-language issue per problem and hides resolved ones by default', () => {
    render(<IssuesPanel review={review()} role="officer" onOpenDocument={() => {}} onChanged={() => {}} />)
    // Title always visible in collapsed header
    expect(screen.getByText('Institution name is missing')).toBeTruthy()
    expect(screen.queryByText('Old resolved issue')).toBeNull()
    expect(screen.getByText(/Not uploaded yet:/)).toBeTruthy()
    // Explanation is hidden until the row is expanded
    expect(screen.queryByText(/Make sure the institution name is clearly shown/)).toBeNull()
    fireEvent.click(screen.getByText('Institution name is missing'))
    expect(screen.getByText(/Make sure the institution name is clearly shown/)).toBeTruthy()
    expect(screen.queryByText(/SYN-RULE/)).toBeNull()

    // Show resolved toggle reveals resolved issues
    fireEvent.click(screen.getByText('Show resolved'))
    expect(screen.getByText('Old resolved issue')).toBeTruthy()
  })

  it('opens the document report from a group', () => {
    const onOpen = vi.fn()
    render(<IssuesPanel review={review()} role="officer" onOpenDocument={onOpen} onChanged={() => {}} />)
    fireEvent.click(screen.getByText(/Preview & report/))
    expect(onOpen).toHaveBeenCalledWith('doc-1')
  })

  it('records a resolution against the underlying finding and refreshes', async () => {
    const onChanged = vi.fn()
    render(<IssuesPanel review={review()} role="officer" onOpenDocument={() => {}} onChanged={onChanged} />)
    // Expand the issue first
    fireEvent.click(screen.getByText('Institution name is missing'))
    fireEvent.change(screen.getByPlaceholderText(/Explain why this is resolved/), {
      target: { value: 'Checked the original document' },
    })
    fireEvent.click(screen.getByText('Mark accepted'))
    await waitFor(() =>
      expect(api.resolveFinding).toHaveBeenCalledWith('officer', 'f-1', {
        status: 'accepted',
        reason: 'Checked the original document',
      }),
    )
    await waitFor(() => expect(onChanged).toHaveBeenCalled())
  })

  it('requires a reason before resolving', () => {
    render(<IssuesPanel review={review()} role="officer" onOpenDocument={() => {}} onChanged={() => {}} />)
    // Expand first
    fireEvent.click(screen.getByText('Institution name is missing'))
    fireEvent.click(screen.getByText('Mark resolved'))
    expect(screen.getByText(/at least 5 characters/)).toBeTruthy()
    expect(api.resolveFinding).not.toHaveBeenCalled()
  })

  it('offers no resolve controls to non-staff roles', () => {
    render(<IssuesPanel review={review()} role="applicant" onOpenDocument={() => {}} onChanged={() => {}} />)
    expect(screen.queryByText('Mark resolved')).toBeNull()
  })
})

describe('DocumentCards', () => {
  it('makes each uploaded document clickable and lists missing ones', () => {
    const onOpen = vi.fn()
    render(<DocumentCards review={review()} onOpen={onOpen} />)
    fireEvent.click(screen.getByRole('button', { name: 'Open Sworn Affidavit' }))
    expect(onOpen).toHaveBeenCalledWith('doc-1')
    expect(screen.getByText('Fire Safety Certificate')).toBeTruthy()
    expect(screen.getByText('1 open · Failed')).toBeTruthy()
  })
})

describe('DecisionPanel', () => {
  const detail = {
    id: 'app-1',
    status: 'under_scrutiny',
    reviewNotes: [],
    auditEvents: [],
  } as unknown as ApplicationDetail

  it('prefills the clarification from the suggested plain-language text', async () => {
    render(<DecisionPanel detail={detail} review={review()} role="officer" onChanged={() => {}} />)
    fireEvent.click(screen.getByText('Use suggested text'))
    const body = screen.getByLabelText('Clarification details') as HTMLTextAreaElement
    expect(body.value).toContain('Please correct the following')

    fireEvent.click(screen.getByText('Send clarification request'))
    await waitFor(() =>
      expect(api.requestClarification).toHaveBeenCalledWith(
        'officer',
        'app-1',
        expect.objectContaining({ title: 'Corrections needed for AIC-1' }),
      ),
    )
  })

  it('shows an earlier decision and the reason, and hides actions once closed', () => {
    const closed = { ...detail, status: 'rejected' } as ApplicationDetail
    const r = review()
    r.decision = {
      ...r.decision,
      status: 'rejected',
      finalDecision: 'rejected',
      finalDecisionReason: 'Names do not match.',
      finalDecisionBy: 'Officer Rao',
    }
    render(<DecisionPanel detail={closed} review={r} role="officer" onChanged={() => {}} />)
    expect(screen.getByText('Names do not match.')).toBeTruthy()
    expect(screen.queryByText('Send clarification request')).toBeNull()
    expect(screen.queryByText('Recommend')).toBeNull()
  })
})
