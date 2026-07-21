import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { JobSnapshot } from '../types'

// Starts a background job (align/extract) and polls its progress until done.
export function useJob() {
  const [job, setJob] = useState<JobSnapshot | null>(null)
  const [error, setError] = useState('')
  const timer = useRef<number | null>(null)

  const stop = () => {
    if (timer.current) {
      clearInterval(timer.current)
      timer.current = null
    }
  }
  useEffect(() => stop, [])

  const poll = (id: string) => {
    stop()
    timer.current = window.setInterval(async () => {
      try {
        const snap: JobSnapshot = await api.get(`/api/jobs/${id}`)
        setJob(snap)
        if (snap.status !== 'running') stop()
      } catch (e) {
        setError((e as Error).message)
        stop()
      }
    }, 800)
  }

  const start = async (endpoint: string, body: unknown): Promise<void> => {
    setError('')
    setJob({ id: '', kind: '', status: 'running', phase: null, percent: null, log: '', result: null, error: null })
    try {
      const { job_id } = await api.post(endpoint, body)
      poll(job_id)
    } catch (e) {
      setJob(null)
      setError((e as Error).message)
    }
  }

  const reset = () => {
    stop()
    setJob(null)
    setError('')
  }

  return { job, error, start, reset, running: job?.status === 'running' }
}
