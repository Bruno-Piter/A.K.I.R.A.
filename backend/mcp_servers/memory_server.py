"""Memory MCP server. Dispatches to app.arms.memory; never runs Cypher here."""

from __future__ import annotations

import _bootstrap  # noqa: F401

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("memory", log_level="ERROR")

try:
    from app.arms.memory import hybrid_search, neighborhood
    from app.arms.memory.retriever import search as memory_search
except ImportError:
    hybrid_search = None
    neighborhood = None
    memory_search = None


def _kernel_missing(tool: str) -> dict:
    return {
        "ok": False,
        "tool": tool,
        "todo": (
            "Wait for Agent 2 (Memory) kernel at app.arms.memory. "
            "Do not duplicate Cypher in Skills."
        ),
    }


def _call(tool: str, fn, **kwargs):
    if fn is None:
        return _kernel_missing(tool)
    try:
        result = fn(**kwargs)
    except Exception as exc:
        return {"ok": False, "tool": tool, "error": str(exc)}
    if isinstance(result, dict):
        return {"ok": True, "tool": tool, **result}
    return {"ok": True, "tool": tool, "hits": result}


@mcp.tool()
def search_graph(query: str, top_k: int = 8) -> dict:
    """Search the knowledge graph (hybrid vector + keyword over chunks and entities)."""
    return _call("search_graph", hybrid_search, query=query, top_k=top_k)


@mcp.tool()
def expand_entity(entity_id: str, hops: int = 1) -> dict:
    """Expand an entity by returning its neighborhood for the given hop count."""
    return _call("expand_entity", neighborhood, id=entity_id, hops=hops)


@mcp.tool()
def multi_hop(
    start_id: str,
    max_hops: int = 3,
    rel_types: str | None = None,
) -> dict:
    """Multi-hop retrieval seeded from start_id. Kernel has no rel_types filter."""
    del rel_types  # kernel search() does not accept relationship-type filters
    return _call(
        "multi_hop",
        memory_search,
        query=start_id,
        mode="multi_hop",
        hops=max_hops,
    )


@mcp.tool()
def get_neighborhood(id: str, hops: int = 2) -> dict:
    """Return the undirected neighborhood of a node as a graph payload."""
    return _call("get_neighborhood", neighborhood, id=id, hops=hops)


if __name__ == "__main__":
    mcp.run(transport="stdio")