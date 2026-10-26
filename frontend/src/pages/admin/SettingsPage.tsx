import { useEffect, useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input, Label, Textarea } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import type { AdminSetting } from '@/types'

export function SettingsPage() {
  const { role } = useRole()
  const [settings, setSettings] = useState<AdminSetting[]>([])
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [reasons, setReasons] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  function load() {
    api
      .listAdminSettings(role)
      .then((rows) => {
        setSettings(rows)
        const next: Record<string, string> = {}
        for (const s of rows) next[s.key] = JSON.stringify(s.value ?? {}, null, 2)
        setDrafts(next)
        setError(null)
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : 'Failed to load settings'),
      )
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role])

  return (
    <AppShell title="Verification & Settings" breadcrumbs={['Administrator', 'Settings']}>
      <DemoBanner>
        Safe non-secret configuration only. API keys and passwords cannot be stored here. Live
        verification stays off until authorized connectors are configured outside this demo.
      </DemoBanner>

      {error && (
        <div className="mb-4 rounded-[var(--radius-md)] border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          {error}
        </div>
      )}
      {msg && (
        <div className="mb-4 rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2 text-xs">
          {msg}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {settings.map((s) => (
          <Card key={s.key}>
            <CardHeader
              title={s.key}
              description={s.description || 'Administrator setting'}
              action={
                <Badge tone={s.key === 'verification' ? 'warning' : 'neutral'}>{s.key}</Badge>
              }
            />
            <Label>Value (JSON)</Label>
            <Textarea
              rows={10}
              value={drafts[s.key] ?? '{}'}
              onChange={(e) => setDrafts((d) => ({ ...d, [s.key]: e.target.value }))}
            />
            <div className="mt-2">
              <Label>Change reason</Label>
              <Input
                value={reasons[s.key] ?? ''}
                onChange={(e) => setReasons((r) => ({ ...r, [s.key]: e.target.value }))}
                placeholder="Why this change?"
              />
            </div>
            <div className="mt-3">
              <Button
                size="sm"
                disabled={busy === s.key}
                onClick={async () => {
                  const reason = (reasons[s.key] ?? '').trim()
                  if (reason.length < 3) {
                    setMsg('Provide a change reason (≥3 characters).')
                    return
                  }
                  if (
                    !window.confirm(
                      `Save setting "${s.key}"? This is audited and must not contain secrets.`,
                    )
                  ) {
                    return
                  }
                  setBusy(s.key)
                  setMsg(null)
                  try {
                    const value = JSON.parse(drafts[s.key] ?? '{}')
                    await api.updateAdminSetting(role, s.key, {
                      value,
                      change_reason: reason,
                    })
                    setMsg(`Updated ${s.key}`)
                    load()
                  } catch (err) {
                    setMsg(err instanceof Error ? err.message : 'Save failed')
                  } finally {
                    setBusy(null)
                  }
                }}
              >
                Save {s.key}
              </Button>
            </div>
            {s.updatedAt && (
              <p className="mt-2 text-[11px] text-ink-muted">
                Last update: {s.updatedAt}
                {s.changeReason ? ` — ${s.changeReason}` : ''}
              </p>
            )}
          </Card>
        ))}
      </div>
    </AppShell>
  )
}
