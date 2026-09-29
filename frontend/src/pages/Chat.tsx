import { useMemo, useRef, useState } from 'react'
import { apiStatus, streamChat } from '../api/client.ts'
import type { ChatSource, GraphPayload } from '../api/types.ts'
import GraphScene from '../components/graph/GraphScene.tsx'

type ChatProps = {
  onGraphContext?: (graph: GraphPayload | null) => void
}

type Role = 'user' | 'assistant'

type Message = {
  id: string
  role: Role
  content: string
  stage?: string
  sources?: ChatSource[]
  graph?: GraphPayload | null
  streaming?: boolean
  usedMock?: boolean
}

function newId(): string {
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function graphFromSources(sources: ChatSource[]): GraphPayload {
  const nodes: GraphPayload['nodes'] = []
  const links: GraphPayload['links'] = []
  const seen = new Set<string>()
  for (const source of sources) {
    const docId = source.document_id || `doc-${source.chunk_id}`
    if (!seen.has(docId)) {
      seen.add(docId)
      nodes.push({
        id: docId,
        label: source.title || docId,
        type: 'document',
        val: 2.4,
      })
    }
    const chunkId = source.chunk_id || `chunk-${nodes.length}`
    if (!seen.has(chunkId)) {
      seen.add(chunkId)
      nodes.push({
        id: chunkId,
        label: source.excerpt || source.title || chunkId,
        type: 'chunk',
        val: 1.2,
      })
      links.push({
        source: docId,
        target: chunkId,
        type: 'HAS_CHUNK',
        strength: source.score != null ? Math.max(0.4, source.score) : 1,
      })
    }
  }
  return { nodes, links }
}

export default function Chat({ onGraphContext }: ChatProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [draft, setDraft] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [threadId, setThreadId] = useState<string | null>(null)
  const [liveGraph, setLiveGraph] = useState<GraphPayload | null>(null)
  const liveGraphRef = useRef<GraphPayload | null>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const lastGraph = useMemo(() => {
    if (liveGraph && liveGraph.nodes.length) return liveGraph
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const graph = messages[i]?.graph
      if (graph && graph.nodes.length) return graph
    }
    return null
  }, [messages, liveGraph])

  const highlightIds = lastGraph?.nodes.map((node) => node.id) ?? []

  function applyGraph(graph: GraphPayload | null | undefined): void {
    if (!graph || !graph.nodes.length) return
    liveGraphRef.current = graph
    setLiveGraph(graph)
    onGraphContext?.(graph)
  }

  async function send(): Promise<void> {
    const text = draft.trim()
    if (!text || streaming) return

    const userMsg: Message = { id: newId(), role: 'user', content: text }
    const assistantId = newId()
    const assistantMsg: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      stage: 'enviando',
      streaming: true,
    }

    setDraft('')
    setStreaming(true)
    setMessages((prev) => [...prev, userMsg, assistantMsg])

    const patchAssistant = (updater: (current: Message) => Message) => {
      setMessages((prev) =>
        prev.map((item) => (item.id === assistantId ? updater(item) : item)),
      )
    }

    const result = await streamChat(
      {
        message: text,
        thread_id: threadId,
        document_ids: [],
      },
      {
        onStage: (stage) => {
          patchAssistant((current) => ({ ...current, stage }))
        },
        onToken: (token) => {
          patchAssistant((current) => ({
            ...current,
            content: current.content + token,
            stage: current.stage,
          }))
          queueMicrotask(() => {
            listRef.current?.scrollTo({ top: listRef.current.scrollHeight })
          })
        },
        onSources: (sources) => {
          patchAssistant((current) => ({ ...current, sources }))
          if (!liveGraphRef.current?.nodes.length) {
            applyGraph(graphFromSources(sources))
          }
        },
        onGraphContext: (graph) => {
          patchAssistant((current) => ({ ...current, graph }))
          applyGraph(graph)
        },
        onDone: (content) => {
          if (content && typeof content === 'object') {
            const record = content as Record<string, unknown>
            const tid = record.thread_id
            if (typeof tid === 'string' && tid) setThreadId(tid)
            const nested =
              record.graph_context ?? record.graph_payload ?? record.graph ?? record.content
            if (nested && typeof nested === 'object') {
              const payload = nested as GraphPayload
              if (Array.isArray(payload.nodes) && payload.nodes.length) {
                patchAssistant((current) => ({ ...current, graph: payload }))
                applyGraph(payload)
              }
            }
          }
        },
        onError: (error) => {
          patchAssistant((current) => ({
            ...current,
            content: current.content || `Erro no stream: ${error.message}`,
            streaming: false,
          }))
        },
      },
    )

    patchAssistant((current) => ({
      ...current,
      streaming: false,
      stage: undefined,
      usedMock: result.usedMock,
      graph: current.graph ?? liveGraphRef.current,
    }))
    setStreaming(false)
  }

  return (
    <div className="page page--chat">
      <section className="chat-pane">
        <div ref={listRef} className="chat-log" aria-live="polite">
          {messages.length === 0 ? (
            <div className="empty-state">
              <h2>Chat A.K.I.R.A.</h2>
              <p>
                Pergunte sobre os documentos ingeridos. A resposta chega em SSE e o grafo
                ao lado destaca o contexto recuperado.
              </p>
              <p className="empty-state__hint">
                Se o backend estiver fora, a UI usa um stream mock em português.
              </p>
            </div>
          ) : (
            messages.map((message) => (
              <article
                key={message.id}
                className={`bubble bubble--${message.role}`}
              >
                <header className="bubble__meta">
                  <span>{message.role === 'user' ? 'Você' : 'A.K.I.R.A.'}</span>
                  {message.streaming && message.stage ? (
                    <span className="bubble__stage">estágio: {message.stage}</span>
                  ) : null}
                  {message.usedMock ? (
                    <span className="bubble__mock">API offline, usando mocks</span>
                  ) : null}
                </header>
                <div className="bubble__body">
                  {message.content || (message.streaming ? '…' : '')}
                </div>
                {message.sources && message.sources.length > 0 ? (
                  <ul className="source-list">
                    {message.sources.map((source) => (
                      <li key={source.chunk_id}>
                        <strong>{source.title}</strong>
                        <span>{source.excerpt}</span>
                        {source.score != null ? (
                          <em>score {source.score.toFixed(2)}</em>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </article>
            ))
          )}
        </div>

        <form
          className="composer"
          onSubmit={(event) => {
            event.preventDefault()
            void send()
          }}
        >
          <textarea
            value={draft}
            rows={3}
            placeholder="Escreva uma pergunta…"
            disabled={streaming}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                void send()
              }
            }}
          />
          <button type="submit" disabled={streaming || !draft.trim()}>
            {streaming ? 'Respondendo…' : 'Enviar'}
          </button>
        </form>
      </section>

      <aside className="chat-graph">
        <header className="pane-header">
          <h2>Contexto do grafo</h2>
          {apiStatus().usingMocks ? (
            <span className="muted">mocks</span>
          ) : null}
        </header>
        <div className="graph-canvas">
          <GraphScene
            variant="chat"
            data={lastGraph ?? { nodes: [], links: [] }}
            highlightIds={highlightIds}
          />
        </div>
      </aside>
    </div>
  )
}
