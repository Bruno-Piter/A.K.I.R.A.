"""List MCP tools exposed by the Skills ARM. Run as `python -m app.arms.skills.boot`."""

from __future__ import annotations

import asyncio
import sys

from app.arms.skills.client import get_tools


async def main() -> int:
    tools = await get_tools()
    for tool in tools:
        print(tool.name)
    print(len(tools))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except SystemExit:
        raise
    except Exception as exc:
        print(f"boot failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
