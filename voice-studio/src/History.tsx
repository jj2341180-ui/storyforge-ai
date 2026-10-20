import { useCallback, useEffect, useState } from 'react'
import { api, formatBytes, formatDate, type Record as Rec } from './api'
import { EngineBadge, Notice } from './ui'

export default function History({ refreshKey }: { refreshKey: number }) {
  const [items, setItems] = useState<Rec[] | null>(null)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try {
      const { history } = await api.history()
      setItems(history)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load history.')
    }
  }, [])

  useEffect(() => { load() }, [load, refreshKey])

  const remove = async (id: string) => {
    try {
      await api.remove(id)
      setItems(list => (list || []).filter(r => r.id !== id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete that recording.')
    }
  }

  if (error) return <Notice kind="err">{error}</Notice>
  if (!items) return <div className="center"><span className="spinner" /> Loading your recordings…</div>
  if (items.length === 0) {
    return (
      <div className="card">
        <h2>History &amp; Downloads</h2>
        <div className="empty">No recordings yet. Generate your first voice on the Speak tab.</div>
      </div>
    )
  }

  return (
    <div className="card">
      <h2>History &amp; Downloads</h2>
      <p className="help">Every MP3 you create appears here. Play it, download it, or delete it.</p>
      <Notice kind="info" title="Keep what matters">
        This free server's disk is wiped whenever the app updates. Tap <b>Download MP3</b> to save recordings to your phone — those copies are yours forever.
      </Notice>
      {items.map(r => (
        <div className="hist-item" key={r.id}>
          <div className="hist-top">
            <div>
              <div className="hist-title">{r.title}</div>
              <div className="hist-meta">
                <EngineBadge rec={r} />
                <span>{r.kind === 'studio' ? 'Studio' : 'Speech'} · {r.voice}</span>
                <span>· {r.duration}s · {formatBytes(r.size)}</span>
                <span>· {formatDate(r.created_at)}</span>
              </div>
            </div>
          </div>
          {r.file_exists === false ? (
            <Notice kind="warn" title="File no longer on the server">
              A server update cleared this recording. Re-create it from the Speak tab — any copy you downloaded to your phone is unaffected.
            </Notice>
          ) : (
            <>
              <audio controls preload="none" src={`/api/voice/audio/${r.id}`} />
              <div className="btn-row">
                <a className="btn small" style={{ textDecoration: 'none' }} href={`/api/voice/audio/${r.id}?download=1`} download={`${r.title}.mp3`}>⬇ Download MP3</a>
                <button className="btn small ghost" onClick={() => remove(r.id)}>Delete</button>
              </div>
            </>
          )}
        </div>
      ))}
    </div>
  )
}
