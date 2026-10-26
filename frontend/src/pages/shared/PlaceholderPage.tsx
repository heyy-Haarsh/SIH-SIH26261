import type { LucideIcon } from 'lucide-react'
import { Construction } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { EmptyState } from '@/components/ui/EmptyState'
import { Badge } from '@/components/ui/Badge'

export function PlaceholderPage({
  title,
  breadcrumbs,
  description,
  icon = Construction,
}: {
  title: string
  breadcrumbs: string[]
  description: string
  icon?: LucideIcon
}) {
  return (
    <AppShell title={title} breadcrumbs={breadcrumbs}>
      <div className="mb-3">
        <Badge tone="warning">Not yet fully implemented</Badge>
      </div>
      <EmptyState icon={icon} title={title} description={description} />
    </AppShell>
  )
}
