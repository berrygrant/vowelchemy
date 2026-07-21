import { useEffect, useState } from 'react'
import { api } from '../api'
import type { GlossaryTerm } from '../types'

export function GlossaryDrawer({ onClose }: { onClose: () => void }) {
  const [terms, setTerms] = useState<GlossaryTerm[]>([])
  useEffect(() => {
    api.get('/api/glossary').then((r) => setTerms(r.terms)).catch(() => {})
  }, [])
  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-label="Glossary">
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <b>Glossary — what the terms mean</b>
          <button className="btn btn-small" onClick={onClose} aria-label="Close glossary">
            ✕
          </button>
        </div>
        <div className="browser">
          {terms.map((t) => (
            <div key={t.term} className="glossary-item">
              <div className="glossary-term">{t.term}</div>
              <div className="muted small">{t.definition}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
