import { useCallback, useState } from 'react'

// The one busy/error wrapper for async UI actions: clears the previous error,
// sets busy, surfaces thrown errors, and always clears busy — so stages don't
// hand-roll (subtly inconsistent) try/catch/finally blocks.
export function useBusy() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const run = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    setBusy(true)
    setError('')
    try {
      return await fn()
    } catch (e) {
      setError((e as Error).message)
      return undefined
    } finally {
      setBusy(false)
    }
  }, [])

  return { busy, error, setError, run }
}
