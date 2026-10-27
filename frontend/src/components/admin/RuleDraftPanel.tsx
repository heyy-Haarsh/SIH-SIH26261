import { useState } from 'react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Textarea } from '@/components/ui/Input'
import { errorText } from '@/components/scrutiny/scrutinyUi'
import { api } from '@/services/api'
import type { RuleDraftProposal } from '@/types'

const EXAMPLES = [
  'Warn the officer when a certificate\'s validity ends within 90 days.',
  'The fire safety certificate is mandatory for every application.',
  'The institution name must match across all documents.',
]

export function RuleDraftPanel({ role, onSaved }: { role: string; onSaved: () => void }) {
  const [text, setText] = useState('')
  const [proposal, setProposal] = useState<RuleDraftProposal | null>(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [reviewed, setReviewed] = useState(false)

  async function draft() {
    setBusy(true)
    setMsg(null)
    setReviewed(false)
    try {
      setProposal(await api.draftRuleFromText(role, text))
    } catch (err) {
      setProposal(null)
      setMsg(errorText(err, 'Could not draft a rule'))
    } finally {
      setBusy(false)
    }
  }

  async function save() {
    if (!proposal) return
    const d = proposal.draft
    setBusy(true)
    setMsg(null)
    try {
      const res = await api.saveRuleDraft(role, [
        {
          code: d.code,
          name: d.name,
          description: d.description,
          version: d.version,
          is_synthetic: d.isSynthetic,
          definition: d.definition,
          change_reason: d.changeReason,
        },
      ])
      setMsg(res.message)
      setProposal(null)
      setText('')
      onSaved()
    } catch (err) {
      setMsg(errorText(err, 'Could not save the draft'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader
        title="Draft a rule from a description"
        description="Produces a draft for you to review. Nothing is saved or activated until you say so."
      />
      <div className="space-y-3">
        <Textarea
          aria-label="Rule description"
          rows={4}
          value={text}
          onChange={(e) => {
            setText(e.target.value)
            setProposal(null)
          }}
          placeholder="Describe the rule in plain language"
        />
        <div className="flex flex-wrap gap-2 text-xs">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              className="rounded-full border border-border bg-white px-2.5 py-1 text-ink-secondary hover:bg-surface-muted"
              onClick={() => {
                setText(ex)
                setProposal(null)
              }}
            >
              {ex}
            </button>
          ))}
        </div>
        <Button disabled={busy || text.trim().length < 10} onClick={() => void draft()}>
          Draft rule
        </Button>
        {msg && (
          <p role="status" className="text-xs text-ink-secondary">
            {msg}
          </p>
        )}

        {proposal && (
          <div className="space-y-3 rounded-[var(--radius-md)] border border-border p-3" aria-live="polite">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="manual">Needs your review</Badge>
              <Badge tone={proposal.executable ? 'pass' : 'warning'}>
                {proposal.executable ? 'The engine can run this' : 'Documentation only — the engine cannot run this'}
              </Badge>
              <Badge tone="neutral">
                {proposal.mode === 'new_version_of_existing_rule'
                  ? `New version of ${proposal.draft.targetRuleCode}`
                  : 'New rule'}
              </Badge>
            </div>
            <div>
              <div className="text-xs font-semibold text-ink-secondary">How this was understood</div>
              <ul className="list-disc pl-4 text-xs text-ink-secondary">
                {proposal.interpretation.map((i) => (
                  <li key={i}>{i}</li>
                ))}
              </ul>
            </div>
            {proposal.warnings.length > 0 && (
              <ul className="list-disc space-y-0.5 pl-4 text-xs text-status-warning">
                {proposal.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            )}
            <div>
              <div className="text-xs font-semibold text-ink-secondary">
                {proposal.draft.code} · {proposal.draft.version}
              </div>
              <pre className="mt-1 max-h-48 overflow-auto rounded-[var(--radius-md)] bg-surface px-2 py-1.5 text-[11px] text-ink-secondary">
                {JSON.stringify(proposal.draft.definition, null, 2)}
              </pre>
            </div>
            {!proposal.validation.valid && (
              <ul className="list-disc pl-4 text-xs text-status-failed" role="alert">
                {proposal.validation.errors.map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
            )}
            <label className="flex items-start gap-2 text-xs text-ink-secondary">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={reviewed}
                onChange={(e) => setReviewed(e.target.checked)}
              />
              I have read this draft and its warnings.
            </label>
            <Button disabled={busy || !reviewed || !proposal.validation.valid} onClick={() => void save()}>
              Save as draft
            </Button>
            <p className="text-[11px] text-ink-muted">
              Saved drafts appear in the Rules tab. Activating one is a separate, audited step.
            </p>
          </div>
        )}
      </div>
    </Card>
  )
}
