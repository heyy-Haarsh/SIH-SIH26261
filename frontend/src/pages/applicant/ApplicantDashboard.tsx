import { Link } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, FilePlus2, FolderOpen, Upload } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { StatCard } from '@/components/dashboard/StatCard'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { ApplicationTable } from '@/components/applications/ApplicationTable'
import { APPLICANT_APPLICATIONS } from '@/mocks/demoData'
import { useRole } from '@/app/RoleContext'

export function ApplicantDashboard() {
  const { user } = useRole()
  const apps = APPLICANT_APPLICATIONS

  return (
    <AppShell title="Institution Dashboard" breadcrumbs={['Applicant', 'Dashboard']}>
      <DemoBanner>
        {`Applicant workspace for ${user.institutionName ?? 'your institution'}. Demo data only — not a live AICTE portal.`}
      </DemoBanner>

      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="My applications" value={apps.length} icon={FolderOpen} />
        <StatCard
          label="Open deficiencies"
          value={apps.reduce((n, a) => n + a.deficiencyCount, 0)}
          icon={AlertTriangle}
        />
        <StatCard
          label="Awaiting review"
          value={apps.filter((a) => a.status === 'awaiting_review').length}
          icon={CheckCircle2}
        />
        <StatCard label="Documents pending" value={2} hint="Checklist items" icon={Upload} />
      </div>

      <div className="mb-5 flex flex-wrap gap-2">
        <Link to="/applicant/applications/new">
          <Button leftIcon={<FilePlus2 size={16} />}>New application</Button>
        </Link>
        <Link to="/applicant/uploads">
          <Button variant="outline" leftIcon={<Upload size={16} />}>
            Upload documents
          </Button>
        </Link>
        <Link to="/applicant/deficiencies">
          <Button variant="secondary" leftIcon={<AlertTriangle size={16} />}>
            View deficiencies
          </Button>
        </Link>
      </div>

      <Card>
        <CardHeader
          title="My applications"
          description="Applications belonging to your institution"
          action={
            <Link to="/applicant/applications">
              <Button variant="outline" size="sm">
                View all
              </Button>
            </Link>
          }
        />
        <ApplicationTable rows={apps} detailBasePath="/applicant/applications" />
      </Card>
    </AppShell>
  )
}
