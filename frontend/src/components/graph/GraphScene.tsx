import { Component, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { ErrorInfo, ReactNode } from 'react'
import ForceGraph3D from 'react-force-graph-3d'
import type { ForceGraphMethods } from 'react-force-graph-3d'
import * as THREE from 'three'
import SpriteText from 'three-spritetext'
import type { GraphLink, GraphNode, GraphPayload } from '../../api/types.ts'

export type GraphSceneProps = {
  data: GraphPayload
  highlightIds?: string[]
  onNodeClick?: (id: string) => void
  height?: number
  variant?: 'explorer' | 'chat'
  selectedId?: string | null
}

type FgNode = GraphNode & {
  id: string
  x?: number
  y?: number
  z?: number
  __threeObj?: unknown
}

type FgLink = GraphLink & {
  source: string | FgNode
  target: string | FgNode
}

type OrbitControlsLike = {
  autoRotate: boolean
  autoRotateSpeed: number
}

const TYPE_COLORS: Record<string, string> = {
  document: '#c084fc',
  entity: '#22d3ee',
  chunk: '#fbbf24',
}

const ACCENT = '#c084fc'
const FALLBACK_COLOR = '#9ca3af'

const SPHERE_GEOMETRY = new THREE.SphereGeometry(1, 16, 16)
SPHERE_GEOMETRY.dispose = () => {}

function makeMaterial(color: string, intensity: number): THREE.MeshLambertMaterial {
  const mat = new THREE.MeshLambertMaterial({
    color,
    emissive: new THREE.Color(color),
    emissiveIntensity: intensity,
  })
  mat.dispose = () => {}
  return mat
}

const MATERIALS: Record<string, THREE.MeshLambertMaterial> = {
  document: makeMaterial(TYPE_COLORS.document, 0.85),
  entity: makeMaterial(TYPE_COLORS.entity, 0.85),
  chunk: makeMaterial(TYPE_COLORS.chunk, 0.85),
  fallback: makeMaterial(FALLBACK_COLOR, 0.7),
}

const HOT_MATERIALS: Record<string, THREE.MeshLambertMaterial> = {
  document: makeMaterial(TYPE_COLORS.document, 1.2),
  entity: makeMaterial(TYPE_COLORS.entity, 1.2),
  chunk: makeMaterial(TYPE_COLORS.chunk, 1.2),
  fallback: makeMaterial(FALLBACK_COLOR, 1.1),
}

function detectWebGL(): boolean {
  try {
    const canvas = document.createElement('canvas')
    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl')
    return gl != null
  } catch {
    return false
  }
}

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function typeKey(type: string | undefined): string {
  const key = (type || '').toLowerCase()
  if (key === 'document' || key === 'entity' || key === 'chunk') return key
  return 'fallback'
}

function materialFor(type: string | undefined, hot: boolean): THREE.MeshLambertMaterial {
  const key = typeKey(type)
  return hot ? HOT_MATERIALS[key] : MATERIALS[key]
}

function linkStrength(link: FgLink): number {
  return typeof link.strength === 'number' && Number.isFinite(link.strength) ? link.strength : 1
}

function nodeIdOf(node: unknown): string | null {
  try {
    if (node == null || typeof node !== 'object') return null
    const id = (node as { id?: unknown }).id
    if (id == null) return null
    return String(id)
  } catch {
    return null
  }
}

function hasLayout(node: unknown): boolean {
  try {
    if (node == null || typeof node !== 'object') return false
    const n = node as { x?: unknown; y?: unknown; z?: unknown }
    return Number.isFinite(n.x) && Number.isFinite(n.y)
  } catch {
    return false
  }
}

class GraphErrorBoundary extends Component<
  { children: ReactNode; onReset?: () => void },
  { hasError: boolean }
> {
  state = { hasError: false }

  static getDerivedStateFromError(): { hasError: boolean } {
    return { hasError: true }
  }

  componentDidCatch(_error: Error, _info: ErrorInfo): void {
    // swallow 3d-force-graph pointer crashes
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="graph-empty">
          <p>Falha ao desenhar o grafo 3D. Tente de novo.</p>
          <button
            type="button"
            onClick={() => {
              this.setState({ hasError: false })
              this.props.onReset?.()
            }}
          >
            Recarregar cena
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

export default function GraphScene({
  data,
  highlightIds = [],
  onNodeClick,
  height,
  variant = 'explorer',
  selectedId = null,
}: GraphSceneProps) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const fgRef = useRef<ForceGraphMethods<FgNode, FgLink> | undefined>(undefined)
  const bloomAddedRef = useRef(false)
  const hoverIdRef = useRef<string | null>(null)
  const selectedIdRef = useRef<string | null>(selectedId)
  const highlightRef = useRef<Set<string>>(new Set(highlightIds))
  const variantRef = useRef(variant)
  const onNodeClickRef = useRef(onNodeClick)
  const clickLockRef = useRef(false)
  const [webglOk] = useState(() => detectWebGL())
  const [sceneNonce, setSceneNonce] = useState(0)
  const [size, setSize] = useState({ width: 0, height: 0 })

  const highlighted = useMemo(() => new Set(highlightIds), [highlightIds])

  selectedIdRef.current = selectedId
  highlightRef.current = highlighted
  variantRef.current = variant
  onNodeClickRef.current = onNodeClick

  useEffect(() => {
    const onError = (event: ErrorEvent) => {
      const msg = String(event.message || '')
      const stack = event.error instanceof Error ? event.error.stack || '' : ''
      const isX =
        msg.includes("reading 'x'") ||
        msg.includes('reading "x"') ||
        msg.includes("Cannot read properties of undefined")
      const fromControls =
        stack.includes('onPointerUp') ||
        stack.includes('OrbitControls') ||
        stack.includes('DragControls') ||
        stack.includes('3d-force-graph')
      if (isX && (fromControls || stack === '')) {
        event.preventDefault()
        event.stopImmediatePropagation()
      }
    }
    window.addEventListener('error', onError, true)
    return () => window.removeEventListener('error', onError, true)
  }, [])

  useEffect(() => {
    if (!webglOk || data.nodes.length === 0 || size.width < 2) return
    let tries = 0
    let raf = 0
    const wrap = () => {
      const fg = fgRef.current
      const controls = fg?.controls?.() as
        | {
            _onPointerUp?: (event: PointerEvent) => void
            __akiraPointerUpGuarded?: boolean
          }
        | undefined
      if (!controls?._onPointerUp) {
        tries += 1
        if (tries < 60) raf = requestAnimationFrame(wrap)
        return
      }
      if (controls.__akiraPointerUpGuarded) return
      const orig = controls._onPointerUp.bind(controls)
      controls._onPointerUp = (event: PointerEvent) => {
        try {
          orig(event)
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err)
          if (msg.includes("reading 'x'") || msg.includes('of undefined')) return
          throw err
        }
      }
      controls.__akiraPointerUpGuarded = true
    }
    raf = requestAnimationFrame(wrap)
    return () => {
      if (raf) cancelAnimationFrame(raf)
    }
  }, [webglOk, data.nodes.length, size.width, size.height, sceneNonce])

  const graphData = useMemo(
    () => ({
      nodes: data.nodes.map((node) => ({ ...node })),
      links: data.links.map((item) => ({ ...item })),
    }),
    [data],
  )

  useLayoutEffect(() => {
    const el = wrapRef.current
    if (!el) return

    const apply = () => {
      const parent = el.parentElement
      const rect = el.getBoundingClientRect()
      const parentRect = parent?.getBoundingClientRect()
      const width = Math.max(
        1,
        Math.round(rect.width || parentRect?.width || el.clientWidth || 0),
      )
      const heightPx = Math.max(
        1,
        Math.round(rect.height || parentRect?.height || el.clientHeight || height || 0),
      )
      setSize((prev) =>
        prev.width === width && prev.height === heightPx ? prev : { width, height: heightPx },
      )
      const fg = fgRef.current as
        | (ForceGraphMethods<FgNode, FgLink> & {
            width?: (w: number) => void
            height?: (h: number) => void
          })
        | undefined
      if (fg && width > 1 && heightPx > 1) {
        try {
          fg.width?.(width)
          fg.height?.(heightPx)
        } catch {
          // renderer may not be ready
        }
      }
    }

    apply()
    const observer = new ResizeObserver(() => apply())
    observer.observe(el)
    if (el.parentElement) observer.observe(el.parentElement)
    window.addEventListener('resize', apply)
    return () => {
      observer.disconnect()
      window.removeEventListener('resize', apply)
    }
  }, [height, webglOk, data.nodes.length, sceneNonce])

  const nodeThreeObject = useCallback((node: FgNode) => {
    try {
      const id = nodeIdOf(node) ?? 'node'
      const selected = selectedIdRef.current === id
      const highlightedNode = highlightRef.current.has(id)
      const hovered = hoverIdRef.current === id
      const hot = selected || highlightedNode || hovered
      const radius = Math.max(1.4, (node.val ?? 1) * (hot ? 2.4 : 1.5))

      const group = new THREE.Group()
      const mesh = new THREE.Mesh(SPHERE_GEOMETRY, materialFor(node.type, hot))
      mesh.scale.setScalar(radius)
      group.add(mesh)

      const overview = variantRef.current === 'explorer' && !selectedIdRef.current
      const showLabel =
        hovered ||
        selected ||
        (variantRef.current === 'chat' && highlightedNode) ||
        (overview && ((node.val ?? 0) >= 2 || typeKey(node.type) === 'document')) ||
        (variantRef.current === 'explorer' && highlightedNode && !overview)

      if (showLabel) {
        const sprite = new SpriteText(node.label || id)
        sprite.color = '#e5e7eb'
        sprite.textHeight = Math.max(2.4, radius * 0.55)
        sprite.fontFace = 'system-ui, Segoe UI, sans-serif'
        sprite.backgroundColor = 'rgba(7,8,13,0.55)'
        sprite.padding = 1.2
        sprite.borderRadius = 1.5
        sprite.position.y = radius + 2.6
        group.add(sprite)
      }

      return group
    } catch {
      const fallback = new THREE.Mesh(SPHERE_GEOMETRY, MATERIALS.fallback)
      fallback.scale.setScalar(1.4)
      return fallback
    }
  }, [])

  useEffect(() => {
    try {
      fgRef.current?.refresh()
    } catch {
      // ignore refresh while the simulation is swapping nodes
    }
  }, [selectedId, highlighted, variant])

  useEffect(() => {
    if (!webglOk || data.nodes.length === 0 || size.width < 2) {
      bloomAddedRef.current = false
      return
    }

    let cancelled = false
    let raf = 0
    let attempts = 0

    const setup = () => {
      if (cancelled) return
      const fg = fgRef.current
      if (!fg) {
        attempts += 1
        if (attempts < 90) raf = requestAnimationFrame(setup)
        return
      }

      try {
        const sized = fg as ForceGraphMethods<FgNode, FgLink> & {
          width?: (w: number) => void
          height?: (h: number) => void
        }
        sized.width?.(size.width)
        sized.height?.(size.height)
      } catch {
        // ignore
      }

      try {
        const controls = fg.controls() as OrbitControlsLike
        const reduced = prefersReducedMotion()
        if (reduced || variant === 'chat') {
          controls.autoRotate = false
        } else {
          controls.autoRotate = true
          controls.autoRotateSpeed = 0.4
        }
      } catch {
        // orbit controls may not be ready
      }

      if (bloomAddedRef.current) return

      void (async () => {
        try {
          let BloomPass: typeof import('three/examples/jsm/postprocessing/UnrealBloomPass.js').UnrealBloomPass
          try {
            const mod = await import('three/examples/jsm/postprocessing/UnrealBloomPass.js')
            BloomPass = mod.UnrealBloomPass
          } catch {
            const mod = await import('three/addons/postprocessing/UnrealBloomPass.js')
            BloomPass = mod.UnrealBloomPass
          }
          if (cancelled || bloomAddedRef.current) return
          const composer = fg.postProcessingComposer() as { addPass: (pass: unknown) => void }
          const pass = new BloomPass(
            new THREE.Vector2(size.width, size.height),
            variant === 'chat' ? 0.28 : 0.6,
            0.5,
            0.2,
          )
          composer.addPass(pass)
          bloomAddedRef.current = true
        } catch {
          // bloom is optional
        }
      })()
    }

    raf = requestAnimationFrame(setup)
    return () => {
      cancelled = true
      if (raf) cancelAnimationFrame(raf)
    }
  }, [webglOk, data.nodes.length, variant, size.width, size.height])

  function handleNodeClick(node: FgNode | null): void {
    if (clickLockRef.current) return
    try {
      const id = nodeIdOf(node)
      if (!id) return
      clickLockRef.current = true
      window.setTimeout(() => {
        clickLockRef.current = false
      }, 350)
      onNodeClickRef.current?.(id)
    } catch {
      clickLockRef.current = false
    }
  }

  if (!data.nodes.length) {
    return (
      <div className="graph-empty" style={height ? { minHeight: height } : undefined}>
        <p>Nenhum nó no grafo. Faça upload ou use o chat.</p>
      </div>
    )
  }

  if (!webglOk) {
    return (
      <div className="graph-empty graph-fallback" style={height ? { minHeight: height } : undefined}>
        <p>WebGL indisponível neste navegador. O grafo 3D não pôde ser iniciado.</p>
        <ul className="graph-fallback__list">
          {data.nodes.map((node) => (
            <li key={node.id}>{node.label || node.id}</li>
          ))}
        </ul>
      </div>
    )
  }

  return (
    <div
      ref={wrapRef}
      className="graph-scene radial-graph"
      style={height ? { minHeight: height, height: '100%', width: '100%' } : { height: '100%', width: '100%' }}
    >
      {size.width < 2 || size.height < 2 ? null : (
        <GraphErrorBoundary onReset={() => setSceneNonce((n) => n + 1)}>
          <ForceGraph3D<FgNode, FgLink>
            key={sceneNonce}
            ref={fgRef}
            width={size.width}
            height={size.height}
            graphData={graphData}
            backgroundColor="#07080d"
            showNavInfo={false}
            controlType="orbit"
            enablePointerInteraction
            enableNodeDrag={false}
            nodeId="id"
            nodeVal="val"
            nodeLabel={(node) => {
              try {
                return node.label || String(node.id ?? '')
              } catch {
                return ''
              }
            }}
            nodeThreeObject={nodeThreeObject}
            nodeThreeObjectExtend={false}
            cooldownTicks={90}
            linkColor={() => ACCENT}
            linkOpacity={0.35}
            linkWidth={(link) => {
              try {
                return Math.max(0.4, linkStrength(link))
              } catch {
                return 0.4
              }
            }}
            linkDirectionalParticles={(link) => {
              try {
                const src = (link as FgLink).source
                const tgt = (link as FgLink).target
                if (typeof src === 'object' && !hasLayout(src)) return 0
                if (typeof tgt === 'object' && !hasLayout(tgt)) return 0
                return Math.max(1, Math.round(linkStrength(link) * 2))
              } catch {
                return 0
              }
            }}
            linkDirectionalParticleColor={() => ACCENT}
            linkDirectionalParticleWidth={1.2}
            onEngineStop={() => {
              try {
                fgRef.current?.zoomToFit(400, 40)
              } catch {
                // zoomToFit can throw if nodes have no coords yet
              }
            }}
            onNodeHover={(node) => {
              try {
                const id = nodeIdOf(node)
                if (hoverIdRef.current === id) return
                hoverIdRef.current = id
                fgRef.current?.refresh()
              } catch {
                // hover during graph swap
              }
            }}
            onNodeClick={(node) => handleNodeClick(node)}
            onBackgroundClick={() => {
              hoverIdRef.current = null
            }}
          />
        </GraphErrorBoundary>
      )}
    </div>
  )
}
