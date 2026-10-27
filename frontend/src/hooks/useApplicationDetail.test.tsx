import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const getApplication = vi.fn()

vi.mock('@/app/RoleContext', () => ({ useRole: () => ({ role: 'officer' }) }))
vi.mock('@/mocks/demoData', () => ({ getDemoApplicationDetail: () => undefined }))
vi.mock('@/services/api', () => ({
  api: { getApplication: (...args: unknown[]) => getApplication(...args) },
  ApiError: class ApiError extends Error {},
}))

import { useApplicationDetail } from '@/hooks/useApplicationDetail'

describe('useApplicationDetail — page jumps to top after upload/replace', () => {
  beforeEach(() => getApplication.mockReset())

  it('reload() refreshes in the background: loading stays false so the page is not unmounted', async () => {
    getApplication.mockResolvedValueOnce({ id: 'a1', status: 'submitted' })
    const { result } = renderHook(() => useApplicationDetail('a1'))
    expect(result.current.loading).toBe(true)
    await waitFor(() => expect(result.current.detail?.status).toBe('submitted'))
    expect(result.current.loading).toBe(false)

    let release!: () => void
    getApplication.mockReturnValueOnce(
      new Promise((resolve) => {
        release = () => resolve({ id: 'a1', status: 'under_scrutiny' })
      }),
    )

    let p!: Promise<void>
    act(() => {
      p = result.current.reload() as Promise<void>
    })
    // The old behaviour set loading=true here, which made the page render its spinner
    // instead of the content and reset scroll to the top.
    expect(result.current.loading).toBe(false)
    expect(result.current.refreshing).toBe(true)
    expect(result.current.detail?.status).toBe('submitted')

    await act(async () => {
      release()
      await p
    })
    expect(result.current.detail?.status).toBe('under_scrutiny')
    expect(result.current.refreshing).toBe(false)
    expect(result.current.loading).toBe(false)
  })

  it('a failed background refresh keeps the last good detail on screen', async () => {
    getApplication.mockResolvedValueOnce({ id: 'a1', status: 'submitted' })
    const { result } = renderHook(() => useApplicationDetail('a1'))
    await waitFor(() => expect(result.current.detail).toBeDefined())

    getApplication.mockRejectedValueOnce(new Error('network down'))
    await act(async () => {
      await result.current.reload()
    })
    expect(result.current.detail?.status).toBe('submitted')
    expect(result.current.error).toBeTruthy()
  })
})
