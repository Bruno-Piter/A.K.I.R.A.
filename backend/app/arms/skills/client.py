"""MultiServerMCPClient factory for the Skills ARM."""

from langchain_mcp_adapters.client import MultiServerMCPClient
from app.arms.skills.registry import load_connections


def get_mcp_client() -> MultiServerMCPClient:
    return MultiServerMCPClient(load_connections())


async def get_tools():
    client = get_mcp_client()
    return await client.get_tools()
