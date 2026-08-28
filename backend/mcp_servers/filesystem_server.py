"""Read-only filesystem MCP server, sandboxed to C:\\PROJETOS\\akira\\data."""

from __future__ import annotations

import _bootstrap  # noqa: F401

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("filesystem", log_level="ERROR")

ALLOWLIST_ROOT = Path(r"C:\PROJETOS\akira\data").resolve()


def _is_within_allowlist(resolved: Path) -> bool:
    """Return True if resolved is the allowlist root or a descendant."""
    try:
        resolved.relative_to(ALLOWLIST_ROOT)
    except ValueError:
        return False
    root = os.path.normcase(str(ALLOWLIST_ROOT))
    target = os.path.normcase(str(resolved))
    if target == root:
        return True
    return target.startswith(root + os.sep)


def _safe_resolve(relative_path: str) -> tuple[Path | None, dict | None]:
    """Resolve relative_path under the allowlist, or return an error dict."""
    if not ALLOWLIST_ROOT.exists() or not ALLOWLIST_ROOT.is_dir():
        return None, {
            "ok": False,
            "error": (
                f"Allowlist data directory does not exist: {ALLOWLIST_ROOT}. "
                "Skills will not create it."
            ),
        }
    resolved = (ALLOWLIST_ROOT / relative_path).resolve()
    if not _is_within_allowlist(resolved):
        return None, {
            "ok": False,
            "error": "Path escapes the filesystem allowlist root.",
            "relative_path": relative_path,
        }
    return resolved, None


@mcp.tool()
def list_directory(relative_path: str = ".") -> dict:
    """List entries under the allowlisted data directory. Read-only."""
    target, err = _safe_resolve(relative_path)
    if err is not None:
        return err
    if not target.exists():
        return {"ok": False, "error": "Path not found.", "relative_path": relative_path}
    if not target.is_dir():
        return {"ok": False, "error": "Not a directory.", "relative_path": relative_path}

    entries = []
    for child in sorted(target.iterdir(), key=lambda p: p.name.lower()):
        item = {"name": child.name, "is_dir": child.is_dir()}
        if child.is_file():
            try:
                item["size"] = child.stat().st_size
            except OSError:
                item["size"] = None
        entries.append(item)
    rel = target.relative_to(ALLOWLIST_ROOT).as_posix() or "."
    return {"ok": True, "path": rel, "entries": entries}


@mcp.tool()
def read_file(relative_path: str, max_bytes: int = 65536) -> dict:
    """Read a text file under the allowlisted data directory. Read-only."""
    target, err = _safe_resolve(relative_path)
    if err is not None:
        return err
    if not target.exists():
        return {"ok": False, "error": "File not found.", "relative_path": relative_path}
    if not target.is_file():
        return {"ok": False, "error": "Not a file.", "relative_path": relative_path}

    limit = max(0, int(max_bytes))
    size = target.stat().st_size
    data = target.read_bytes()[:limit]
    truncated = size > limit
    text = data.decode("utf-8", errors="replace")
    rel = target.relative_to(ALLOWLIST_ROOT).as_posix()
    return {
        "ok": True,
        "path": rel,
        "truncated": truncated,
        "size": size,
        "content": text,
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
