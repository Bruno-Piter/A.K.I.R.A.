export type HealthResponse = {
  status: 'healthy'
  version: string
  llm_provider: string
  embeddings_provider: string
  neo4j_uri: string
}

export type SseEventType = 'stage' | 'token' | 'sources' | 'graph_context' | 'done'

export type SseEvent = {
  type: SseEventType
  content: unknown
}

export type ChatStreamRequest = {
  message: string
  thread_id?: string | null
  document_ids: string[]
}

export type ChatSource = {
  chunk_id: string
  document_id: string
  title: string
  excerpt: string
  score?: number | null
}

export type GraphNode = {
  id: string
  label: string
  type: string
  val: number
  color?: string | null
}

export type GraphLink = {
  source: string
  target: string
  type: string
  strength: number
}

export type GraphPayload = {
  nodes: GraphNode[]
  links: GraphLink[]
}

export type GraphOverviewResponse = GraphPayload & {
  document_count: number
  entity_count: number
  chunk_count: number
}

export type GraphNeighborhoodQuery = {
  id: string
  hops: number
}

export type DocumentSummary = {
  id: string
  filename: string
  status: string
  created_at?: string | null
  hashtags: string[]
}

export type DocumentListResponse = {
  documents: DocumentSummary[]
}

export type DocumentUploadResponse = {
  job_id: string
  document_id: string
  filename: string
  status: string
}

export type ApiStatus = {
  online: boolean
  usingMocks: boolean
  message: string
  health: HealthResponse | null
  lastError: string | null
}

export type ChatStreamCallbacks = {
  onStage?: (stage: string) => void
  onToken?: (token: string) => void
  onSources?: (sources: ChatSource[]) => void
  onGraphContext?: (graph: GraphPayload) => void
  onDone?: (content: unknown) => void
  onError?: (error: Error) => void
}

export const SSE_EVENT_TYPES: readonly SseEventType[] = [
  'stage',
  'token',
  'sources',
  'graph_context',
  'done',
]

export function isSseEventType(value: string): value is SseEventType {
  return (SSE_EVENT_TYPES as readonly string[]).includes(value)
}