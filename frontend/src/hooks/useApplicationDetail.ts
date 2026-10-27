import { useCallback, useEffect, useRef, useState } from 'react'
import { useRole } from '@/app/RoleContext'
import { getDemoApplicationDetail } from '@/mocks/demoData'
import { api, ApiError } from '@/services/api'
import type { ApplicationDetail } from '@/types'

/**
 * Prefer live API detail when available. Fall back to labeled demo mocks for
 * synthetic IDs like app-1001 when the backend has no matching row.
 *
 * `loading` is true ONLY while there is nothing to show yet (first load, or the
 * application id/role changed). `reload()` refreshes in the background and flips
 * `refreshing` instead, keeping the current data mounted. Setting `loading` on reload
 * used to unmount the whole page, which reset the scroll position to the top after
 * every upload/replace/clarification action.
 */
export function useApplicationDetail(id: string | undefined) {
  const { role } = useRole()
  const [detail, setDetail] = useState<ApplicationDetail | undefined>(undefined)
  const [source, setSource] = useState<'api' | 'mock' | 'none'>('none')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Guards against an older response overwriting a newer one.
  const requestSeq = useRef(0)

  const fetchDetail = useCallback(
    (appId: string, { background }: { background: boolean }) => {
      const seq = ++requestSeq.current
      if (background) setRefreshing(true)
      else {
        setLoading(true)
        setError(null)
      }
      return api
        .getApplication(appId, role)
        .then((data) => {
          if (seq !== requestSeq.current) return
          setDetail(data)
          setSource('api')
          setError(null)
        })
        .catch((err: unknown) => {
          if (seq !== requestSeq.current) return
          const mock = getDemoApplicationDetail(appId)
          if (mock) {
            setDetail(mock)
            setSource('mock')
            setError(null)
          } else if (background) {
            // Keep showing the last good data; surface the refresh failure only.
            setError(err instanceof ApiError ? err.message : 'Failed to refresh application')
          } else {
            setDetail(undefined)
            setSource('none')
            setError(err instanceof ApiError ? err.message : 'Failed to load application')
          }
        })
        .finally(() => {
          if (seq !== requestSeq.current) return
          setLoading(false)
          setRefreshing(false)
        })
    },
    [role],
  )

  useEffect(() => {
    if (!id) {
      requestSeq.current++
      setDetail(undefined)
      setSource('none')
      setLoading(false)
      return
    }
    // New id or role → different data set; show the loading state, not stale data.
    setDetail(undefined)
    void fetchDetail(id, { background: false })
    return () => {
      requestSeq.current++
    }
  }, [id, fetchDetail])

  const reload = useCallback(() => {
    if (!id) return Promise.resolve()
    return fetchDetail(id, { background: true })
  }, [id, fetchDetail])

  return { detail, source, loading, refreshing, error, setDetail, reload }
}
