"""Insert backend/ onto sys.path so `import app...` works when launched as a script."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
_backend = str(BACKEND_ROOT)
if _backend not in sys.path:
    sys.path.insert(0, _backend)

# MCP stdio uses stdout for the protocol. Keep all logs on stderr.
logging.basicConfig(
    stream=sys.stderr,
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s",
    force=True,
)
