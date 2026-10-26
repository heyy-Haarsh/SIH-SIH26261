import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  ClipboardList,
  Eye,
  FolderOpen,
  Search,
  ShieldAlert,
} from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { AppShell } from '@/components/layout/AppShell'
import { StatCard } from '@/components/dashboard/StatCard'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { Card, CardHeader } from '@/components/ui/Card'
import { Input, Select } from '@/components/ui/Input'
import { ApplicationTable } from '@/components/applications/ApplicationTable'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import {
  DEMO_ACTIVITY,
  DEMO_APPLICATIONS,
  DEMO_HIGH_PRIORITY_FINDINGS,
  DEMO_STATS,
} from '@/mocks/demoData'
import { formatDateTime } from '@/lib/format'
import type { ApplicationStatus, Priority } from '@/types'

export function OfficerDashboard() {
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [priorityFilter, setPriorityFilter] = useState<string>('all')

  const filtered = useMemo(() => {
    return DEMO_APPLICATIONS.filter((app) => {
      const q = query.toLowerCase()
      const matchesQuery =
        !q ||
        app.applicationNumber.toLowerCase().includes(q) ||
        app.institutionName.toLowerCase().includes(q) ||
        app.category.toLowerCase().includes(q)
      const matchesStatus = statusFilter === 'all' || app.status === statusFilter
      const matchesPriority = priorityFilter === 'all' || app.priority === priorityFilter
      return matchesQuery && matchesStatus && matchesPriority
    })
  }, [query, statusFilter, priorityFilter])

  return (
    <AppShell title="Scrutiny Overview" breadcrumbs={['Scrutiny Officer', 'Overview']}>
      <DemoBanner>
        Statistics and queue data below are synthetic demo records for SIH26261. They are not live
        AICTE operational statistics or real institutional applications.
      </DemoBanner>

      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Total in queue"
          value={DEMO_STATS.totalInQueue}
          hint="Demo dataset"
          icon={FolderOpen}
        />
        <StatCard
          label="Awaiting review"
          value={DEMO_STATS.awaitingReview}
          hint="Ready for officer assignment"
          icon={ClipboardList}
        />
        <StatCard
          label="With deficiencies"
          value={DEMO_STATS.withDeficiencies}
          hint="Awaiting institution response"
          icon={AlertTriangle}
        />
        <StatCard
          label="Manual review"
          value={DEMO_STATS.requiringManualReview}
          hint="Human judgment required"
          icon={ShieldAlert}
        />
      </div>

      <div className="mb-5 grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader
            title="Application queue"
            description="Searchable and filterable review queue"
            action={
              <Link to="/officer/queue">
                <Button variant="outline" size="sm">
                  Full queue
                </Button>
              </Link>
            }
          />
          <div className="mb-4 flex flex-col gap-2 sm:flex-row">
            <div className="relative flex-1">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
              <Input
                className="pl-8"
                placeholder="Search by ID, institution, or category…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <Select
              className="sm:w-44"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="all">All statuses</option>
              {(
                [
                  'awaiting_review',
                  'under_review',
                  'deficiency',
                  'manual_review',
                  'resubmitted',
                ] as ApplicationStatus[]
              ).map((s) => (
                <option key={s} value={s}>
                  {s.replace(/_/g, ' ')}
                </option>
              ))}
            </Select>
            <Select
              className="sm:w-36"
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
            >
              <option value="all">All priorities</option>
              {(['critical', 'high', 'medium', 'low'] as Priority[]).map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </Select>
          </div>
          <ApplicationTable rows={filtered} detailBasePath="/officer/applications" />
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader
              title="Status distribution"
              description="Compact chart — demo counts"
            />
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={DEMO_STATS.statusDistribution} margin={{ left: -20, right: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e5eb" vertical={false} />
                  <XAxis
                    dataKey="status"
                    tick={{ fontSize: 10, fill: '#6b7280' }}
                    interval={0}
                    angle={-20}
                    textAnchor="end"
                    height={50}
                  />
                  <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      fontSize: 12,
                      borderRadius: 8,
                      border: '1px solid #e2e5eb',
                    }}
                  />
                  <Bar dataKey="count" fill="#1e3a5f" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card>
            <CardHeader title="Recent scrutiny activity" description="Synthetic timeline" />
            <ul className="space-y-3">
              {DEMO_ACTIVITY.map((item) => (
                <li key={item.id} className="border-b border-border pb-3 last:border-0 last:pb-0">
                  <div className="text-sm font-medium text-ink">{item.title}</div>
                  <div className="mt-0.5 text-xs text-ink-secondary">{item.detail}</div>
                  <div className="mt-1 text-[11px] text-ink-muted">
                    {formatDateTime(item.timestamp)}
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader
          title="High-priority findings"
          description="Evidence-linked findings requiring attention — demo rules only"
        />
        <div className="space-y-3">
          {DEMO_HIGH_PRIORITY_FINDINGS.map((finding) => (
            <div
              key={finding.id}
              className="flex flex-col gap-3 rounded-[var(--radius-md)] border border-border bg-surface p-4 md:flex-row md:items-center md:justify-between"
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold text-ink">{finding.title}</span>
                  <Badge
                    tone={
                      finding.severity === 'failed'
                        ? 'failed'
                        : finding.severity === 'manual_review'
                          ? 'manual'
                          : 'warning'
                    }
                  >
                    {finding.severity.replace(/_/g, ' ')}
                  </Badge>
                </div>
                <p className="mt-1 text-xs text-ink-secondary">{finding.description}</p>
                <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-ink-muted">
                  {finding.ruleId && <span>Rule {finding.ruleId}</span>}
                  {finding.ruleVersion && <span>· {finding.ruleVersion}</span>}
                  {finding.handbookRef && <span>· {finding.handbookRef}</span>}
                </div>
              </div>
              <Link to="/officer/applications/app-1001">
                <Button variant="outline" size="sm" leftIcon={<Eye size={14} />}>
                  Inspect evidence
                </Button>
              </Link>
            </div>
          ))}
        </div>
      </Card>
    </AppShell>
  )
}
