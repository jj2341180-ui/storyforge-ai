import { useEffect, useRef, useState } from 'react'
import { api, pollJob, type Job, type Voice } from './api'
import { Notice, Progress, ResultCard, VoiceSelect } from './ui'

const MAX_BLOCKS = 10
const MAX_CHARS = 2000

type Block = { key: number; text: string; voice: string; rate: number }

export default function Studio({ voices, defaultVoice }: { voices: Voice[]; defaultVoice: string }) {
  const [title, setTitle] = useState('')
  const [blocks, setBlocks] = useState<Block[]>([{ key: 1, text: '', voice: defaultVoice, rate: 0 }])
  const [job, setJob] = useState<Job | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const stopRef = useRef<(() => void) | null>(null)
  const keyRef = useRef(2)

  useEffect(() => () => stopRef.current?.(), [])

  const update = (key: number, patch: Partial<Block>) =>
    setBlocks(bs => bs.map(b => (b.key === key ? { ...b, ...patch } : b)))
  const remove = (key: number) => setBlocks(bs => (bs.length === 1 ? bs : bs.filter(b => b.key !== key)))
  const move = (idx: number, dir: -1 | 1) =>
    setBlocks(bs => {
      const next = [...bs]
      const j = idx + dir
      if (j < 0 || j >= next.length) return bs
      ;[next[idx], next[j]] = [next[j], next[idx]]
      return next
    })
  const add = () => {
    if (blocks.length >= MAX_BLOCKS) { setError(`The studio allows at most ${MAX_BLOCKS} parts in one project.`); return }
    setBlocks(bs => [...bs, { key: keyRef.current++, text: '', voice: defaultVoice, rate: 0 }])
  }

  const build = async () => {
    setError('')
    const filled = blocks.filter(b => b.text.trim())
    if (filled.length === 0) { setError('Add at least one spoken line first.'); return }
    const tooLong = filled.find(b => b.text.length > MAX_CHARS)
    if (tooLong) { setError(`One part is too long. Each part allows up to ${MAX_CHARS.toLocaleString()} characters.`); return }
    setBusy(true)
    setJob({ id: '', kind: 'studio', status: 'queued', progress: 0, message: 'Waiting in queue' })
    try {
      const { job_id } = await api.studio({
        title: title.trim() || undefined,
        blocks: filled.map(b => ({ text: b.text.trim(), voice: b.voice, rate: b.rate, pitch: 0 })),
      })
      stopRef.current = pollJob(job_id, j => {
        setJob(j)
        if (j.status === 'done' || j.status === 'failed') {
          setBusy(false)
          if (j.status === 'failed') setError(j.message || 'The studio project failed. Please try again.')
        }
      })
    } catch (err) {
      setBusy(false)
      setError(err instanceof Error ? err.message : 'Could not start the task. Please try again.')
      setJob(null)
    }
  }

  return (
    <div className="card">
      <h2>Multi-voice Studio</h2>
      <p className="help">Build one long MP4 from several parts — each part can use a different narrator voice, like a podcast or audiobook scene.</p>

      <label htmlFor="studio-title">Project title (optional)</label>
      <input id="studio-title" type="text" placeholder="Example: Episode 1 — The Lighthouse" value={title} onChange={e => setTitle(e.target.value)} />

      {blocks.map((b, idx) => (
        <div className="block-card" key={b.key}>
          <div className="block-head">
            <b>Part {idx + 1}</b>
            <div className="btns">
              <button className="icon-btn" aria-label={`Move part ${idx + 1} up`} onClick={() => move(idx, -1)}>↑</button>
              <button className="icon-btn" aria-label={`Move part ${idx + 1} down`} onClick={() => move(idx, 1)}>↓</button>
              <button className="icon-btn" aria-label={`Remove part ${idx + 1}`} onClick={() => remove(b.key)}>✕</button>
            </div>
          </div>
          <label>Voice for this part</label>
          <VoiceSelect voices={voices} value={b.voice} onChange={v => update(b.key, { voice: v })} />
          <label>Spoken words</label>
          <textarea style={{ minHeight: 90 }} placeholder="Type what this narrator says…" value={b.text}
            onChange={e => update(b.key, { text: e.target.value })} />
          <div className="char-count">{b.text.length.toLocaleString()} / {MAX_CHARS.toLocaleString()}</div>
          <label>Speed: {b.rate === 0 ? 'Normal' : `${b.rate > 0 ? '+' : ''}${b.rate}%`}</label>
          <input type="range" min={-50} max={100} step={5} value={b.rate} onChange={e => update(b.key, { rate: Number(e.target.value) })} />
        </div>
      ))}

      <button className="btn secondary" onClick={add} disabled={blocks.length >= MAX_BLOCKS}>＋ Add another part ({blocks.length}/{MAX_BLOCKS})</button>

      {error && <div style={{ marginTop: 12 }}><Notice kind="err" title="Couldn't build that">{error}</Notice></div>}

      <div style={{ marginTop: 14 }}>
        <button className="btn" onClick={build} disabled={busy}>{busy ? 'Building…' : '🎧 Build full audio (one MP3)'}</button>
      </div>

      {job && job.status !== 'done' && <div style={{ marginTop: 14 }}><Progress job={job} /></div>}
      {job?.status === 'done' && job.record && <ResultCard rec={job.record} />}
    </div>
  )
}
