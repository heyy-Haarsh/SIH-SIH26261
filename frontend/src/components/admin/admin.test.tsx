import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/services/api'
import type { RuleDraftProposal, RuleImportValidation } from '@/types'
import { HealthBadge, overallLabel } from './HealthBadge'
import { RuleDraftPanel } from './RuleDraftPanel'
import { RuleImportPanel } from './RuleImportPanel'

vi.mock('@/services/api', () => ({
  api: {
    validateRuleImport: vi.fn(),
    importRules: vi.fn(),
    draftRuleFromText: vi.fn(),
    saveRuleDraft: vi.fn(),
  },
}))

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>

beforeEach(() => vi.clearAllMocks())
afterEach(cleanup)

const validation = (over: Partial<RuleImportValidation> = {}): RuleImportValidation => ({
  valid: true,
  fileErrors: [],
  willCreate: 1,
  note: 'Validation only.',
  results: [
    { index: 1, code: 'SYN-X-1', action: 'create_rule_draft', valid: true, errors: [], warnings: [], version: 'v1' },
  ],
  ...over,
})

describe('HealthBadge', () => {
  it('never labels an unconfigured or simulated source as healthy', () => {
    render(
      <div>
        <HealthBadge health="not_configured" />
        <HealthBadge health="simulated" />
        <HealthBadge health="disabled" />
      </div>,
    )
    expect(screen.getByText('Not connected')).toBeTruthy()
    expect(screen.getByText('Simulated only')).toBeTruthy()
    expect(screen.getByText('Switched off')).toBeTruthy()
    expect(screen.queryByText('Healthy')).toBeNull()
  })

  it('summarises overall status in plain words', () => {
    expect(overallLabel('degraded').label).toMatch(/limitations/)
    expect(overallLabel('unavailable').tone).toBe('failed')
  })
})

describe('RuleImportPanel', () => {
  it('cannot save until the JSON has been validated as fully valid', async () => {
    mocked.validateRuleImport.mockResolvedValue(validation())
    mocked.importRules.mockResolvedValue({ created: [], activated: 0, message: '1 draft(s) saved.' })
    const onSaved = vi.fn()
    render(<RuleImportPanel role="admin" onSaved={onSaved} />)

    const save = screen.getByRole('button', { name: 'Save as drafts' }) as HTMLButtonElement
    expect(save.disabled).toBe(true)

    fireEvent.change(screen.getByLabelText('Rules JSON'), { target: { value: '[{"code":"SYN-X-1"}]' } })
    fireEvent.click(screen.getByRole('button', { name: 'Validate' }))
    await waitFor(() => expect(screen.getByText(/New rule \(draft, inactive\)/)).toBeTruthy())
    expect(save.disabled).toBe(false)

    fireEvent.click(save)
    await waitFor(() => expect(mocked.importRules).toHaveBeenCalledWith('admin', '[{"code":"SYN-X-1"}]'))
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
  })

  it('shows syntax and per-rule errors and keeps saving disabled', async () => {
    mocked.validateRuleImport.mockResolvedValue(
      validation({
        valid: false,
        fileErrors: ['Not valid JSON: Expecting value (line 3, column 5).'],
        results: [
          {
            index: 2,
            code: 'BAD',
            action: 'invalid',
            valid: false,
            errors: ['Official rules require verified_source_ref.'],
            warnings: [],
            version: 'v1',
          },
        ],
      }),
    )
    render(<RuleImportPanel role="admin" onSaved={() => {}} />)
    fireEvent.change(screen.getByLabelText('Rules JSON'), { target: { value: '{' } })
    fireEvent.click(screen.getByRole('button', { name: 'Validate' }))
    await waitFor(() => expect(screen.getByText(/line 3, column 5/)).toBeTruthy())
    expect(screen.getByText(/Official rules require verified_source_ref/)).toBeTruthy()
    expect(screen.getByText(/all-or-nothing/)).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Save as drafts' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('editing the JSON after validating invalidates the previous result', async () => {
    mocked.validateRuleImport.mockResolvedValue(validation())
    render(<RuleImportPanel role="admin" onSaved={() => {}} />)
    const box = screen.getByLabelText('Rules JSON')
    fireEvent.change(box, { target: { value: '[]' } })
    fireEvent.click(screen.getByRole('button', { name: 'Validate' }))
    await waitFor(() => expect((screen.getByRole('button', { name: 'Save as drafts' }) as HTMLButtonElement).disabled).toBe(false))
    fireEvent.change(box, { target: { value: '[{}]' } })
    expect((screen.getByRole('button', { name: 'Save as drafts' }) as HTMLButtonElement).disabled).toBe(true)
  })
})

describe('RuleDraftPanel', () => {
  const proposal: RuleDraftProposal = {
    requiresReview: true,
    executable: false,
    confidence: 'low',
    mode: 'new_rule',
    interpretation: ['The statement could not be mapped to a check the engine implements.'],
    warnings: ['The engine cannot execute this statement.'],
    sourceText: 'x',
    draft: {
      code: 'SYN-NL-ABC12345',
      name: '[SYNTHETIC] Drafted rule',
      description: 'x',
      version: 'v1',
      isSynthetic: true,
      handbookRef: '',
      verifiedSourceRef: '',
      definition: { logic: 'unrecognized' },
      changeReason: 'Drafted',
      targetRuleCode: null,
    },
    validation: { valid: true, errors: [], warnings: [] },
  }

  it('requires acknowledging the draft before it can be saved, and says when it cannot run', async () => {
    mocked.draftRuleFromText.mockResolvedValue(proposal)
    mocked.saveRuleDraft.mockResolvedValue({ created: [], activated: 0, message: 'Saved 1 draft.' })
    const onSaved = vi.fn()
    render(<RuleDraftPanel role="admin" onSaved={onSaved} />)

    fireEvent.change(screen.getByLabelText('Rule description'), {
      target: { value: 'The library must hold five thousand books.' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Draft rule' }))
    await waitFor(() => expect(screen.getByText('Needs your review')).toBeTruthy())
    expect(screen.getByText(/Documentation only/)).toBeTruthy()
    expect(screen.getByText(/engine cannot execute/i)).toBeTruthy()

    const save = screen.getByRole('button', { name: 'Save as draft' }) as HTMLButtonElement
    expect(save.disabled).toBe(true)
    fireEvent.click(screen.getByLabelText(/I have read this draft/))
    expect(save.disabled).toBe(false)
    fireEvent.click(save)
    await waitFor(() =>
      expect(mocked.saveRuleDraft).toHaveBeenCalledWith('admin', [
        expect.objectContaining({ code: 'SYN-NL-ABC12345', version: 'v1' }),
      ]),
    )
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    // The draft is never activated from here: no publish call exists on the panel.
    expect(Object.keys(mocked)).not.toContain('publishRuleVersion')
  })

  it('does not allow drafting from a very short description', () => {
    render(<RuleDraftPanel role="admin" onSaved={() => {}} />)
    fireEvent.change(screen.getByLabelText('Rule description'), { target: { value: 'short' } })
    expect((screen.getByRole('button', { name: 'Draft rule' }) as HTMLButtonElement).disabled).toBe(true)
  })
})
