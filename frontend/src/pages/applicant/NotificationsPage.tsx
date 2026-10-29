import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'
import { Loading, Notice } from '@/components/ui/Notice'
import { SkeletonFeed } from '@/components/ui/Skeleton'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import { formatDateTime } from '@/lib/format'
import type { AppNotification } from '@/types'

type InboxFilter = 'all' | 'unread'

const KIND_LABEL: Record<string, string> = {
  application_submitted: 'Submitted',
  status_changed: 'Status',
  clarification_requested: 'Clarification',
  clarification_answered: 'Reply',
  applicant_resubmitted: 'Resubmitted',
  decision_recorded: 'Decision',
  case_assigned: 'Assignment',
  processing_completed: 'Document',
  processing_failed: 'Document',
}

/** In-app notification list. Email and SMS are not sent from this product. */
export function NotificationsPage() {
  const { role } = useRole()
  const navigate = useNavigate()
  const [items, setItems] = useState<AppNotification[] | null>(null)
  const [unread, setUnread] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [filter, setFilter] = useState<InboxFilter>('all')

  function load() {
    setError(null)
    api
      .listNotifications(role)
      .then((list) => {
        setItems(list.items)
        setUnread(list.unreadCount)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Notifications could not be loaded.'))
  }

  useEffect(load, [role])

  const visible = useMemo(() => {
    if (!items) return []
    return filter === 'unread' ? items.filter((n) => !n.isRead) : items
  }, [items, filter])

  async function open(n: AppNotification) {
    if (!n.isRead) {
      try {
        await api.markNotificationRead(role, n.id)
      } catch {
        /* still navigate */
      }
    }
    if (n.link) navigate(n.link)
    else load()
  }

  async function markAll() {
    setBusy(true)
    try {
      await api.markAllNotificationsRead(role)
      load()
    } finally {
      setBusy(false)
    }
  }

  return (
    <AppShell
      title="Notifications"
      description="In-app only. Email and SMS delivery is not configured."
      breadcrumbs={['Applicant', 'Notifications']}
      actions={
        unread > 0 ? (
          <Button variant="outline" disabled={busy} onClick={() => void markAll()}>
            Mark all read
          </Button>
        ) : undefined
      }
    >
      {error && (
        <Notice tone="error" className="mb-4" title="Could not load notifications" onRetry={load}>
          {error}
        </Notice>
      )}
      {items === null && !error && <SkeletonFeed count={5} />}
      {items?.length === 0 && (
        <Card className="border-border-strong">
          <EmptyState
            title="No notifications"
            description="When something happens on an application, it will appear here."
          />
        </Card>
      )}
      {items && items.length > 0 && (
        <Card padding={false} className="border-border-strong">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-strong px-4 py-3">
            <div className="flex gap-1">
              <FilterChip active={filter === 'all'} onClick={() => setFilter('all')}>
                All
                <Count n={items.length} />
              </FilterChip>
              <FilterChip active={filter === 'unread'} onClick={() => setFilter('unread')}>
                Unread
                <Count n={unread} />
              </FilterChip>
            </div>
            <p className="text-xs text-ink-muted">
              {unread === 0 ? 'You are caught up.' : `${unread} unread`}
            </p>
          </div>
          {visible.length === 0 ? (
            <p className="px-4 py-10 text-sm text-ink-muted">No unread notifications.</p>
          ) : (
            <ul className="divide-y divide-border">
              {visible.map((n) => (
                <li key={n.id}>
                  <button
                    type="button"
                    onClick={() => void open(n)}
                    className={`flex w-full items-start gap-3 border-l-2 px-4 py-3.5 text-left transition-colors ${
                      n.isRead
                        ? 'border-transparent hover:bg-surface'
                        : 'border-brand bg-brand-soft/60 hover:bg-brand-soft'
                    }`}
                  >
                    <span
                      className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${n.isRead ? 'bg-border-strong' : 'bg-brand'}`}
                      aria-hidden
                    />
                    <span className="min-w-0 flex-1">
                      <span className="flex flex-wrap items-center gap-2">
                        <Badge tone={n.isRead ? 'neutral' : 'brand'}>{KIND_LABEL[n.kind] ?? 'Update'}</Badge>
                        <span className="text-[11px] text-ink-muted">{formatDateTime(n.createdAt)}</span>
                      </span>
                      <span className={`mt-1.5 block text-sm text-ink ${n.isRead ? '' : 'font-semibold'}`}>
                        {n.title}
                      </span>
                      {n.body && (
                        <span className="mt-1 line-clamp-2 block text-xs leading-relaxed text-ink-secondary">
                          {n.body}
                        </span>
                      )}
                    </span>
                    {!n.isRead && <span className="sr-only">Unread</span>}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </AppShell>
  )
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-[var(--radius-md)] px-2.5 py-1 text-xs ${
        active ? 'bg-brand-soft font-medium text-brand' : 'text-ink-muted hover:bg-surface hover:text-ink'
      }`}
    >
      {children}
    </button>
  )
}

function Count({ n }: { n: number }) {
  return <span className="tabular-nums text-[11px] text-ink-muted">{n}</span>
}
