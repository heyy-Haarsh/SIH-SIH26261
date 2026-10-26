import { Link } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { ApplicationTable } from '@/components/applications/ApplicationTable'
import { APPLICANT_APPLICATIONS } from '@/mocks/demoData'

export function ApplicantApplicationsPage() {
  return (
    <AppShell title="My Applications" breadcrumbs={['Applicant', 'Applications']}>
      <DemoBanner>Showing demo applications for the sample institution only.</DemoBanner>
      <Card>
        <CardHeader
          title="Institution applications"
          action={
            <Link to="/applicant/applications/new">
              <Button size="sm">New application</Button>
            </Link>
          }
        />
        <ApplicationTable rows={APPLICANT_APPLICATIONS} detailBasePath="/applicant/applications" />
      </Card>
    </AppShell>
  )
}
