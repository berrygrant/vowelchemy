import { useEffect, useState } from 'react'
import { api } from '../api'
import { saveText } from '../lib'
import type { Ctx, Project } from '../types'

// Reproducible recipe (R1) + persistent named projects (R10) for the sidebar.
export function SessionPanel({ ctx }: { ctx: Ctx }) {
  const [projects, setProjects] = useState<Project[]>([])
  const [name, setName] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  const loadList = () => api.get('/api/projects').then((r) => setProjects(r.projects)).catch(() => {})
  useEffect(() => {
    loadList()
  }, [])

  const flash = (m: string) => {
    setMsg(m)
    window.setTimeout(() => setMsg(''), 2500)
  }

  const downloadRecipe = async () => {
    try {
      const r = await api.get('/api/recipe')
      saveText(JSON.stringify(r, null, 2), 'vowelchemy_recipe.json', 'application/json')
    } catch (e) {
      flash((e as Error).message)
    }
  }

  const loadRecipe = async (file: File) => {
    try {
      await api.post('/api/recipe', { recipe: JSON.parse(await file.text()) })
      await ctx.refresh()
      flash('Recipe applied')
    } catch (e) {
      flash((e as Error).message)
    }
  }

  const saveProject = async () => {
    if (!name.trim()) return
    setBusy(true)
    try {
      await api.post('/api/projects/save', { name })
      setName('')
      await loadList()
      flash('Project saved')
    } finally {
      setBusy(false)
    }
  }

  const loadProject = async (n: string) => {
    setBusy(true)
    try {
      await api.post('/api/projects/load', { name: n })
      await ctx.refresh()
      flash(`Loaded ${n}`)
      ctx.go('dataset')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="side-section">
      <div className="side-heading">Session</div>
      <div className="side-actions">
        <button className="btn btn-small" onClick={downloadRecipe}>
          ⬇︎ Recipe
        </button>
        <label className="btn btn-small file-btn">
          ⬆︎ Recipe
          <input type="file" accept=".json" onChange={(e) => e.target.files?.[0] && loadRecipe(e.target.files[0])} />
        </label>
      </div>
      <div className="side-project-save">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="project name"
          aria-label="Project name"
        />
        <button className="btn btn-small" onClick={saveProject} disabled={busy || !name.trim()}>
          Save
        </button>
      </div>
      {projects.length > 0 && (
        <div className="side-projects">
          {projects.slice(0, 6).map((p) => (
            <button key={p.name} className="project-row" onClick={() => loadProject(p.name)} disabled={busy}>
              📂 {p.name}
              {p.has_tracks ? ' ·traj' : ''}
            </button>
          ))}
        </div>
      )}
      {msg && <div className="muted small">{msg}</div>}
    </div>
  )
}
