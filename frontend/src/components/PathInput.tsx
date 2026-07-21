import { useState } from 'react'
import { FolderPicker } from './FolderPicker'

// A text input paired with a "Browse…" button that opens the server folder/file
// picker. `mode='file'` picks a file (filtered by `exts`), otherwise a folder.
export function PathInput({
  value,
  onChange,
  placeholder,
  mode = 'dir',
  exts,
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  mode?: 'dir' | 'file'
  exts?: string
}) {
  const [picking, setPicking] = useState(false)
  // Open the picker at the current path (its parent folder, for a file field).
  const startPath = value ? (mode === 'file' ? value.replace(/\/[^/]*$/, '') : value) : undefined
  return (
    <div className="path-input">
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
      <button type="button" className="btn btn-small" onClick={() => setPicking(true)}>
        Browse…
      </button>
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
