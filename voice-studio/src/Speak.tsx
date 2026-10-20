import { useEffect, useRef, useState } from 'react'
import { api, pollJob, type Job, type Voice } from './api'
import { Notice, Progress, RatePitch, ResultCard, VoiceSelect } from './ui'

const MAX = 5000

export default function Speak({ voices, voiceId, setVoiceId }: {
  voices: Voice[]
  voiceId: string
  setVoiceId: (id: string) => void
}) {
  const [text, setText] = useState('')
  const [rate, setRate] = useState(0)
  const [pitch, setPitch] = useState(0)
  const [job, setJob] = useState<Job | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const stopRef = useRef<(() => void) | null>(null)

  useEffect(() => () => stopRef.current?.(), [])

  const generate = async () => {
    setError('')
    if (!text.trim()) { setError('Enter some text first.'); return }
    if (text.length > MAX) { setError(`That text is too long. The limit is ${MAX.toLocaleString()} characters.`); return }
    setBusy(true)
    setJob({ id: '', kind: 'speak', status: 'queued', progress: 0, message: 'Waiting in queue' })
    try {
      const { job_id } = await api.speak({ text: text.trim(), voice: voiceId, rate, pitch })
      stopRef.current = pollJob(job_id, j => {
        setJob(j)
        if (j.status === 'done' || j.status === 'failed') {
          setBusy(false)
          if (j.status === 'failed') setError(j.message || 'The voice could not be generated. Please try again.')
        }
      })
    } catch (err) {
      setBusy(false)
      setError(err instanceof Error ? err.message : 'Could not start the task. Please try again.')
      setJob(null)
    }
  }

  const over = text.length > MAX

  return (
    <div className="card">
      <h2>Text to Speech</h2>
      <p className="help">Type or paste your words, pick a free voice, and get a downloadable MP3. No account, no card, no paid plan — ever.</p>

      <label htmlFor="speak-text">Your text</label>
      <textarea
        id="speak-text"
        placeholder="Example: Welcome to our studio. Today's story begins in a quiet town by the sea…"
        value={text}
        onChange={e => setText(e.target.value)}
      />
      <div className={`char-count ${over ? 'over' : ''}`}>{text.length.toLocaleString()} / {MAX.toLocaleString()} characters</div>

      <label htmlFor="speak-voice">Voice</label>
      <VoiceSelect id="speak-voice" voices={voices} value={voiceId} onChange={setVoiceId} />

      <RatePitch rate={rate} pitch={pitch} onRate={setRate} onPitch={setPitch} />

      {error && <Notice kind="err" title="Couldn't generate that">{error}</Notice>}

      <div style={{ marginTop: 16 }}>
        <button className="btn" onClick={generate} disabled={busy}>
          {busy ? 'Generating…' : '🎙 Generate voice MP3'}
        </button>
      </div>

      {job && job.status !== 'done' && <div style={{ marginTop: 14 }}><Progress job={job} /></div>}
      {job?.status === 'done' && job.record && <ResultCard rec={job.record} />}
    </div>
  )
}
