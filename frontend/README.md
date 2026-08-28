# A.K.I.R.A. Console (frontend)

Vite + React + TypeScript UI for the A.K.I.R.A. console.
The browser talks only to FastAPI over HTTP/SSE. Never Neo4j. Never MCP.

## Run

From the frontend folder: npm run dev
Dev server: http://localhost:5173
vite.config.ts proxies /api to http://localhost:8000
Optional env VITE_API_URL if not using the proxy (leave unset for relative URLs).
Build: npm run build

## Pages

Tab state lives in src/App.tsx (no extra router).
- Chat: src/pages/Chat.tsx  POST /api/chat/stream (SSE)
- Grafo: src/pages/GraphExplorer.tsx  GET /api/graph and GET /api/graph/neighborhood
- Ingestao: src/pages/Ingest.tsx  GET/POST /api/documents (multipart field file)
Health: GET /api/health every 10s (src/components/HealthStatus.tsx)
Radial canvas: src/components/graph/RadialGraph.tsx (dagMode radialout)

## MOCK MODE

If a request 404s or the network fails, the client falls back to src/api/mocks.ts
and the UI shows: API offline, usando mocks.
- Health pill: offline / mocks (version 0.1.0, llm openai).
- Chat: fake SSE stream (retrieve, PT-BR tokens, sources, graph_context, done).
- Grafo: radial tree of about 14 nodes rooted at a Document.
- Ingestao: three mock documents. Upload is NOT sent; a queued mock row is added.
When FastAPI is up, the same UI uses live endpoints without code changes.

## API contracts

Types: src/api/types.ts   Client: src/api/client.ts
SSE parser accepts event/data pairs or a single data JSON {type, content}.
