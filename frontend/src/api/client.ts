import {
  MOCK_DOCUMENT_LIST,
  MOCK_GRAPH_OVERVIEW,
  MOCK_HEALTH,
  mockNeighborhood,
  mockQueuedDocument,
  mockUpload,
  playMockChatStream,
} from './mocks.ts'
import type {
  ApiStatus,
  ChatSource,
  ChatStreamCallbacks,
  ChatStreamRequest,
  DocumentListResponse,
  DocumentSummary,
  DocumentUploadResponse,
  GraphOverviewResponse,
  GraphPayload,
  HealthResponse,
  SseEvent,
  SseEventType,
} from './types.ts'
import { isSseEventType } from './types.ts'

const API_BASE = normalizeBase(import.meta.env.VITE_API_URL)

function normalizeBase(value: unknown): string {
  if (typeof value !== 'string') return ''
  return value.replace(/\/$/, '')
}

function apiUrl(path: string): string {
  return `${API_BASE}${path}`
}

let status: ApiStatus = {
  online: false,
  usingMocks: false,
  message: 'Verificando API…',
  health: null,
  lastError: null,
}

const listeners = new Set<(next: ApiStatus) => void>()

export function apiStatus(): ApiStatus {
  return status
}

export function subscribeApiStatus(listener: (next: ApiStatus) => void): () => void {
  listeners.add(listener)
  listener(status)
  return () => {
    listeners.delete(listener)
  }
}

function emitStatus(patch: Partial<ApiStatus>): void {
  status = { ...status, ...patch }
  for (const listener of listeners) listener(status)
}

function markOnline(health: HealthResponse): void {
  emitStatus({
    online: true,
    message: 'API online',
    health,
    lastError: null,
  })
}

function markMock(error: unknown, message = 'API offline, usando mocks'): void {
  const lastError = error instanceof Error ? error.message : String(error)
  emitStatus({
    usingMocks: true,
    message,
    lastError,
  })
}

function markHealthDown(error: unknown): void {
  const lastError = error instanceof Error ? error.message : String(error)
  emitStatus({
    online: false,
    usingMocks: true,
    message: 'API offline, usando mocks',
    lastError,
  })
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), init)
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} em ${path}`)
  }
  return (await response.json()) as T
}

export async function getHealth(): Promise<HealthResponse> {
  try {
    const data = await fetchJson<HealthResponse>('/api/health')
    markOnline(data)
    return data
  } catch (error) {
    markHealthDown(error)
    return MOCK_HEALTH
  }
}

export async function listDocuments(): Promise<DocumentListResponse> {
  try {
    const data = await fetchJson<DocumentListResponse>('/api/documents')
    emitStatus({ usingMocks: false, lastError: null })
    return data
  } catch (error) {
    markMock(error)
    return {
      documents: [...mockDocumentStore],
    }
  }
}

const mockDocumentStore: DocumentSummary[] = [...MOCK_DOCUMENT_LIST.documents]

export async function uploadDocument(file: File): Promise<DocumentUploadResponse> {
  try {
    const body = new FormData()
    body.append('file', file)
    const data = await fetchJson<DocumentUploadResponse>('/api/documents', {
      method: 'POST',
      body,
    })
    emitStatus({ usingMocks: false, lastError: null })
    return data
  } catch (error) {
    markMock(error, 'API offline — o arquivo não foi enviado (simulação mock)')
    const fake = mockUpload(file)
    mockDocumentStore.unshift(mockQueuedDocument(file, fake.document_id))
    return fake
  }
}

export async function getGraph(): Promise<GraphOverviewResponse> {
  try {
    const data = await fetchJson<GraphOverviewResponse>('/api/graph')
    emitStatus({ usingMocks: false, lastError: null })
    return data
  } catch (error) {
    markMock(error)
    return MOCK_GRAPH_OVERVIEW
  }
}

export async function getNeighborhood(id: string, hops: number): Promise<GraphPayload> {
  const params = new URLSearchParams({
    id,
    hops: String(hops),
  })
  try {
    const data = await fetchJson<GraphPayload>(`/api/graph/neighborhood?${params.toString()}`)
    emitStatus({ usingMocks: false, lastError: null })
    return data
  } catch (error) {
    markMock(error)
    return mockNeighborhood(id, hops)
  }
}

function parseJsonOrRaw(raw: string): unknown {
  const trimmed = raw.trim()
  if (!trimmed) return trimmed
  try {
    return JSON.parse(trimmed) as unknown
  } catch {
    return raw
  }
}

function asChatSources(value: unknown): ChatSource[] {
  return Array.isArray(value) ? (value as ChatSource[]) : []
}

function asGraphPayload(value: unknown): GraphPayload {
  if (!isRecord(value)) return { nodes: [], links: [] }
  const nodes = Array.isArray(value.nodes) ? (value.nodes as GraphPayload['nodes']) : []
  const links = Array.isArray(value.links) ? (value.links as GraphPayload['links']) : []
  return { nodes, links }
}

function dispatchEvent(type: SseEventType, content: unknown, callbacks: ChatStreamCallbacks): void {
  switch (type) {
    case 'stage':
      callbacks.onStage?.(typeof content === 'string' ? content : String(content ?? ''))
      break
    case 'token':
      callbacks.onToken?.(typeof content === 'string' ? content : String(content ?? ''))
      break
    case 'sources':
      callbacks.onSources?.(asChatSources(content))
      break
    case 'graph_context':
      callbacks.onGraphContext?.(asGraphPayload(content))
      break
    case 'done':
      callbacks.onDone?.(content)
      break
  }
}

function dispatchSseBlock(block: string, callbacks: ChatStreamCallbacks): void {
  const lines = block.split('\n')
  let eventName: string | undefined
  const dataLines: string[] = []
  for (const line of lines) {
    if (!line || line.startsWith(':')) continue
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart())
    }
  }
  if (dataLines.length === 0) return
  const parsed = parseJsonOrRaw(dataLines.join('\n'))

  if (isRecord(parsed) && typeof parsed.type === 'string' && isSseEventType(parsed.type)) {
    const event = parsed as SseEvent
    dispatchEvent(event.type, event.content, callbacks)
    return
  }

  if (eventName && isSseEventType(eventName)) {
    dispatchEvent(eventName, parsed, callbacks)
  }
}

async function readSseStream(
  body: ReadableStream<Uint8Array>,
  callbacks: ChatStreamCallbacks,
): Promise<void> {
  const reader = body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      buffer = buffer.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
      let sep = buffer.indexOf('\n\n')
      while (sep !== -1) {
        const raw = buffer.slice(0, sep)
        buffer = buffer.slice(sep + 2)
        dispatchSseBlock(raw, callbacks)
        sep = buffer.indexOf('\n\n')
      }
    }
    buffer += decoder.decode()
    if (buffer.trim()) dispatchSseBlock(buffer, callbacks)
  } finally {
    reader.releaseLock()
  }
}

export async function streamChat(
  req: ChatStreamRequest,
  callbacks: ChatStreamCallbacks,
): Promise<{ usedMock: boolean }> {
  try {
    const response = await fetch(apiUrl('/api/chat/stream'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify(req),
    })
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} em /api/chat/stream`)
    }
    if (!response.body) {
      throw new Error('Resposta SSE sem corpo')
    }
    await readSseStream(response.body, callbacks)
    emitStatus({ usingMocks: false, lastError: null })
    return { usedMock: false }
  } catch (error) {
    markMock(error)
    await playMockChatStream(callbacks)
    return { usedMock: true }
  }
}