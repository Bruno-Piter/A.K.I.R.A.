"""Web search MCP server. Calls Tavily REST via httpx when TAVILY_API_KEY is set."""

from __future__ import annotations

import _bootstrap  # noqa: F401

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Repo root is parents[2] from backend/mcp_servers/. Env var wins (dotenv does not override).
_repo_root = Path(__file__).resolve().parents[2]
load_dotenv(_repo_root / ".env")

mcp = FastMCP("web_search", log_level="ERROR")

_TAVILY_URL = "https://api.tavily.com/search"


@mcp.tool()
def web_search(query: str, max_results: int = 5) -> dict:
    """Search the web via Tavily. Disabled when TAVILY_API_KEY is not set."""
    api_key = os.getenv("TAVILY_API_KEY") or ""
    if not api_key.strip():
        return {
            "ok": False,
            "enabled": False,
            "reason": "TAVILY_API_KEY is not set. Web search is disabled.",
        }

    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(_TAVILY_URL, json=payload)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        return {"ok": False, "enabled": True, "error": str(exc), "query": query}

    results = []
    for item in data.get("results") or []:
        results.append(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "content": item.get("content"),
            }
        )
    return {"ok": True, "query": query, "results": results}


if __name__ == "__main__":
    mcp.run(transport="stdio")
