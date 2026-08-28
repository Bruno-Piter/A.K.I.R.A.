"""Graph neighborhood HTTP API. Calls memory.neighborhood directly (never MCP)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import GraphOverviewResponse, GraphPayload
from app.arms.memory import graph_overview, neighborhood

router = APIRouter()


@router.get("/graph", response_model=GraphOverviewResponse)
async def get_graph_overview() -> GraphOverviewResponse:
    try:
        payload = graph_overview()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        return GraphOverviewResponse.model_validate(payload)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc



@router.get("/graph/neighborhood", response_model=GraphPayload)
async def get_neighborhood(
    id: str = Query(..., min_length=1),
    hops: int = Query(2, ge=1, le=6),
) -> GraphPayload:
    try:
        payload = neighborhood(id, hops=hops)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not isinstance(payload, dict):
        try:
            payload = payload.model_dump()
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    nodes = payload.get("nodes") or []
    if not nodes:
        raise HTTPException(status_code=404, detail=f"node not found: {id}")
    try:
        return GraphPayload.model_validate(payload)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
