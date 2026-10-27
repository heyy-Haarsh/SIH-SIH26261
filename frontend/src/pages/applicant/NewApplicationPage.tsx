import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input, Label, Select } from '@/components/ui/Input'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import { validateApplicationForm, type ApplicationFormErrors } from '@/lib/applicationForm'

export function NewApplicationPage() {
  const { role, user } = useRole()
  const navigate = useNavigate()
  const [category, setCategory] = useState('NEW-ENG')
  const [institutionName, setInstitutionName] = useState(user.institutionName ?? '')
  const [program, setProgram] = useState('')
  const [year, setYear] = useState('2025-26')
  const [busy, setBusy] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<ApplicationFormErrors>({})
  const [error, setError] = useState<string | null>(null)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    const { values, errors } = validateApplicationForm({ institutionName, program, year })
    setFieldErrors(errors)
    if (Object.keys(errors).length > 0) return
    setBusy(true)
    setError(null)
    try {
      const created = await api.createApplication(role, {
        category_code: category,
        institution_name: values.institutionName,
        program_name: values.program,
        academic_year: values.year,
      })
      navigate(`/applicant/applications/${created.id}`)
    } catch (err) {
      setError(
        err instanceof ApiError
          ? `The application could not be created: ${err.message}`
          : 'Could not reach the server. Please try again shortly.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <AppShell title="New Application" breadcrumbs={['Applicant', 'New Application']}>
      <Card className="max-w-xl">
        <CardHeader
          title="Start a new application"
          description="You will upload the required documents on the next screen."
        />
        <form className="space-y-4" onSubmit={onSubmit} noValidate>
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
            <Label htmlFor="institutionName">Institution name</Label>
            <Input
              id="institutionName"
              value={institutionName}
              onChange={(e) => setInstitutionName(e.target.value)}
              placeholder="Full name as it appears on your documents"
              maxLength={255}
              aria-invalid={Boolean(fieldErrors.institutionName)}
              aria-describedby="institutionName-help"
            />
            <p
              id="institutionName-help"
              className={`mt-1 text-[11px] ${fieldErrors.institutionName ? 'text-status-failed' : 'text-ink-muted'}`}
            >
              {fieldErrors.institutionName ??
                'Use the exact name from your affidavit and land documents — the officer compares them.'}
            </p>
          </div>
          <div>
            <Label htmlFor="program">Program name</Label>
            <Input
              id="program"
              value={program}
              onChange={(e) => setProgram(e.target.value)}
              placeholder="e.g. B.Tech — Computer Science"
              aria-invalid={Boolean(fieldErrors.program)}
            />
            {fieldErrors.program && <p className="mt-1 text-[11px] text-status-failed">{fieldErrors.program}</p>}
          </div>
          <div>
            <Label htmlFor="year">Academic year</Label>
            <Input
              id="year"
              value={year}
              onChange={(e) => setYear(e.target.value)}
              placeholder="2025-26"
              aria-invalid={Boolean(fieldErrors.year)}
            />
            {fieldErrors.year && <p className="mt-1 text-[11px] text-status-failed">{fieldErrors.year}</p>}
          </div>
          {error && (
            <div
              role="alert"
              className="rounded-[var(--radius-md)] border border-red-200 bg-status-failed-bg px-3 py-2 text-xs text-status-failed"
            >
              {error}
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
