import { useState } from 'react'
import type { DragEvent } from 'react'
import { api } from '../api'
import { FolderPicker } from './FolderPicker'

interface Candidate {
  path: string
  score: number
  matched: number
  total: number
  depth: number
  file?: string
}

// Names inside a dropped folder (Chrome hands back at most 100 per call).
async function listEntries(entry: FileSystemDirectoryEntry, limit = 300): Promise<string[]> {
  const reader = entry.createReader()
  const names: string[] = []
  const batch = () => new Promise<FileSystemEntry[]>((res, rej) => reader.readEntries(res, rej))
  for (;;) {
    const got = await batch()
    if (!got.length) break
    for (const e of got) names.push(e.name)
    if (names.length >= limit) break
  }
  return names.slice(0, limit)
}

// Some sources (file managers, a dragged path) hand over the path itself.
function pathFromText(dt: DataTransfer): string | null {
  for (const line of dt.getData('text/uri-list').split(/\r?\n/)) {
    const s = line.trim()
    if (!s || s.startsWith('#') || !s.startsWith('file:')) continue
    try {
      let p = decodeURIComponent(new URL(s).pathname)
      if (/^\/[A-Za-z]:/.test(p)) p = p.slice(1).replace(/\//g, '\\') // file:///C:/…
      return p
    } catch {
      /* not a URL */
    }
  }
  const text = dt.getData('text/plain').trim()
  return /^(\/|~\/|[A-Za-z]:\\|\\\\)/.test(text) && !text.includes('\n') ? text : null
}

// A text input for a path on the machine running the app, with three ways to
// fill it besides typing: drop a folder (or an alias/shortcut, or a file inside
// it) from Finder/Explorer, open the system's own folder chooser, or browse
// with the in-app picker. Browsers keep a dropped item's location secret, so
// the drop sends its name and top-level listing and the server finds the
// folder in the usual places, asking only when several folders share the name.
export function PathInput({
  value,
  onChange,
  placeholder,
  mode = 'dir',
  exts,
  nativeDialog = false,
  dropHint,
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  mode?: 'dir' | 'file'
  exts?: string
  nativeDialog?: boolean
  dropHint?: string
}) {
  const [picking, setPicking] = useState(false)
  const [over, setOver] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [candidates, setCandidates] = useState<Candidate[]>([])
  // Open the picker at the current path (its parent folder, for a file field).
  const startPath = value ? (mode === 'file' ? value.replace(/\/[^/]*$/, '') : value) : undefined

  const choose = (p: string) => {
    onChange(p)
    setCandidates([])
    setMessage('')
  }
  const pick = (c: Candidate) => choose(mode === 'file' && c.file ? c.file : c.path)

  const locate = async (name: string, entries: string[], kind: 'directory' | 'file', fallbackToFile = false) => {
    setBusy(true)
    setMessage('')
    setCandidates([])
    try {
      let res = (await api.post('/api/locate-folder', { name, entries, kind })) as {
        name: string
        candidates: Candidate[]
      }
      if (!res.candidates.length && fallbackToFile) {
        res = await api.post('/api/locate-folder', { name, entries: [], kind: 'file' })
      }
      const c = res.candidates
      if (!c.length) {
        setMessage(
          `Couldn't find “${res.name}” in the usual places (Desktop, Documents, Downloads, home, mounted drives). Use Choose… / Browse…, or type the path.`,
        )
        return
      }
      const complete = c.filter((x) => x.total > 0 && x.matched === x.total)
      if (c.length === 1 || (complete.length === 1 && complete[0] === c[0])) {
        pick(c[0])
        setMessage(`Found it: ${mode === 'file' && c[0].file ? c[0].file : c[0].path}`)
        return
      }
      setCandidates(c)
      setMessage(`Several folders are named “${res.name}” — pick the right one:`)
    } catch (e) {
      setMessage((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const onDrop = async (ev: DragEvent<HTMLDivElement>) => {
    ev.preventDefault()
    setOver(false)
    const dt = ev.dataTransfer
    const direct = pathFromText(dt)
    if (direct) {
      choose(direct)
      return
    }
    const item = dt.items?.[0]
    const entry = item && typeof item.webkitGetAsEntry === 'function' ? item.webkitGetAsEntry() : null
    if (entry?.isDirectory) {
      const names = await listEntries(entry as FileSystemDirectoryEntry).catch(() => [] as string[])
      await locate(entry.name, names, 'directory')
      return
    }
    const name = entry?.name ?? dt.files?.[0]?.name
    if (!name) {
      setMessage('Nothing usable was dropped — drop a folder from Finder or Explorer.')
      return
    }
    // A dropped file: an alias/shortcut stands for a folder of (nearly) the same
    // name; anything else is a file inside the corpus, so find its folder.
    if (mode === 'file') await locate(name, [], 'file')
    else await locate(name, [], 'directory', true)
  }

  const openNative = async () => {
    setBusy(true)
    setMessage('')
    try {
      const res = (await api.post('/api/native-folder-dialog', { start: startPath ?? null, mode })) as {
        path: string | null
        cancelled: boolean
      }
      if (res.path) choose(res.path)
    } catch (e) {
      setMessage((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="path-input-wrap">
      <div
        className={`path-input${over ? ' drop-over' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          e.dataTransfer.dropEffect = 'copy'
          setOver(true)
        }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
      >
        <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
        {nativeDialog && (
          <button
            type="button"
            className="btn btn-small"
            onClick={openNative}
            disabled={busy}
            title={mode === 'file' ? "Open your system's file chooser" : "Open your system's folder chooser"}
          >
            📂 Choose…
          </button>
        )}
        <button type="button" className="btn btn-small" onClick={() => setPicking(true)} disabled={busy}>
          Browse…
        </button>
      </div>
      {(busy || message || dropHint) && (
        <div className="muted small path-hint">{busy ? 'Looking for that folder…' : message || dropHint}</div>
      )}
      {candidates.length > 0 && (
        <div className="path-candidates">
          {candidates.map((c) => (
            <div key={c.path} className="env-row">
              <div>
                <div className="mono small">{c.path}</div>
                {c.total > 0 && (
                  <div className="muted small">
                    {c.matched} of {c.total} dropped items found here
                  </div>
                )}
              </div>
              <button type="button" className="btn btn-small" onClick={() => pick(c)}>
                Use this
              </button>
            </div>
          ))}
          <div className="row">
            <button type="button" className="btn btn-small" onClick={() => setCandidates([])}>
              None of these
            </button>
          </div>
        </div>
      )}
      {picking && (
        <FolderPicker
          mode={mode}
          exts={exts}
          startPath={startPath}
          onPick={(p) => {
            onChange(p)
            setPicking(false)
          }}
          onClose={() => setPicking(false)}
        />
      )}
    </div>
  )
}
