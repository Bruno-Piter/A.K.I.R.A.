# Cookbook — backend Python

## Run

```powershell
cd C:\PROJETOS\akira\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
uvicorn app.main:app --reload --port 8000
```

## Add a route

1. Declare request/response types in `app/api/schemas.py`.
2. Implement the router under `app/api/routers/`.
3. Include the router in `app/main.py`.

Do not add an endpoint that is missing from `schemas.py`.

## Memory vs Skills vs Routines

- Cypher → `app/arms/memory/` only.
- External tools → FastMCP in `mcp_servers/`, registered in `skills.yaml`.
- Orchestration → `app/arms/routines/` StateGraph. Do not put `create_react_agent` at the app root.

## Neo4j

`docker compose up -d neo4j` from the repo root. Auth matches `.env.example`. No GDS plugin in compose.
