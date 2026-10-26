import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input, Label, Select } from '@/components/ui/Input'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import { Badge } from '@/components/ui/Badge'

export function NewApplicationPage() {
  const { role } = useRole()
  const navigate = useNavigate()
  const [category, setCategory] = useState('NEW-ENG')
  const [program, setProgram] = useState('B.Tech — Computer Science')
  const [year, setYear] = useState('2025-26')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setInfo(null)
    try {
      const created = await api.createApplication(role, {
        category_code: category,
        program_name: program,
        academic_year: year,
      })
      setInfo(`Created ${created.applicationNumber} via API.`)
      navigate(`/applicant/applications/${created.id}`)
    } catch (err) {
      if (err instanceof ApiError) {
        setError(
          `API unavailable or rejected (${err.status}): ${err.message}. You can still explore demo applications from the dashboard.`,
        )
      } else {
        setError('Could not reach the backend. Start the FastAPI server to use live create.')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <AppShell title="New Application" breadcrumbs={['Applicant', 'New Application']}>
      <DemoBanner>
        Creating an application calls the backend when available. Backend authorization still
        applies — the demo role switcher alone cannot bypass API permissions.
      </DemoBanner>

      <Card className="max-w-xl">
        <CardHeader
          title="Start a new application"
          description="Minimal create flow for the first working end-to-end path"
          action={<Badge tone="info">API-backed when online</Badge>}
        />
        <form className="space-y-4" onSubmit={onSubmit}>
          <div>
            <Label htmlFor="category">Application category</Label>
            <Select id="category" value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="NEW-ENG">New Institution — Engineering</option>
              <option value="EOA">Extension of Approval</option>
              <option value="INTAKE">Increase in Intake</option>
              <option value="NEW-MBA">New Program — MBA</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="program">Program name</Label>
            <Input id="program" value={program} onChange={(e) => setProgram(e.target.value)} required />
          </div>
          <div>
            <Label htmlFor="year">Academic year</Label>
            <Input id="year" value={year} onChange={(e) => setYear(e.target.value)} required />
          </div>
          {error && (
            <div className="rounded-[var(--radius-md)] border border-red-200 bg-status-failed-bg px-3 py-2 text-xs text-status-failed">
              {error}
            </div>
          )}
          {info && (
            <div className="rounded-[var(--radius-md)] border border-emerald-200 bg-status-pass-bg px-3 py-2 text-xs text-status-pass">
              {info}
            </div>
          )}
          <div className="flex gap-2">
            <Button type="submit" disabled={busy}>
              {busy ? 'Creating…' : 'Create application'}
            </Button>
            <Button type="button" variant="outline" onClick={() => navigate('/applicant/applications')}>
              Cancel
            </Button>
          </div>
        </form>
      </Card>
    </AppShell>
  )
}
