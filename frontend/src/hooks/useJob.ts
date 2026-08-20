import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { JobSnapshot } from '../types'

// Starts a background job (align/extract) and polls its progress until done.
// With a `storageKey`, the active job id is persisted so a page reload
// re-attaches to a still-running job. `onDone` fires exactly once per job
// completion (including after a reload re-attach).
export function useJob(storageKey?: string, onDone?: (job: JobSnapshot) => void) {
  const [job, setJob] = useState<JobSnapshot | null>(null)
  const [error, setError] = useState('')
  const timer = useRef<number | null>(null)
  const onDoneRef = useRef(onDone)
  onDoneRef.current = onDone

  const stop = () => {
    if (timer.current) {
      clearInterval(timer.current)
      timer.current = null
    }
  }

  const finish = (snap: JobSnapshot) => {
    stop()
    if (storageKey) localStorage.removeItem(storageKey)
    if (snap.status === 'done') onDoneRef.current?.(snap)
  }

  const poll = (id: string) => {
    stop()
    timer.current = window.setInterval(async () => {
      try {
        const snap: JobSnapshot = await api.get(`/api/jobs/${id}`)
        setJob(snap)
        if (snap.status !== 'running') finish(snap)
      } catch (e) {
        setError((e as Error).message)
        stop()
      }
    }, 800)
  }

  // Reconnect to a persisted job on mount.
  useEffect(() => {
    if (storageKey) {
      const id = localStorage.getItem(storageKey)
      if (id) {
        api
          .get(`/api/jobs/${id}`)
          .then((snap: JobSnapshot) => {
            setJob(snap)
            if (snap.status === 'running') poll(id)
            else finish(snap)
          })
          .catch(() => localStorage.removeItem(storageKey))
      }
    }
    return stop
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const start = async (endpoint: string, body: unknown): Promise<void> => {
    setError('')
    setJob({ id: '', kind: '', status: 'running', phase: null, percent: null, log: '', result: null, error: null })
    try {
      const { job_id } = await api.post(endpoint, body)
      if (storageKey) localStorage.setItem(storageKey, job_id)
      poll(job_id)
    } catch (e) {
      setJob(null)
      setError((e as Error).message)
    }
  }

  return { job, error, start, running: job?.status === 'running' }
}
