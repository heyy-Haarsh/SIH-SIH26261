import { useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { Card, CardHeader } from '@/components/ui/Card'
import { Input, Select } from '@/components/ui/Input'
import { ApplicationTable } from '@/components/applications/ApplicationTable'
import { DEMO_APPLICATIONS } from '@/mocks/demoData'

export function QueuePage() {
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')

  const rows = useMemo(
    () =>
      DEMO_APPLICATIONS.filter((a) => {
        const q = query.toLowerCase()
        const matchQ =
          !q ||
          a.applicationNumber.toLowerCase().includes(q) ||
          a.institutionName.toLowerCase().includes(q)
        const matchS = statusFilter === 'all' || a.status === statusFilter
        return matchQ && matchS
      }),
    [query, statusFilter],
  )

  return (
    <AppShell title="Application Queue" breadcrumbs={['Scrutiny Officer', 'Queue']}>
      <DemoBanner>
        Queue contents are synthetic demo applications for product walkthrough only.
      </DemoBanner>
      <Card>
        <CardHeader title="Review queue" description={`${rows.length} applications shown`} />
        <div className="mb-4 flex flex-col gap-2 sm:flex-row">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
            <Input
              className="pl-8"
              placeholder="Search applications…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <Select
            className="sm:w-48"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">All statuses</option>
            <option value="awaiting_review">Awaiting review</option>
            <option value="under_review">Under review</option>
            <option value="deficiency">Deficiency</option>
            <option value="manual_review">Manual review</option>
            <option value="resubmitted">Resubmitted</option>
          </Select>
        </div>
        <ApplicationTable rows={rows} detailBasePath="/officer/applications" />
      </Card>
    </AppShell>
  )
}
