# A.K.I.R.A.

Agentic Knowledge Integration & Retrieval Architecture. Agentic OS no padrão ARMS (Apps, Routines, Memory, Skills).

Monorepo em `C:\PROJETOS\akira`. MVP: FastAPI + LangGraph + FastMCP + Neo4j 5 + React (Vite).

## Subir o ambiente (Step 1)

```powershell
docker compose up -d neo4j
cd backend; .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
cd frontend; npm run dev
```

Health: [http://localhost:8000/api/health](http://localhost:8000/api/health)  
Neo4j Browser: [http://localhost:7474](http://localhost:7474)

## Dono de pasta (agentes)

| Agente | Pastas |
|---|---|
| 1 Foundations | raiz, `backend/app/core/`, `backend/app/api/schemas.py`, scaffold `frontend/` |
| 2 Memory | `backend/app/arms/memory/`, `backend/tests/memory/` |
| 3 Skills | `backend/mcp_servers/`, `backend/app/arms/skills/` |
| 4 Routines | `backend/app/arms/routines/`, `backend/app/api/routers/` de negócio, `main.py` |
| 5 Console UI | `frontend/src/` |
| 6 Integrador | E2E, CORS, `.env`, README — não reescreve arquitetura |

## Contratos HTTP

Fonte da verdade: `backend/app/api/schemas.py`.
