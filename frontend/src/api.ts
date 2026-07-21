// Thin fetch wrapper. Every request carries a per-browser session id so the
// backend can keep the loaded dataset between calls. Paths already include the
// `/api` prefix; in dev, Vite proxies `/api` to the uvicorn backend.

const SESSION_KEY = 'vowelchemy-session'

function sessionId(): string {
  let id = localStorage.getItem(SESSION_KEY)
  if (!id) {
    id = 'sess-' + Math.random().toString(36).slice(2) + '-' + Date.now().toString(36)
    localStorage.setItem(SESSION_KEY, id)
  }
  return id
}

function headers(json = true): Record<string, string> {
  const h: Record<string, string> = { 'X-Vowelchemy-Session': sessionId() }
  if (json) h['Content-Type'] = 'application/json'
  return h
}

async function handle(res: Response) {
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const j = await res.json()
      if (j && j.detail) detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  get: (path: string) => fetch(path, { headers: headers(false) }).then(handle),
  post: (path: string, body?: unknown) =>
    fetch(path, { method: 'POST', headers: headers(), body: JSON.stringify(body ?? {}) }).then(handle),
  upload: (path: string, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return fetch(path, {
      method: 'POST',
      headers: { 'X-Vowelchemy-Session': sessionId() },
      body: fd,
    }).then(handle)
  },
  download: async (path: string, filename: string) => {
    const res = await fetch(path, { headers: headers(false) })
    if (!res.ok) throw new Error('Download failed')
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },
}

export { sessionId }
