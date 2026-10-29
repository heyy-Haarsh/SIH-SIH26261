import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { NotificationList } from '@/types'
import { NotificationBell } from './NotificationBell'

const mocks = vi.hoisted(() => ({
  listNotifications: vi.fn(),
  markNotificationRead: vi.fn(),
  markAllNotificationsRead: vi.fn(),
}))

vi.mock('@/services/api', () => ({ api: mocks }))
vi.mock('@/app/RoleContext', () => ({ useRole: () => ({ role: 'officer' }) }))

function inbox(over: Partial<NotificationList> = {}): NotificationList {
  return {
    unreadCount: 1,
    items: [
      {
        id: 'n-1',
        kind: 'case_assigned',
        title: 'PRM-2025-1010 assigned to you',
        body: 'Test Institute — B.Tech',
        applicationId: 'app-1',
        link: '/officer/applications/app-1',
        createdAt: '2026-10-28T10:00:00Z',
        readAt: null,
        isRead: false,
      },
      {
        id: 'n-2',
        kind: 'decision_recorded',
        title: 'Older item',
        body: '',
        applicationId: 'app-2',
        link: null,
        createdAt: '2026-10-27T10:00:00Z',
        readAt: '2026-10-27T11:00:00Z',
        isRead: true,
      },
    ],
    ...over,
  }
}

function renderBell() {
  return render(
    <MemoryRouter initialEntries={['/start']}>
      <Routes>
        <Route path="/start" element={<NotificationBell />} />
        <Route path="/officer/applications/:id" element={<p>Case page</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.markNotificationRead.mockResolvedValue({})
  mocks.markAllNotificationsRead.mockResolvedValue({ marked: 1 })
})
afterEach(cleanup)

describe('NotificationBell', () => {
  it('shows the real unread count from the server', async () => {
    mocks.listNotifications.mockResolvedValue(inbox())
    renderBell()
    expect((await screen.findByTestId('unread-count')).textContent).toBe('1')
  })

  it('shows no badge and an honest empty state when there is nothing', async () => {
    mocks.listNotifications.mockResolvedValue({ items: [], unreadCount: 0 })
    renderBell()
    await waitFor(() => expect(mocks.listNotifications).toHaveBeenCalled())
    expect(screen.queryByTestId('unread-count')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Notifications' }))
    expect(await screen.findByText('You have no notifications.')).toBeTruthy()
    expect(screen.getByText(/Email \/ SMS delivery is not configured/)).toBeTruthy()
  })

  it('marks an item read and opens its link', async () => {
    mocks.listNotifications.mockResolvedValue(inbox())
    renderBell()
    fireEvent.click(await screen.findByRole('button', { name: /Notifications, 1 unread/ }))
    fireEvent.click(await screen.findByText('PRM-2025-1010 assigned to you'))
    await waitFor(() => expect(mocks.markNotificationRead).toHaveBeenCalledWith('officer', 'n-1'))
    expect(await screen.findByText('Case page')).toBeTruthy()
  })

  it('does not re-mark an already read item', async () => {
    mocks.listNotifications.mockResolvedValue(inbox({ unreadCount: 0 }))
    renderBell()
    fireEvent.click(await screen.findByRole('button', { name: 'Notifications' }))
    fireEvent.click(await screen.findByText('Older item'))
    expect(mocks.markNotificationRead).not.toHaveBeenCalled()
  })

  it('reports a load failure instead of pretending the inbox is empty', async () => {
    mocks.listNotifications.mockRejectedValue(new Error('down'))
    renderBell()
    fireEvent.click(screen.getByRole('button', { name: 'Notifications' }))
    expect(await screen.findByText('Could not load notifications right now.')).toBeTruthy()
    expect(screen.queryByText('You have no notifications.')).toBeNull()
  })
})
