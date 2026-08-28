import { useCallback, useEffect, useState } from 'react'
import { apiStatus, getGraph, getNeighborhood } from '../api/client.ts'
import type { GraphOverviewResponse, GraphPayload } from '../api/types.ts'
import RadialGraph from '../components/graph/RadialGraph.tsx'

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
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadOverview = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getGraph()
      setOverview(data)
      setCanvas({ nodes: data.nodes, links: data.links })
      setFocused(null)
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
    setLoading(true)
    setError(null)
    try {
      const neighborhood = await getNeighborhood(id, 2)
      setCanvas(neighborhood)
      setFocused(id)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  const usingMocks = apiStatus().usingMocks

  return (
    <div className="page page--graph">
      <header className="graph-toolbar">
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
        <div className="graph-toolbar__actions">
          {focused ? <span className="muted">foco: {focused} (2 hops)</span> : null}
          {usingMocks ? <span className="muted">API offline, usando mocks</span> : null}
          {loading ? <span className="muted">carregando…</span> : null}
          <button type="button" onClick={() => void loadOverview()}>
            Visão geral
          </button>
        </div>
      </header>
      {error ? <p className="banner banner--warn">{error}</p> : null}
      <div className="graph-canvas">
        <RadialGraph
          data={canvas}
          highlightIds={focused ? [focused, ...highlightIds] : highlightIds}
          onNodeClick={(id) => {
            void onNodeClick(id)
          }}
        />
      </div>
    </div>
  )
}