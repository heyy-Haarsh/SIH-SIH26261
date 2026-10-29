import { useCallback, useEffect, useRef, useState } from 'react'
import { Bell } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useRole } from '@/app/RoleContext'
import { api } from '@/services/api'
import { formatDateTime } from '@/lib/format'
import type { NotificationList } from '@/types'

const POLL_MS = 30_000

/** In-app inbox backed by `/notifications`. Email/SMS delivery is not implemented. */
export function NotificationBell() {
  const { role } = useRole()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [list, setList] = useState<NotificationList>({ items: [], unreadCount: 0 })
  const [error, setError] = useState(false)
  const alive = useRef(true)

  const refresh = useCallback(async () => {
    try {
      const next = await api.listNotifications(role)
      if (!alive.current) return
      setList(next)
      setError(false)
    } catch {
      if (alive.current) setError(true)
    }
  }, [role])

  useEffect(() => {
    alive.current = true
    setList({ items: [], unreadCount: 0 })
    void refresh()
    const timer = window.setInterval(() => void refresh(), POLL_MS)
    return () => {
      alive.current = false
      window.clearInterval(timer)
    }
  }, [refresh])

  async function openItem(id: string, link?: string | null, isRead?: boolean) {
    if (!isRead) {
      try {
        await api.markNotificationRead(role, id)
      } catch {
        /* navigation still works if marking fails */
      }
    }
    setOpen(false)
    void refresh()
    if (link) navigate(link)
  }

  async function markAll() {
    try {
      await api.markAllNotificationsRead(role)
    } finally {
      void refresh()
    }
  }

  return (
    <div className="relative">
      <button
        type="button"
        className="relative rounded-md p-2 text-ink-muted hover:bg-surface-muted"
        aria-label={list.unreadCount > 0 ? `Notifications, ${list.unreadCount} unread` : 'Notifications'}
        aria-expanded={open}
        onClick={() => {
          setOpen((o) => !o)
          if (!open) void refresh()
        }}
      >
        <Bell size={18} />
        {list.unreadCount > 0 && (
          <span
            data-testid="unread-count"
            className="absolute -right-0.5 -top-0.5 min-w-4 rounded-full bg-status-failed px-1 text-center text-[10px] font-semibold leading-4 text-white"
          >
            {list.unreadCount > 99 ? '99+' : list.unreadCount}
          </span>
        )}
      </button>
      {open && (
        <div
          role="dialog"
          aria-label="Notifications"
          className="absolute right-0 z-50 mt-1 w-80 rounded-[var(--radius-md)] border border-border bg-white shadow-[var(--shadow-card)]"
        >
          <div className="flex items-center justify-between border-b border-border px-3 py-2">
            <p className="text-xs font-semibold text-ink">Notifications</p>
            {list.unreadCount > 0 && (
              <button
                type="button"
                className="text-[11px] font-medium text-brand hover:underline"
                onClick={() => void markAll()}
              >
                Mark all read
              </button>
            )}
          </div>
          <ul className="max-h-80 divide-y divide-border overflow-y-auto">
            {error && (
              <li className="px-3 py-3 text-[11px] text-status-failed">
                Could not load notifications right now.
              </li>
            )}
            {!error && list.items.length === 0 && (
              <li className="px-3 py-4 text-[11px] text-ink-muted">You have no notifications.</li>
            )}
            {list.items.map((n) => (
              <li key={n.id}>
                <button
                  type="button"
                  className={`w-full px-3 py-2 text-left hover:bg-surface-muted ${n.isRead ? '' : 'bg-brand-soft/40'}`}
                  onClick={() => void openItem(n.id, n.link, n.isRead)}
                >
                  <span className="flex items-start justify-between gap-2">
                    <span className={`text-xs text-ink ${n.isRead ? '' : 'font-semibold'}`}>{n.title}</span>
                    {!n.isRead && <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-brand" aria-label="Unread" />}
                  </span>
                  {n.body && <span className="mt-0.5 block text-[11px] text-ink-muted">{n.body}</span>}
                  <span className="mt-0.5 block text-[10px] text-ink-muted">{formatDateTime(n.createdAt)}</span>
                </button>
              </li>
            ))}
          </ul>
          {role === 'applicant' && (
            <button
              type="button"
              className="w-full border-t border-border px-3 py-2 text-left text-[11px] font-medium text-ink-secondary hover:bg-surface"
              onClick={() => {
                setOpen(false)
                navigate('/applicant/notifications')
              }}
            >
              View all notifications
            </button>
          )}
          <p className="border-t border-border px-3 py-1.5 text-[10px] text-ink-muted">
            In-app only. Email / SMS delivery is not configured.
          </p>
        </div>
      )}
    </div>
  )
}
