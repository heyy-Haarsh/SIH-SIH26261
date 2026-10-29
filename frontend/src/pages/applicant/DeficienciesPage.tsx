import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Textarea } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import type { DeficiencyNotice } from '@/types'

export function DeficienciesPage() {
  const { role } = useRole()
  const [items, setItems] = useState<DeficiencyNotice[]>([])
  const [error, setError] = useState<string | null>(null)
  const [responses, setResponses] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)

  function load() {
    api
      .listDeficiencies(role)
      .then(setItems)
      .catch((err) =>
        setError(
          err instanceof ApiError
            ? err.message
            : 'Backend unreachable — start the API on port 8000.',
        ),
      )
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role])

  return (
    <AppShell
      title="Clarifications"
      description="Respond to officer requests, then open the application to upload replacements and resubmit."
      breadcrumbs={['Applicant', 'Clarifications']}
    >
      <DemoBanner>
        Open clarification requests from scrutiny officers. Respond here, upload corrected documents,
        then resubmit from the application page. Prior versions and audit history are preserved.
      </DemoBanner>

      <Card>
        <CardHeader title="Open clarification requests" description={`${items.length} notice(s)`} />
        {error && (
          <div className="mb-4 rounded-[var(--radius-md)] border border-[#e3d8bd] bg-status-warning-bg px-3 py-2 text-xs text-status-warning">
            {error}
          </div>
        )}
        {msg && (
          <div className="mb-4 rounded-[var(--radius-md)] border border-[#cfdad2] bg-status-pass-bg px-3 py-2 text-xs text-status-pass">
            {msg}
          </div>
        )}
        {items.length === 0 && !error && (
          <EmptyState
            icon={AlertTriangle}
            title="No deficiency notices"
            description="When an officer requests clarification, items appear here."
          />
        )}
        <ul className="space-y-3">
          {items.map((d) => (
            <li key={d.id} className="rounded-[var(--radius-md)] border border-border p-4">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium text-ink">{d.title}</span>
                <Badge
                  tone={
                    d.status === 'open' ? 'warning' : d.status === 'responded' ? 'info' : 'pass'
                  }
                >
                  {d.status}
                </Badge>
                {d.applicationNumber && (
                  <Link
                    className="text-xs text-brand underline"
                    to={`/applicant/applications/${d.applicationId}`}
                  >
                    {d.applicationNumber}
                  </Link>
                )}
              </div>
              <p className="mb-2 text-xs text-ink-secondary">{d.description}</p>              {d.applicantResponse && (
                <p className="mb-2 text-[11px] text-ink-muted">Your response: {d.applicantResponse}</p>
              )}
              {d.status === 'open' && (
                <div className="space-y-2 border-t border-border pt-3">
                  <Textarea
                    rows={2}
                    placeholder="Describe how you addressed this deficiency…"
                    value={responses[d.id] ?? ''}
                    onChange={(e) =>
                      setResponses((prev) => ({ ...prev, [d.id]: e.target.value }))
                    }
                  />
                  <Button
                    size="sm"
                    disabled={busy === d.id}
                    onClick={async () => {
                      const response = (responses[d.id] ?? '').trim()
                      if (response.length < 5) {
                        setMsg('Enter a response (min 5 characters).')
                        return
                      }
                      setBusy(d.id)
                      try {
                        await api.respondDeficiency(role, d.id, response)
                        setMsg('Response recorded. Upload corrected docs, then resubmit the application.')
                        load()
                      } catch (err) {
                        setMsg(err instanceof Error ? err.message : 'Failed to respond')
                      } finally {
                        setBusy(null)
                      }
                    }}
                  >
                    Submit response
                  </Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      </Card>
    </AppShell>
  )
}
