import { useEffect, useMemo, useState } from 'react'
import { api, type Catalog, type Voice } from './api'
import Speak from './Speak'
import Studio from './Studio'
import Voices from './Voices'
import History from './History'
import { Notice } from './ui'

type Tab = 'speak' | 'studio' | 'voices' | 'history'

const TABS: { id: Tab; label: string }[] = [
  { id: 'speak', label: 'Speak' },
  { id: 'studio', label: 'Studio' },
  { id: 'voices', label: 'Voices' },
  { id: 'history', label: 'History' },
]

const DEFAULT_VOICE = 'en-US-AriaNeural'

export default function App() {
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [catalogError, setCatalogError] = useState('')
  const [tab, setTab] = useState<Tab>('speak')
  const [voiceId, setVoiceId] = useState(DEFAULT_VOICE)
  const [historyKey, setHistoryKey] = useState(0)

  useEffect(() => {
    api.catalog()
      .then(cat => {
        setCatalog(cat)
        if (!cat.voices.some(v => v.id === DEFAULT_VOICE) && cat.voices[0]) setVoiceId(cat.voices[0].id)
      })
      .catch(err => setCatalogError(err instanceof Error ? err.message : 'Could not load voices.'))
  }, [])

  // Refresh the History tab each time it is opened.
  const switchTab = (t: Tab) => {
    setTab(t)
    if (t === 'history') setHistoryKey(k => k + 1)
  }

  const voices: Voice[] = useMemo(() => catalog?.voices || [], [catalog])

  return (
    <div className="app">
      <header className="top">
        <div className="logo" aria-hidden>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" y1="19" x2="12" y2="23" />
            <line x1="8" y1="23" x2="16" y2="23" />
          </svg>
        </div>
        <div className="header-row">
          <div>
            <h1>VoiceForge</h1>
            <p className="tagline">Free AI Voice Studio</p>
          </div>
          <a className="back-link" href="/">← StoryForge</a>
        </div>
        <span className="free-pill">✓ 100% free · no account · no card · no paid tier</span>
      </header>

      <nav className="tabs" role="tablist">
        {TABS.map(t => (
          <button key={t.id} role="tab" aria-selected={tab === t.id}
            className={`tab ${tab === t.id ? 'active' : ''}`} onClick={() => switchTab(t.id)}>
            {t.label}
          </button>
        ))}
      </nav>

      {catalogError && (
        <Notice kind="err" title="Couldn't load the voice list">
          {catalogError} Pull down to refresh, or try again in a moment.
        </Notice>
      )}

      {!catalog && !catalogError && (
        <div className="center"><span className="spinner" /> Loading free voices…</div>
      )}

      {catalog && (
        <>
          {!catalog.edge_available && tab !== 'voices' && (
            <Notice kind="warn" title="Neural voices are unreachable right now">
              Generation automatically falls back to the bundled offline voice — free and fully working.
            </Notice>
          )}
          {tab === 'speak' && <Speak voices={voices} voiceId={voiceId} setVoiceId={setVoiceId} />}
          {tab === 'studio' && <Studio voices={voices} defaultVoice={voiceId} />}
          {tab === 'voices' && (
            <Voices
              voices={voices}
              edgeAvailable={catalog.edge_available}
              onUse={id => { setVoiceId(id); setTab('speak') }}
            />
          )}
          {tab === 'history' && <History refreshKey={historyKey} />}
        </>
      )}

      <p className="footer-note">
        VoiceForge uses free neural voices streamed from a public service, with an offline open-source
        voice built in as backup. No API keys, no subscriptions, no tracking. Generated audio is yours to
        download and use. Running on the same free server as StoryForge AI.
      </p>
    </div>
  )
}
