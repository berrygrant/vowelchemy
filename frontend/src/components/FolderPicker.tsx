import { useEffect, useState } from 'react'
import { api } from '../api'
import type { BrowseResult } from '../types'

// A modal that browses the *server* filesystem (the backend runs on the user's
// own machine), so a corpus folder can be clicked instead of typed.
export function FolderPicker({
  mode = 'dir',
  exts,
  title,
  startPath,
  onPick,
  onClose,
}: {
  mode?: 'dir' | 'file'
  exts?: string
  title?: string
  startPath?: string
  onPick: (path: string) => void
  onClose: () => void
}) {
  const [data, setData] = useState<BrowseResult | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const load = async (path?: string, fallbackHome = false) => {
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams()
      if (path) params.set('path', path)
      if (mode === 'file' && exts) params.set('exts', exts)
      const qs = params.toString()
      setData(await api.get('/api/browse' + (qs ? `?${qs}` : '')))
    } catch (e) {
      if (fallbackHome) {
        await load() // the given path was bad; fall back to home
        return
      }
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load(startPath || undefined, Boolean(startPath))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <b>{title ?? (mode === 'file' ? 'Select a file' : 'Select a folder')}</b>
          <button className="btn btn-small" onClick={onClose}>
            ✕
          </button>
        </div>
        <div className="row-between">
          <code className="path grow">{data?.path ?? '…'}</code>
          <div className="picker-nav">
            <button className="btn btn-small" disabled={!data?.home} onClick={() => load(data?.home)}>
              Home
            </button>
            <button
              className="btn btn-small"
              disabled={!data?.parent}
              onClick={() => data?.parent && load(data.parent)}
            >
              ↑ Up
            </button>
          </div>
        </div>
        {error && <div className="notice notice-error">{error}</div>}
        <div className="browser">
          {loading && <p className="muted small">Loading…</p>}
          {data?.dirs.map((d) => (
            <div key={d.path} className="browse-row">
              <button className="browse-name" onClick={() => load(d.path)}>
                <span className="folder-ico">📁</span> {d.name}{' '}
                {d.has_wav ? <span title="contains audio">🔊</span> : null}{' '}
                {d.has_transcript ? <span title="contains transcripts">📝</span> : null}
              </button>
              {mode === 'dir' && (
                <button className="btn btn-small" onClick={() => onPick(d.path)}>
                  Select
                </button>
              )}
            </div>
          ))}
          {mode === 'file' &&
            data?.files.map((f) => (
              <div key={f.path} className="browse-row">
                <button className="browse-name" onClick={() => onPick(f.path)}>
                  📄 {f.name}
                </button>
              </div>
            ))}
          {data && data.dirs.length === 0 && (mode === 'dir' || data.files.length === 0) && (
            <p className="muted small">
              {mode === 'file' ? 'No sub-folders or matching files here.' : 'No sub-folders here.'}
            </p>
          )}
        </div>
        {mode === 'dir' && data && (
          <div className="modal-foot">
            <button className="btn btn-primary" onClick={() => onPick(data.path)}>
              Use this folder
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
