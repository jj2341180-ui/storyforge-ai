import type { ReactNode } from 'react'
import type { Job, Record as Rec, Voice } from './api'
import { audioUrl, formatBytes, formatDate } from './api'

export function Notice({ kind, title, children }: { kind: 'warn' | 'err' | 'info'; title?: string; children: ReactNode }) {
  return (
    <div className={`notice ${kind}`} role="alert">
      {title && <strong>{title}</strong>}
      {children}
    </div>
  )
}

export function Progress({ job }: { job: Job }) {
  const pct = Math.round((job.progress || 0) * 100)
  return (
    <div>
      <div className="progress-wrap">
        <div className="progress-bar" style={{ width: `${Math.max(4, pct)}%` }} />
      </div>
      <div className="progress-msg">{job.message || 'Working…'} {pct > 0 && `· ${pct}%`}</div>
    </div>
  )
}

export function VoiceSelect({
  voices, value, onChange, id,
}: { voices: Voice[]; value: string; onChange: (id: string) => void; id?: string }) {
  const featured = ['en-US-AriaNeural', 'en-US-GuyNeural', 'en-GB-SoniaNeural', 'en-GB-RyanNeural',
    'en-AU-NatashaNeural', 'en-IN-NeerjaNeural', 'en-NG-EzinneNeural', 'en-ZA-LeahNeural']
  const featuredVoices = featured.map(f => voices.find(v => v.id === f)).filter(Boolean) as Voice[]
  const byLocale = new Map<string, Voice[]>()
  for (const v of voices) {
    if (featured.includes(v.id)) continue
    const list = byLocale.get(v.locale) || []
    list.push(v)
    byLocale.set(v.locale, list)
  }
  return (
    <select id={id} value={value} onChange={e => onChange(e.target.value)}>
      {featuredVoices.length > 0 && (
        <optgroup label="Featured free voices">
          {featuredVoices.map(v => <option key={v.id} value={v.id}>{v.label} — {v.locale} ({v.gender})</option>)}
        </optgroup>
      )}
      {[...byLocale.keys()].sort().map(loc => (
        <optgroup key={loc} label={loc}>
          {byLocale.get(loc)!.map(v => (
            <option key={v.id} value={v.id}>
              {v.label} ({v.gender}){v.engine === 'piper' ? ' · offline' : ''}
            </option>
          ))}
        </optgroup>
      ))}
    </select>
  )
}

export function RatePitch({
  rate, pitch, onRate, onPitch,
}: { rate: number; pitch: number; onRate: (n: number) => void; onPitch: (n: number) => void }) {
  return (
    <div>
      <label>Speed</label>
      <input type="range" min={-50} max={100} step={5} value={rate} onChange={e => onRate(Number(e.target.value))} />
      <div className="range-row"><span>Slower</span><span className="range-value">{rate === 0 ? 'Normal' : `${rate > 0 ? '+' : ''}${rate}%`}</span><span>Faster</span></div>
      <label>Pitch</label>
      <input type="range" min={-50} max={50} step={5} value={pitch} onChange={e => onPitch(Number(e.target.value))} />
      <div className="range-row"><span>Lower</span><span className="range-value">{pitch === 0 ? 'Normal' : `${pitch > 0 ? '+' : ''}${pitch} Hz`}</span><span>Higher</span></div>
    </div>
  )
}

export function EngineBadge({ rec }: { rec: Rec }) {
  const offline = rec.engine.includes('piper')
  return <span className={`badge ${offline ? 'offline' : 'neural'}`}>{rec.engine_label}</span>
}

export function ResultCard({ rec }: { rec: Rec }) {
  return (
    <div className="result">
      <div className="title">{rec.title}</div>
      <div className="meta">
        <EngineBadge rec={rec} />
        <span>{rec.voice}</span>
        <span>· {rec.duration}s</span>
        <span>· {formatBytes(rec.size)}</span>
      </div>
      <audio controls preload="none" src={audioUrl(rec.id)} />
      <div className="btn-row" style={{ marginTop: 8 }}>
        <a className="btn small" style={{ textDecoration: 'none' }} href={audioUrl(rec.id, true)} download={`${rec.title}.mp3`}>
          ⬇ Download MP3
        </a>
      </div>
      <div className="footer-note">Saved {formatDate(rec.created_at)} · download it now to keep it forever.</div>
    </div>
  )
}
