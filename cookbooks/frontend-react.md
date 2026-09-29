# Cookbook - frontend React

## Run

```powershell
cd C:\PROJETOS\akira\frontend
npm install
npm run dev
```

Dev server: `http://localhost:5173`. Proxy or `VITE_API_URL=http://localhost:8000`.

## Pages (Agente 5)

When implementing product UI: `Chat`, `GraphExplorer`, `Ingest`. Graph component: `components/graph/GraphScene.tsx` using `react-force-graph-3d` (WebGL, free 3D force, UnrealBloomPass, `three-spritetext` labels). `RadialGraph.tsx` re-exports `GraphScene` so older imports keep working.

Explorer is a full-bleed canvas with an overlay HUD (counts, legend, orbit tip, Visão geral). Chat aside uses `variant="chat"` (softer bloom, no auto-rotate, `showNavInfo={false}`). Mock mode still comes from `src/api/mocks.ts` when FastAPI is offline.

## API client

Keep fetch/SSE in `src/api/client.ts`. Types must match `backend/app/api/schemas.py` (`GraphPayload`, SSE event names).

## Do not

- Import Neo4j drivers.
- Call MCP servers from the browser.
- Introduce Next.js or a second bundler.

