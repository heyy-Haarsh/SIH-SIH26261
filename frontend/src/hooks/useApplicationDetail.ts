import { useEffect, useState } from 'react'
import { useRole } from '@/app/RoleContext'
import { getDemoApplicationDetail } from '@/mocks/demoData'
import { api, ApiError } from '@/services/api'
import type { ApplicationDetail } from '@/types'

/**
 * Prefer live API detail when available. Fall back to labeled demo mocks for
 * synthetic IDs like app-1001 when the backend has no matching row.
 */
export function useApplicationDetail(id: string | undefined) {
  const { role } = useRole()
  const [detail, setDetail] = useState<ApplicationDetail | undefined>(undefined)
  const [source, setSource] = useState<'api' | 'mock' | 'none'>('none')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) {
      setDetail(undefined)
      setSource('none')
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)

    api
      .getApplication(id, role)
      .then((data) => {
        if (cancelled) return
        setDetail(data)
        setSource('api')
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const mock = getDemoApplicationDetail(id)
        if (mock) {
          setDetail(mock)
          setSource('mock')
          setError(null)
        } else {
          setDetail(undefined)
          setSource('none')
          setError(err instanceof ApiError ? err.message : 'Failed to load application')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [id, role])

  return { detail, source, loading, error, setDetail }
}
