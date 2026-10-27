import { useState } from 'react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Textarea } from '@/components/ui/Input'
import { errorText } from '@/components/scrutiny/scrutinyUi'
import { api } from '@/services/api'
import type { RuleImportValidation } from '@/types'

const EXAMPLE = `[
  {
    "code": "SYN-RULE-EXAMPLE",
    "name": "Example rule",
    "definition": { "logic": "missing_mandatory", "synthetic": true },
    "change_reason": "Imported for review"
  }
]`

export function RuleImportPanel({ role, onSaved }: { role: string; onSaved: () => void }) {
  const [text, setText] = useState('')
  const [check, setCheck] = useState<RuleImportValidation | null>(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  async function validate() {
    setBusy(true)
    setMsg(null)
    try {
      setCheck(await api.validateRuleImport(role, text))
    } catch (err) {
      setCheck(null)
      setMsg(errorText(err, 'Validation failed'))
    } finally {
      setBusy(false)
    }
  }

  async function save() {
    setBusy(true)
    setMsg(null)
    try {
      const res = await api.importRules(role, text)
      setMsg(res.message)
      setText('')
      setCheck(null)
      onSaved()
    } catch (err) {
      setMsg(errorText(err, 'Import failed'))
    } finally {
      setBusy(false)
    }
  }

  async function onFile(file: File | undefined) {
    if (!file) return
    setText(await file.text())
    setCheck(null)
    setMsg(null)
  }

  return (
    <Card>
      <CardHeader
        title="Import rules from JSON"
        description="Validated first. Imported rules are saved as drafts and never take effect until you activate them."
      />
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-[var(--radius-md)] border border-border bg-white px-3 py-1.5 font-medium text-ink hover:bg-surface-muted">
            Choose a .json file
            <input
              type="file"
              accept="application/json,.json"
              className="sr-only"
              onChange={(e) => void onFile(e.target.files?.[0])}
            />
          </label>
          <button type="button" className="text-accent underline" onClick={() => setText(EXAMPLE)}>
            Insert example
          </button>
        </div>
        <Textarea
          aria-label="Rules JSON"
          rows={12}
          className="font-mono text-xs"
          value={text}
          onChange={(e) => {
            setText(e.target.value)
            setCheck(null)
          }}
          placeholder='A JSON array of rules, or {"rules": [...]}'
        />
        <div className="flex flex-wrap gap-2">
          <Button disabled={busy || !text.trim()} variant="outline" onClick={() => void validate()}>
            Validate
          </Button>
          <Button disabled={busy || !check?.valid} onClick={() => void save()}>
            Save as drafts
          </Button>
        </div>
        {msg && (
          <p role="status" className="text-xs text-ink-secondary">
            {msg}
          </p>
        )}

        {check && (
          <div className="space-y-2" aria-live="polite">
            {check.fileErrors.map((e) => (
              <p key={e} role="alert" className="text-xs text-status-failed">
                {e}
              </p>
            ))}
            {check.results.length > 0 && (
              <ul className="space-y-1.5">
                {check.results.map((r) => (
                  <li
                    key={r.index}
                    className="rounded-[var(--radius-md)] border border-border px-3 py-2 text-xs"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium text-ink">
                        #{r.index} {r.code || '(no code)'}
                      </span>
                      <Badge tone={r.valid ? 'pass' : 'failed'}>
                        {r.valid
                          ? r.action === 'add_draft_version'
                            ? `New draft version ${r.version}`
                            : 'New rule (draft, inactive)'
                          : 'Invalid'}
                      </Badge>
                    </div>
                    {r.errors.map((e) => (
                      <p key={e} className="mt-1 text-status-failed">
                        {e}
                      </p>
                    ))}
                    {r.warnings.map((w) => (
                      <p key={w} className="mt-1 text-status-warning">
                        {w}
                      </p>
                    ))}
                  </li>
                ))}
              </ul>
            )}
            {check.valid && (
              <p className="text-xs text-status-pass">
                All {check.willCreate} rule(s) are valid. {check.note}
              </p>
            )}
            {!check.valid && check.results.length > 0 && (
              <p className="text-xs text-ink-muted">
                Nothing can be imported until every rule is valid — the import is all-or-nothing.
              </p>
            )}
          </div>
        )}
      </div>
    </Card>
  )
}
