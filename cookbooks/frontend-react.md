# Cookbook — frontend React

## Run

```powershell
cd C:\PROJETOS\akira\frontend
npm install
npm run dev
```

Dev server: `http://localhost:5173`. Proxy or `VITE_API_URL=http://localhost:8000`.

## Pages (Agente 5)

When implementing product UI: `Chat`, `GraphExplorer`, `Ingest`. Graph component: `components/graph/RadialGraph.tsx` using `react-force-graph-2d`.

## API client

Keep fetch/SSE in `src/api/client.ts`. Types must match `backend/app/api/schemas.py` (`GraphPayload`, SSE event names).

## Do not

- Import Neo4j drivers.
- Call MCP servers from the browser.
- Introduce Next.js or a second bundler.
