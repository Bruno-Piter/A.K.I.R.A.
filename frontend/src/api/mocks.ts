import type {
  ChatSource,
  ChatStreamCallbacks,
  DocumentListResponse,
  DocumentSummary,
  DocumentUploadResponse,
  GraphLink,
  GraphNode,
  GraphOverviewResponse,
  GraphPayload,
  HealthResponse,
  SseEvent,
} from './types.ts'

export const MOCK_HEALTH: HealthResponse = {
  status: 'healthy',
  version: '0.1.0',
  llm_provider: 'openai',
  embeddings_provider: 'openai',
  neo4j_uri: 'bolt://localhost:7687',
}

const DOC_COLOR = '#c084fc'
const ENTITY_COLOR = '#22d3ee'
const CHUNK_COLOR = '#fbbf24'

export const MOCK_NODES: GraphNode[] = [
  {
    id: 'doc-akira',
    label: 'Arquitetura A.K.I.R.A.',
    type: 'document',
    val: 8,
    color: DOC_COLOR,
  },
  { id: 'ent-rag', label: 'RAG', type: 'entity', val: 5, color: ENTITY_COLOR },
  { id: 'ent-neo4j', label: 'Neo4j', type: 'entity', val: 5, color: ENTITY_COLOR },
  { id: 'ent-fastapi', label: 'FastAPI', type: 'entity', val: 4, color: ENTITY_COLOR },
  { id: 'ent-sse', label: 'SSE', type: 'entity', val: 4, color: ENTITY_COLOR },
  {
    id: 'ent-embeddings',
    label: 'Embeddings',
    type: 'entity',
    val: 4,
    color: ENTITY_COLOR,
  },
  {
    id: 'ent-langgraph',
    label: 'LangGraph',
    type: 'entity',
    val: 3,
    color: ENTITY_COLOR,
  },
  {
    id: 'chunk-intro',
    label: 'chunk: introdução',
    type: 'chunk',
    val: 2,
    color: CHUNK_COLOR,
  },
  {
    id: 'chunk-retrieve',
    label: 'chunk: recuperação',
    type: 'chunk',
    val: 2,
    color: CHUNK_COLOR,
  },
  {
    id: 'chunk-graph',
    label: 'chunk: grafo',
    type: 'chunk',
    val: 2,
    color: CHUNK_COLOR,
  },
  {
    id: 'chunk-api',
    label: 'chunk: API HTTP',
    type: 'chunk',
    val: 2,
    color: CHUNK_COLOR,
  },
  {
    id: 'chunk-chat',
    label: 'chunk: chat SSE',
    type: 'chunk',
    val: 2,
    color: CHUNK_COLOR,
  },
  {
    id: 'chunk-ingest',
    label: 'chunk: ingestão',
    type: 'chunk',
    val: 2,
    color: CHUNK_COLOR,
  },
  {
    id: 'chunk-arch',
    label: 'chunk: camadas',
    type: 'chunk',
    val: 2,
    color: CHUNK_COLOR,
  },
]

function link(source: string, target: string, type = 'RELATED_TO', strength = 1): GraphLink {
  return { source, target, type, strength }
}

export const MOCK_LINKS: GraphLink[] = [
  link('doc-akira', 'ent-rag', 'MENTIONS', 1.2),
  link('doc-akira', 'ent-neo4j', 'MENTIONS', 1.2),
  link('doc-akira', 'ent-fastapi', 'MENTIONS', 1),
  link('doc-akira', 'ent-sse', 'MENTIONS', 1),
  link('doc-akira', 'ent-embeddings', 'MENTIONS', 1),
  link('doc-akira', 'chunk-intro', 'HAS_CHUNK', 0.8),
  link('doc-akira', 'chunk-arch', 'HAS_CHUNK', 0.8),
  link('ent-rag', 'ent-langgraph', 'RELATED_TO', 0.9),
  link('ent-rag', 'chunk-retrieve', 'APPEARS_IN', 1),
  link('ent-embeddings', 'chunk-retrieve', 'APPEARS_IN', 0.7),
  link('ent-embeddings', 'chunk-ingest', 'APPEARS_IN', 1),
  link('ent-neo4j', 'chunk-graph', 'APPEARS_IN', 1.1),
  link('ent-fastapi', 'chunk-api', 'APPEARS_IN', 1),
  link('ent-sse', 'chunk-chat', 'APPEARS_IN', 1.1),
  link('ent-langgraph', 'chunk-chat', 'APPEARS_IN', 0.6),
]

export const MOCK_GRAPH: GraphPayload = {
  nodes: MOCK_NODES,
  links: MOCK_LINKS,
}

export const MOCK_GRAPH_OVERVIEW: GraphOverviewResponse = {
  ...MOCK_GRAPH,
  document_count: 3,
  entity_count: 6,
  chunk_count: 7,
}

export const MOCK_DOCUMENTS: DocumentSummary[] = [
  {
    id: 'doc-akira',
    filename: 'arquitetura-akira.md',
    status: 'indexed',
    created_at: '2026-08-20T14:10:00-03:00',
    hashtags: ['#arquitetura', '#rag', '#grafo'],
  },
  {
    id: 'doc-reuniao',
    filename: 'notas-reuniao-ingestao.txt',
    status: 'indexed',
    created_at: '2026-08-22T09:45:00-03:00',
    hashtags: ['#ingestao', '#documentos'],
  },
  {
    id: 'doc-grafo',
    filename: 'especificacao-grafo.pdf',
    status: 'processing',
    created_at: '2026-08-27T18:02:00-03:00',
    hashtags: ['#grafo', '#neo4j'],
  },
]

export const MOCK_DOCUMENT_LIST: DocumentListResponse = {
  documents: MOCK_DOCUMENTS,
}

export const MOCK_SOURCES: ChatSource[] = [
  {
    chunk_id: 'chunk-retrieve',
    document_id: 'doc-akira',
    title: 'Arquitetura A.K.I.R.A. — recuperação',
    excerpt:
      'O pipeline RAG recupera chunks por similaridade de embeddings e reordena com o contexto do grafo.',
    score: 0.91,
  },
  {
    chunk_id: 'chunk-graph',
    document_id: 'doc-akira',
    title: 'Arquitetura A.K.I.R.A. — grafo',
    excerpt:
      'Entidades e documentos formam um grafo radial no Neo4j; o chat destaca a vizinhança relevante.',
    score: 0.84,
  },
  {
    chunk_id: 'chunk-chat',
    document_id: 'doc-akira',
    title: 'Arquitetura A.K.I.R.A. — chat SSE',
    excerpt:
      'A resposta é transmitida em Server-Sent Events: stage, token, sources, graph_context e done.',
    score: 0.78,
  },
]

const CONTEXT_IDS = new Set([
  'doc-akira',
  'ent-rag',
  'ent-neo4j',
  'ent-sse',
  'chunk-retrieve',
  'chunk-graph',
  'chunk-chat',
])

export const MOCK_GRAPH_CONTEXT: GraphPayload = {
  nodes: MOCK_NODES.filter((node) => CONTEXT_IDS.has(node.id)),
  links: MOCK_LINKS.filter(
    (item) => CONTEXT_IDS.has(item.source) && CONTEXT_IDS.has(item.target),
  ),
}

const MOCK_ANSWER =
  'A A.K.I.R.A. combina recuperação de documentos (RAG) com um grafo de conhecimento no Neo4j. O chat consulta chunks relevantes via FastAPI e destaca entidades relacionadas no canvas radial, transmitindo a resposta em SSE.'

export const MOCK_THREAD_ID = 'thread-mock-001'

export function mockNeighborhood(id: string, hops: number): GraphPayload {
  const clampedHops = Math.min(6, Math.max(1, hops))
  const adjacency = new Map<string, Set<string>>()
  for (const node of MOCK_NODES) {
    adjacency.set(node.id, new Set())
  }
  for (const item of MOCK_LINKS) {
    adjacency.get(item.source)?.add(item.target)
    adjacency.get(item.target)?.add(item.source)
  }

  const root = MOCK_NODES.some((node) => node.id === id) ? id : MOCK_NODES[0].id
  const seen = new Set<string>([root])
  let frontier = [root]
  for (let depth = 0; depth < clampedHops; depth += 1) {
    const next: string[] = []
    for (const nodeId of frontier) {
      for (const neighbor of adjacency.get(nodeId) ?? []) {
        if (!seen.has(neighbor)) {
          seen.add(neighbor)
          next.push(neighbor)
        }
      }
    }
    frontier = next
  }

  return {
    nodes: MOCK_NODES.filter((node) => seen.has(node.id)),
    links: MOCK_LINKS.filter((item) => seen.has(item.source) && seen.has(item.target)),
  }
}

export function mockUpload(file: File): DocumentUploadResponse {
  return {
    job_id: `mock-job-${Date.now()}`,
    document_id: `mock-doc-${Date.now()}`,
    filename: file.name,
    status: 'queued',
  }
}

export function mockQueuedDocument(file: File, documentId: string): DocumentSummary {
  return {
    id: documentId,
    filename: file.name,
    status: 'queued (mock)',
    created_at: new Date().toISOString(),
    hashtags: ['#mock'],
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

export const MOCK_SSE_EVENTS: SseEvent[] = [
  { type: 'stage', content: 'retrieve' },
  ...MOCK_ANSWER.split(/(\s+)/)
    .filter(Boolean)
    .map((token) => ({ type: 'token' as const, content: token })),
  { type: 'sources', content: MOCK_SOURCES },
  { type: 'graph_context', content: MOCK_GRAPH_CONTEXT },
  { type: 'done', content: { thread_id: MOCK_THREAD_ID } },
]

export async function playMockChatStream(callbacks: ChatStreamCallbacks): Promise<void> {
  try {
    for (const event of MOCK_SSE_EVENTS) {
      switch (event.type) {
        case 'stage':
          callbacks.onStage?.(String(event.content))
          await sleep(220)
          break
        case 'token':
          callbacks.onToken?.(String(event.content))
          await sleep(28)
          break
        case 'sources':
          callbacks.onSources?.(event.content as ChatSource[])
          await sleep(80)
          break
        case 'graph_context':
          callbacks.onGraphContext?.(event.content as GraphPayload)
          await sleep(60)
          break
        case 'done':
          callbacks.onDone?.(event.content)
          break
      }
    }
  } catch (error) {
    callbacks.onError?.(error instanceof Error ? error : new Error(String(error)))
  }
}