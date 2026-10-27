import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useRefreshable } from '@/hooks/useRefreshable'

function deferred<T>() {
  let resolve!: (v: T) => void
  const promise = new Promise<T>((r) => {
    resolve = r
  })
  return { promise, resolve }
}

describe('useRefreshable — scroll-jump regression', () => {
  it('keeps data mounted and never re-enters loading on reload()', async () => {
    let n = 0
    const load = () => Promise.resolve({ version: ++n })
    const { result } = renderHook(() => useRefreshable(load, 'app-1'))

    expect(result.current.loading).toBe(true)
    await waitFor(() => expect(result.current.data).toEqual({ version: 1 }))
    expect(result.current.loading).toBe(false)

    // Track every render's loading flag during the reload: it must never go true again,
    // because loading=true unmounts the page and resets the browser scroll position.
    const seen: boolean[] = []
    const d = deferred<{ version: number }>()
    const slowLoad = () => d.promise
    const { result: r2, rerender } = renderHook(({ fn }) => useRefreshable(fn, 'app-1'), {
      initialProps: { fn: load as () => Promise<{ version: number }> },
    })
    await waitFor(() => expect(r2.current.data).toBeDefined())
    rerender({ fn: slowLoad })

    let p!: Promise<void>
    act(() => {
      p = r2.current.reload() as Promise<void>
    })
    seen.push(r2.current.loading)
    expect(r2.current.refreshing).toBe(true)
    expect(r2.current.data).toBeDefined() // stale data stays visible while refreshing

    await act(async () => {
      d.resolve({ version: 99 })
      await p
    })
    seen.push(r2.current.loading)
    expect(r2.current.data).toEqual({ version: 99 })
    expect(r2.current.refreshing).toBe(false)
    expect(seen.every((x) => x === false)).toBe(true)
  })

  it('keeps the last good data if a background refresh fails', async () => {
    let fail = false
    const load = () => (fail ? Promise.reject(new Error('boom')) : Promise.resolve('good'))
    const { result } = renderHook(() => useRefreshable(load, 'k'))
    await waitFor(() => expect(result.current.data).toBe('good'))

    fail = true
    await act(async () => {
      await result.current.reload()
    })
    expect(result.current.data).toBe('good')
    expect(result.current.error).toBe('boom')
    expect(result.current.loading).toBe(false)
  })

  it('shows loading (not stale data) when the key changes', async () => {
    const { result, rerender } = renderHook(
      ({ key }) => useRefreshable(() => Promise.resolve(key), key),
      { initialProps: { key: 'a' } },
    )
    await waitFor(() => expect(result.current.data).toBe('a'))
    rerender({ key: 'b' })
    await waitFor(() => expect(result.current.data).toBe('b'))
  })

  it('ignores an older response that arrives after a newer one', async () => {
    const first = deferred<string>()
    const second = deferred<string>()
    const queue = [first, second]
    const load = () => queue.shift()!.promise
    const { result } = renderHook(() => useRefreshable(load, 'k'))

    let p!: Promise<void>
    act(() => {
      p = result.current.reload() as Promise<void>
    })
    await act(async () => {
      second.resolve('new')
      await p
    })
    await act(async () => {
      first.resolve('old')
      await Promise.resolve()
    })
    expect(result.current.data).toBe('new')
  })
})
