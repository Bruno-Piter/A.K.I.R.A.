"""SQLite checkpointer factory. Persists LangGraph state to disk, not RAM."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
CHECKPOINT_PATH = _BACKEND_ROOT / "data" / "routines-checkpoints.sqlite"

_conn: sqlite3.Connection | None = None
_checkpointer: Any = None


def get_checkpointer() -> Any:
    """Return a process-wide SqliteSaver (check_same_thread=False)."""
    global _conn, _checkpointer
    if _checkpointer is not None:
        return _checkpointer
    from langgraph.checkpoint.sqlite import SqliteSaver

    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(str(CHECKPOINT_PATH), check_same_thread=False)
    saver = SqliteSaver(_conn)
    saver.setup()
    _checkpointer = saver
    logger.info("routines checkpointer ready at %s", CHECKPOINT_PATH)
    return _checkpointer


def close_checkpointer() -> None:
    global _conn, _checkpointer
    _checkpointer = None
    if _conn is not None:
        try:
            _conn.close()
        except Exception:
            logger.debug("checkpointer connection already closed")
        _conn = None