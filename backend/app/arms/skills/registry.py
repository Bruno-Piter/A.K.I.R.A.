"""Load skills.yaml and build MultiServerMCPClient stdio connections."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

BACKEND_ROOT = Path(__file__).resolve().parents[3]
_YAML_PATH = Path(__file__).resolve().parent / "skills.yaml"


def _resolve_command(command: str) -> str:
    if command == "python":
        return sys.executable
    return command


def _resolve_args(args: list) -> list[str]:
    resolved: list[str] = []
    for arg in args:
        path = Path(str(arg))
        if path.is_absolute():
            resolved.append(str(path))
        else:
            resolved.append(str((BACKEND_ROOT / path).resolve()))
    return resolved


def load_connections() -> dict:
    """Return a connections dict suitable for MultiServerMCPClient."""
    spec = yaml.safe_load(_YAML_PATH.read_text(encoding="utf-8")) or {}
    servers = spec.get("servers") or {}
    env = {
        **os.environ,
        "PYTHONPATH": str(BACKEND_ROOT),
        "PYTHONUNBUFFERED": "1",
    }
    connections: dict = {}
    for name, cfg in servers.items():
        connections[name] = {
            "transport": cfg.get("transport") or "stdio",
            "command": _resolve_command(str(cfg["command"])),
            "args": _resolve_args(list(cfg.get("args") or [])),
            "cwd": str(BACKEND_ROOT),
            "env": env,
            "encoding": "utf-8",
        }
    return connections
