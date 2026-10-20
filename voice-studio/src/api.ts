// Tiny API client. Server errors are always converted to plain human sentences —
// raw JSON must never reach the UI.

export type Voice = {
  id: string
  label: string
  locale: string
  lang: string
  region: string
  gender: string
  personalities: string
  engine: 'edge' | 'piper'
  engine_label: string
}

export type Catalog = {
  voices: Voice[]
  edge_available: boolean
  forced_engine: string | null
}

export type Record = {
  id: string
  kind: 'speak' | 'studio'
  title: string
  voice: string
  engine: string
  engine_label: string
  characters: number
  duration: number
  size: number
  created_at: number
  file_exists?: boolean
}

export type Job = {
  id: string
  kind: string
  status: 'queued' | 'running' | 'done' | 'failed'
  progress: number
  message: string
  record?: Record
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  if (res.ok) return (await res.json()) as T
  let message = `Something went wrong (status ${res.status}). Please try again.`
  try {
    const data = await res.json()
    const detail = data?.detail
    if (typeof detail === 'string') message = detail
    else if (detail && typeof detail === 'object' && typeof detail.message === 'string') message = detail.message
  } catch {
    /* keep the generic plain sentence */
  }
  throw new Error(message)
}

export const api = {
  catalog: () => request<Catalog>('/api/voice/voices'),
  speak: (body: { text: string; voice: string; rate: number; pitch: number; title?: string }) =>
    request<{ job_id: string }>('/api/voice/speak', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  studio: (body: { title?: string; blocks: { text: string; voice: string; rate: number; pitch: number }[] }) =>
    request<{ job_id: string }>('/api/voice/studio', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  job: (id: string) => request<Job>(`/api/voice/jobs/${id}`),
  history: () => request<{ history: Record[] }>('/api/voice/history'),
  remove: (id: string) => request<{ status: string }>(`/api/voice/history/${id}`, { method: 'DELETE' }),
}

export const audioUrl = (id: string, download = false) =>
  `/api/voice/audio/${id}${download ? '?download=1' : ''}`

export function pollJob(jobId: string, onUpdate: (job: Job) => void): () => void {
  let stopped = false
  let timer: ReturnType<typeof setTimeout>
  const tick = async () => {
    if (stopped) return
    try {
      const job = await api.job(jobId)
      if (stopped) return
      onUpdate(job)
      if (job.status === 'done' || job.status === 'failed') return
    } catch (err) {
      if (stopped) return
      onUpdate({
        id: jobId, kind: '', status: 'failed', progress: 0,
        message: err instanceof Error ? err.message : 'Task lost. Please try again.',
      })
      return
    }
    timer = setTimeout(tick, 1500)
  }
  timer = setTimeout(tick, 600)
  return () => { stopped = true; clearTimeout(timer) }
}

export const formatBytes = (n: number) =>
  n > 1_000_000 ? `${(n / 1_048_576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`

export const formatDate = (ts: number) =>
  new Date(ts * 1000).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
