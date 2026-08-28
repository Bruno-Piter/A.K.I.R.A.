"""POST /api/chat/stream — SSE over the query StateGraph."""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.schemas import ChatSource, ChatStreamRequest, SseEvent, SseEventType

logger = logging.getLogger(__name__)

router = APIRouter()

_QUERY_NODES = {
    "planner",
    "intent_router",
    "retrieval_router",
    "react_tools",
    "quality_gate",
    "generate",
    "query_graph",
}


@router.post("/chat/stream")
async def chat_stream(body: ChatStreamRequest) -> StreamingResponse:
    return StreamingResponse(
        _stream_chat_sync(body),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _stream_chat_sync(body: ChatStreamRequest) -> Iterator[str]:
    thread_id = (body.thread_id or "").strip() or str(uuid.uuid4())
    yield _sse(
        SseEvent(
            type=SseEventType.stage,
            content={"node": "query_graph", "status": "start", "thread_id": thread_id},
        )
    )
    try:
        from app.arms.routines.query_graph import get_query_graph

        graph = get_query_graph()
    except Exception as exc:
        logger.exception("query graph compile failed")
        yield _sse(
            SseEvent(
                type=SseEventType.done,
                content={"answer": "", "thread_id": thread_id, "error": str(exc)},
            )
        )
        return

    inputs: dict[str, Any] = {
        "query": body.message or "",
        "session_id": thread_id,
        "thread_id": thread_id,
        "document_ids": list(body.document_ids or []),
        "hits": [],
        "retrieved": [],
        "tool_results": [],
        "backtrack_count": 0,
        "messages": [],
    }
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 32}
    answer = ""
    sources: list[dict[str, Any]] = []
    graph_context: dict[str, Any] = {"nodes": [], "links": []}
    error = ""
    sources_sent = False
    graph_sent = False

    try:
        for item in graph.stream(inputs, config, stream_mode=["updates", "custom"]):
            mode, chunk = _unpack_stream_item(item)
            if mode == "custom" and isinstance(chunk, dict):
                kind = chunk.get("type")
                if kind == "token":
                    yield _sse(
                        SseEvent(type=SseEventType.token, content=chunk.get("content") or "")
                    )
                elif kind == "stage":
                    yield _sse(SseEvent(type=SseEventType.stage, content=chunk))
                continue
            if mode == "updates" and isinstance(chunk, dict):
                for node_name, update in chunk.items():
                    if str(node_name).startswith("__"):
                        continue
                    if node_name in _QUERY_NODES or node_name:
                        yield _sse(
                            SseEvent(
                                type=SseEventType.stage,
                                content={"node": node_name, "status": "end"},
                            )
                        )
                    if not isinstance(update, dict):
                        continue
                    if update.get("answer"):
                        answer = str(update["answer"])
                    if update.get("error"):
                        error = str(update["error"])
                    retrieved = update.get("retrieved") or update.get("hits")
                    if retrieved and not sources_sent:
                        sources = _to_sources(retrieved)
                        if sources:
                            yield _sse(SseEvent(type=SseEventType.sources, content=sources))
                            sources_sent = True
                    payload = update.get("graph_context") or update.get("graph_payload")
                    if payload and not graph_sent:
                        graph_context = payload or graph_context
                        yield _sse(
                            SseEvent(type=SseEventType.graph_context, content=graph_context)
                        )
                        graph_sent = True
                    if update.get("sources") and not sources_sent:
                        sources = _to_sources(update["sources"])
                        if sources:
                            yield _sse(SseEvent(type=SseEventType.sources, content=sources))
                            sources_sent = True
    except Exception as exc:
        logger.exception("query graph run failed")
        error = str(exc)

    if not sources_sent and sources:
        yield _sse(SseEvent(type=SseEventType.sources, content=sources))
    if not graph_sent and isinstance(graph_context, dict) and graph_context.get("nodes"):
        yield _sse(SseEvent(type=SseEventType.graph_context, content=graph_context))

    done_content: dict[str, Any] = {"answer": answer, "thread_id": thread_id}
    if error:
        done_content["error"] = error
    yield _sse(SseEvent(type=SseEventType.done, content=done_content))


def _unpack_stream_item(item: Any) -> tuple[str, Any]:
    if isinstance(item, tuple):
        if len(item) == 2:
            return str(item[0]), item[1]
        if len(item) == 3:
            return str(item[1]), item[2]
    return "updates", item


def _to_sources(retrieved: Any) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    if not isinstance(retrieved, list):
        return sources
    for hit in retrieved:
        if not isinstance(hit, dict):
            continue
        try:
            source = ChatSource(
                chunk_id=str(hit.get("chunk_id") or hit.get("entity_id") or ""),
                document_id=str(hit.get("document_id") or ""),
                title=str(hit.get("title") or ""),
                excerpt=str(hit.get("excerpt") or ""),
                score=_opt_float(hit.get("score")),
            )
            sources.append(source.model_dump())
        except Exception:
            continue
    return sources


def _opt_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sse(event: SseEvent) -> str:
    payload = event.model_dump()
    type_value = payload.get("type")
    if hasattr(type_value, "value"):
        type_value = type_value.value
    type_value = str(type_value)
    payload["type"] = type_value
    return f"event: {type_value}\ndata: {json.dumps(payload, default=str)}\n\n"