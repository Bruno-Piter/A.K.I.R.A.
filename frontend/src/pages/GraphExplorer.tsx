import { useCallback, useEffect, useRef, useState } from 'react'
import { apiStatus, getGraph, getNeighborhood } from '../api/client.ts'
import type { GraphNode, GraphOverviewResponse, GraphPayload } from '../api/types.ts'
import GraphScene from '../components/graph/GraphScene.tsx'

type GraphExplorerProps = {
  highlightIds?: string[]
}

const EMPTY_OVERVIEW: GraphOverviewResponse = {
  nodes: [],
  links: [],
  document_count: 0,
  entity_count: 0,
  chunk_count: 0,
}

export default function GraphExplorer({ highlightIds = [] }: GraphExplorerProps) {
  const [overview, setOverview] = useState<GraphOverviewResponse>(EMPTY_OVERVIEW)
  const [canvas, setCanvas] = useState<GraphPayload>(EMPTY_OVERVIEW)
  const [focused, setFocused] = useState<string | null>(null)
  const [inspected, setInspected] = useState<GraphNode | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const clickLockRef = useRef(false)

  const loadOverview = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getGraph()
      setOverview(data)
      setCanvas({ nodes: data.nodes, links: data.links })
      setFocused(null)
      setInspected(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadOverview()
  }, [loadOverview])

  async function onNodeClick(id: string): Promise<void> {
    if (!id || clickLockRef.current) return
    clickLockRef.current = true
    const current = canvas.nodes.find((node) => node.id === id) ?? null
    setInspected(current)
    setLoading(true)
    setError(null)
    try {
      const neighborhood = await getNeighborhood(id, 2)
      setCanvas(neighborhood)
      setFocused(id)
      setInspected(neighborhood.nodes.find((node) => node.id === id) ?? current)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
      window.setTimeout(() => {
        clickLockRef.current = false
      }, 400)
    }
  }

  const usingMocks = apiStatus().usingMocks
  const inspectedNode =
    inspected ?? canvas.nodes.find((node) => node.id === focused) ?? null

  return (
    <div className="page page--graph">
      <div className="graph-canvas">
        <GraphScene
          variant="explorer"
          data={canvas}
          selectedId={focused}
          highlightIds={focused ? [focused, ...highlightIds] : highlightIds}
          onNodeClick={(id) => {
            void onNodeClick(id)
          }}
        />
        <div className="graph-hud">
          <div>
            <div className="graph-hud__bar">
              <div className="counts">
                <span>
                  <strong>{overview.document_count}</strong> documentos
                </span>
                <span>
                  <strong>{overview.entity_count}</strong> entidades
                </span>
                <span>
                  <strong>{overview.chunk_count}</strong> chunks
                </span>
              </div>
              <div className="graph-hud__status">
                {focused ? <span className="graph-focus-chip">foco: {focused}</span> : null}
                {usingMocks ? <span className="muted">API offline, usando mocks</span> : null}
                {loading ? <span className="muted">carregando…</span> : null}
                <button type="button" onClick={() => void loadOverview()}>
                  Visão geral
                </button>
              </div>
            </div>
            {error ? <p className="banner banner--warn graph-hud__banner">{error}</p> : null}
          </div>
          <div className="graph-hud__meta">
            <div className="graph-legend">
              <span className="legend-dot legend-dot--document">Documento</span>
              <span className="legend-dot legend-dot--entity">Entidade</span>
              <span className="legend-dot legend-dot--chunk">Chunk</span>
            </div>
            <p className="graph-orbit-tip">Arraste para orbitar · scroll para zoom</p>
          </div>
        </div>
        {inspectedNode ? (
          <aside className="graph-inspector">
            <h3>{inspectedNode.label}</h3>
            <dl>
              <dt>tipo</dt>
              <dd>{inspectedNode.type}</dd>
              <dt>id</dt>
              <dd>{inspectedNode.id}</dd>
            </dl>
          </aside>
        ) : null}
      </div>
    </div>
  )
}
