import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Load a resource once, then refresh it in the background without unmounting the UI.
 *
 * `loading` is only true while there is no data yet (first load or when `key` changes).
 * `reload()` flips `refreshing` and keeps the previous data on screen, so the page keeps
 * its scroll position after uploads / replacements / responses.
 */
export function useRefreshable<T>(load: (() => Promise<T>) | null, key: string) {
  const [data, setData] = useState<T | undefined>(undefined)
  const [loading, setLoading] = useState(Boolean(load))
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const seq = useRef(0)
  const loadRef = useRef(load)
  loadRef.current = load

  const run = useCallback((background: boolean) => {
    const fn = loadRef.current
    if (!fn) return Promise.resolve()
    const mine = ++seq.current
    if (background) setRefreshing(true)
    else {
      setLoading(true)
      setError(null)
    }
    return fn()
      .then((next) => {
        if (mine !== seq.current) return
        setData(next)
        setError(null)
      })
      .catch((err: unknown) => {
        if (mine !== seq.current) return
        setError(err instanceof Error ? err.message : 'Request failed')
        if (!background) setData(undefined)
      })
      .finally(() => {
        if (mine !== seq.current) return
        setLoading(false)
        setRefreshing(false)
      })
  }, [])

  useEffect(() => {
    if (!loadRef.current) {
      seq.current++
      setData(undefined)
      setLoading(false)
      return
    }
    setData(undefined)
    void run(false)
    return () => {
      seq.current++
    }
  }, [key, run])

  const reload = useCallback(() => run(true), [run])

  return { data, loading, refreshing, error, reload }
}
