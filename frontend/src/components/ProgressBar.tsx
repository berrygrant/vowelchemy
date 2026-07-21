export function ProgressBar({ percent, phase }: { percent: number | null; phase: string | null }) {
  const indeterminate = percent === null || percent === undefined
  return (
    <div className="progress">
      <div className="progress-head">
        <span className="progress-phase">{phase ?? 'Working…'}</span>
        {!indeterminate && <span className="progress-pct">{Math.round(percent as number)}%</span>}
      </div>
      <div className="progress-track">
        <div
          className={`progress-fill ${indeterminate ? 'indeterminate' : ''}`}
          style={indeterminate ? undefined : { width: `${percent}%` }}
        />
      </div>
    </div>
  )
}
