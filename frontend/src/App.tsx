import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import type { Ctx, Stage, Status } from './types'
import { Sidebar } from './components/Sidebar'
import { CorpusStage } from './stages/CorpusStage'
import { AlignStage } from './stages/AlignStage'
import { ExtractStage } from './stages/ExtractStage'
import { DatasetStage } from './stages/DatasetStage'
import { VisualizeStage } from './stages/VisualizeStage'
import { SeparationStage } from './stages/SeparationStage'

export function App() {
  const [stage, setStage] = useState<Stage>('corpus')
  const [status, setStatus] = useState<Status | null>(null)
  const [dark, setDark] = useState<boolean>(
    () => window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false,
  )
  const [offline, setOffline] = useState(false)

  const refresh = useCallback(async () => {
    try {
      setStatus(await api.get('/api/status'))
      setOffline(false)
    } catch {
      setOffline(true)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = (e: MediaQueryListEvent) => setDark(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
  }, [dark])

  const ctx: Ctx = { status, refresh, dark, go: setStage }

  return (
    <div className="app">
      <Sidebar stage={stage} ctx={ctx} />
      <main className="main">
        {offline && (
          <div className="notice notice-error">
            Can't reach the Vowelchemy API. Start it with <code>vowelchemy app</code> (or{' '}
            <code>uvicorn vowelchemy.api:app</code>).
          </div>
        )}
        {stage === 'corpus' && <CorpusStage ctx={ctx} />}
        {stage === 'align' && <AlignStage ctx={ctx} />}
        {stage === 'extract' && <ExtractStage ctx={ctx} />}
        {stage === 'dataset' && <DatasetStage ctx={ctx} />}
        {stage === 'visualize' && <VisualizeStage ctx={ctx} />}
        {stage === 'separation' && <SeparationStage ctx={ctx} />}
      </main>
    </div>
  )
}
