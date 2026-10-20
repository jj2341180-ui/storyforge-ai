import { useMemo, useState } from 'react'
import { api, type Voice } from './api'
import { Notice } from './ui'

const SAMPLE = (label: string) =>
  `Hi, I'm ${label}. This is how I sound when I read your words — completely free, with no paid plan.`

export default function Voices({
  voices, edgeAvailable, onUse,
}: { voices: Voice[]; edgeAvailable: boolean; onUse: (id: string) => void }) {
  const [query, setQuery] = useState('')
  const [lang, setLang] = useState('en')
  const [gender, setGender] = useState('all')
  const [preview, setPreview] = useState<Record<string, string>>({}) // voiceId -> audio url
  const [busy, setBusy] = useState<string>('')
  const [error, setError] = useState('')

  const languages = useMemo(
    () => [...new Set(voices.map(v => v.lang))].sort(),
    [voices],
  )

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return voices.filter(v => {
      if (lang !== 'all' && v.lang !== lang) return false
      if (gender !== 'all' && v.gender !== gender) return false
      if (q && !`${v.label} ${v.locale} ${v.personalities}`.toLowerCase().includes(q)) return false
      return true
    }).slice(0, 120)
  }, [voices, query, lang, gender])

  const playPreview = async (v: Voice) => {
    setError('')
    setBusy(v.id)
    try {
      const { job_id } = await api.speak({ text: SAMPLE(v.label), voice: v.id, rate: 0, pitch: 0 })
      // Poll until finished, then reveal the player.
      const timer = setInterval(async () => {
        try {
          const job = await api.job(job_id)
          if (job.status === 'done' && job.record) {
            clearInterval(timer)
            setPreview(p => ({ ...p, [v.id]: `/api/voice/audio/${job.record!.id}` }))
            setBusy('')
          } else if (job.status === 'failed') {
            clearInterval(timer)
            setBusy('')
            setError(job.message || 'Preview failed. Please try again.')
          }
        } catch {
          clearInterval(timer)
          setBusy('')
          setError('Preview failed. Please try again.')
        }
      }, 1200)
    } catch (err) {
      setBusy('')
      setError(err instanceof Error ? err.message : 'Preview failed. Please try again.')
    }
  }

  return (
    <div className="card">
      <h2>Voice Library</h2>
      <p className="help">{voices.length} free voices in {languages.length} languages. Neural voices stream from a free public service; offline voices work with no network at all.</p>

      {!edgeAvailable && (
        <Notice kind="warn" title="Neural voice service is unreachable right now">
          New speech will automatically use the bundled offline voice instead — still free, still an MP3. The full neural list returns when the network recovers.
        </Notice>
      )}

      <div className="filters">
        <input type="text" placeholder="Search name or language…" value={query} onChange={e => setQuery(e.target.value)} aria-label="Search voices" />
        <select value={lang} onChange={e => setLang(e.target.value)} aria-label="Filter by language">
          <option value="all">All languages</option>
          {languages.map(l => <option key={l} value={l}>{l}</option>)}
        </select>
      </div>
      <div className="filters" style={{ gridTemplateColumns: '1fr' }}>
        <select value={gender} onChange={e => setGender(e.target.value)} aria-label="Filter by gender">
          <option value="all">Any gender</option>
          <option value="female">Female</option>
          <option value="male">Male</option>
          <option value="neutral">Neutral</option>
        </select>
      </div>

      {error && <Notice kind="err">{error}</Notice>}

      <div className="voice-grid">
        {filtered.map(v => (
          <div className="voice-card" key={v.id}>
            <div className="vc-top">
              <div>
                <div className="vc-name">{v.label}</div>
                <div className="vc-sub">{v.locale} · {v.gender}{v.personalities ? ` · ${v.personalities}` : ''}</div>
              </div>
              <span className={`badge ${v.engine === 'piper' ? 'offline' : 'neural'}`}>
                {v.engine === 'piper' ? 'Offline' : 'Neural'}
              </span>
            </div>
            {preview[v.id] && <audio controls autoPlay src={preview[v.id]} style={{ marginTop: 10 }} />}
            <div className="vc-actions">
              <button className="btn small" onClick={() => onUse(v.id)} disabled={busy === v.id}>Use this voice</button>
              <button className="btn small ghost" onClick={() => playPreview(v)} disabled={busy === v.id}>
                {busy === v.id ? 'Preparing…' : '▶ Preview'}
              </button>
            </div>
          </div>
        ))}
        {filtered.length === 0 && <div className="empty">No voices match those filters.</div>}
      </div>
    </div>
  )
}
