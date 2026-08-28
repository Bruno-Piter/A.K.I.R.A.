import { useState } from 'react'
import './App.css'
import type { GraphPayload } from './api/types.ts'
import HealthStatus from './components/HealthStatus.tsx'
import Chat from './pages/Chat.tsx'
import GraphExplorer from './pages/GraphExplorer.tsx'
import Ingest from './pages/Ingest.tsx'

type Tab = 'chat' | 'graph' | 'ingest'

const TABS: { id: Tab; label: string }[] = [
  { id: 'chat', label: 'Chat' },
  { id: 'graph', label: 'Grafo' },
  { id: 'ingest', label: 'Ingestão' },
]

function App() {
  const [tab, setTab] = useState<Tab>('chat')
  const [chatGraph, setChatGraph] = useState<GraphPayload | null>(null)
  const highlightIds = chatGraph?.nodes.map((node) => node.id) ?? []

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">
          <strong>A.K.I.R.A.</strong>
          <span className="brand__sub">Console</span>
        </div>
        <nav className="tabs" aria-label="Seções">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={tab === item.id ? 'tab tab--active' : 'tab'}
              onClick={() => setTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <HealthStatus />
      </header>
      <main className="app-main">
        {tab === 'chat' ? (
          <Chat onGraphContext={setChatGraph} />
        ) : null}
        {tab === 'graph' ? <GraphExplorer highlightIds={highlightIds} /> : null}
        {tab === 'ingest' ? <Ingest /> : null}
      </main>
    </div>
  )
}

export default App