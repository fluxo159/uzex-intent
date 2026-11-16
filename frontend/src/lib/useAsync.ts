import { useCallback, useEffect, useRef, useState } from 'react'

export interface AsyncState<T> { data: T | null; error: unknown; loading: boolean; reload: () => void }

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)
  const fnRef = useRef(fn)
  fnRef.current = fn
  useEffect(() => {
    let alive = true
    setLoading(true)
    setError(null)
    fnRef.current().then(
      (d) => { if (alive) { setData(d); setLoading(false) } },
      (e) => { if (alive) { setError(e); setLoading(false) } },
    )
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])
  const reload = useCallback(() => setTick((x) => x + 1), [])
  return { data, error, loading, reload }
}
