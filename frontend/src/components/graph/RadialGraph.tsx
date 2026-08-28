import { useEffect, useMemo, useRef, useState } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import type { ForceGraphMethods, NodeObject } from 'react-force-graph-2d'
import type { GraphLink, GraphNode, GraphPayload } from '../../api/types.ts'

type RadialGraphProps = {
  data: GraphPayload
  highlightIds?: string[]
  onNodeClick?: (id: string) => void
  height?: number
}

type FgNode = GraphNode & NodeObject<GraphNode>
type FgLink = GraphLink

const TYPE_COLORS: Record<string, string> = {
  document: '#c084fc',
  entity: '#22d3ee',
  chunk: '#fbbf24',
}

function colorFor(node: GraphNode): string {
  return node.color || TYPE_COLORS[node.type] || '#9ca3af'
}

export default function RadialGraph({
  data,
  highlightIds = [],
  onNodeClick,
  height,
}: RadialGraphProps) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const fgRef = useRef<ForceGraphMethods<FgNode, FgLink> | undefined>(undefined)
  const [size, setSize] = useState({ width: 640, height: height ?? 480 })

  const highlighted = useMemo(() => new Set(highlightIds), [highlightIds])

  const graphData = useMemo(
    () => ({
      nodes: data.nodes.map((node) => ({ ...node })),
      links: data.links.map((item) => ({ ...item })),
    }),
    [data],
  )

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return

    const apply = () => {
      const rect = el.getBoundingClientRect()
      setSize({
        width: Math.max(320, Math.floor(rect.width)),
        height: Math.max(height ?? 480, Math.floor(rect.height) || (height ?? 480)),
      })
    }

    apply()
    const observer = new ResizeObserver(apply)
    observer.observe(el)
    return () => observer.disconnect()
  }, [height])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      fgRef.current?.zoomToFit(400, 48)
    }, 350)
    return () => window.clearTimeout(timer)
  }, [graphData, size.width, size.height])

  if (!data.nodes.length) {
    return (
      <div className="graph-empty" style={{ minHeight: height ?? 480 }}>
        <p>Nenhum nó no grafo. Faça upload ou use o chat.</p>
      </div>
    )
  }

  return (
    <div ref={wrapRef} className="radial-graph" style={{ minHeight: height ?? 480, height: '100%' }}>
      <ForceGraph2D<FgNode, FgLink>
        ref={fgRef}
        width={size.width}
        height={size.height}
        graphData={graphData}
        dagMode="radialout"
        dagLevelDistance={70}
        backgroundColor="rgba(0,0,0,0)"
        nodeId="id"
        nodeVal="val"
        nodeLabel="label"
        nodeRelSize={4}
        cooldownTicks={80}
        linkColor={() => 'rgba(192, 132, 252, 0.28)'}
        linkWidth={(item) => Math.max(0.6, item.strength ?? 1)}
        linkDirectionalArrowLength={3.5}
        linkDirectionalArrowRelPos={1}
        onDagError={() => undefined}
        onNodeClick={(node) => {
          if (node.id != null) onNodeClick?.(String(node.id))
        }}
        nodeCanvasObject={(node, ctx, globalScale) => {
          const x = node.x ?? 0
          const y = node.y ?? 0
          const isHit = highlighted.has(String(node.id))
          const radius = Math.max(4, (node.val ?? 1) * (isHit ? 2.4 : 1.6))
          ctx.beginPath()
          ctx.arc(x, y, radius, 0, Math.PI * 2)
          ctx.fillStyle = colorFor(node)
          ctx.fill()
          if (isHit) {
            ctx.strokeStyle = '#f5d0fe'
            ctx.lineWidth = 2.4
            ctx.stroke()
            ctx.beginPath()
            ctx.arc(x, y, radius + 4, 0, Math.PI * 2)
            ctx.strokeStyle = 'rgba(192, 132, 252, 0.7)'
            ctx.lineWidth = 1.5
            ctx.stroke()
          }
          const label = node.label || String(node.id ?? '')
          const fontSize = Math.max(10, 12 / globalScale)
          ctx.font = `${fontSize}px system-ui, sans-serif`
          ctx.textAlign = 'center'
          ctx.textBaseline = 'top'
          ctx.fillStyle = '#e5e7eb'
          ctx.fillText(label, x, y + radius + 3)
        }}
        nodePointerAreaPaint={(node, color, ctx) => {
          const x = node.x ?? 0
          const y = node.y ?? 0
          const isHit = highlighted.has(String(node.id))
          const radius = Math.max(6, (node.val ?? 1) * (isHit ? 2.8 : 2) + 4)
          ctx.beginPath()
          ctx.arc(x, y, radius, 0, Math.PI * 2)
          ctx.fillStyle = color
          ctx.fill()
        }}
      />
    </div>
  )
}