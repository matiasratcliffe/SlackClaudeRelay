"""Single-instance guard.

Binds a fixed localhost port and holds it for the process lifetime. A second
orchestrator trying to bind the same port fails, so only one can run. The OS
releases the port automatically when the process exits or crashes — no stale
lock file to clean up.
"""

from __future__ import annotations

import logging
import socket

from .config import ORCH_LOCK_PORT

logger = logging.getLogger("orchestrator")

_LOCK_HOST = "127.0.0.1"


def acquire_single_instance() -> socket.socket:
    """Return the bound lock socket, or exit if another instance holds it.
    Keep the returned socket referenced for the whole process lifetime."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Reserve the port exclusively so no later socket can share it and the
    # second bind fails hard; on Windows a plain bind is shareable via
    # SO_REUSEADDR, SO_EXCLUSIVEADDRUSE closes that hole.
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        sock.bind((_LOCK_HOST, ORCH_LOCK_PORT))
        sock.listen(1)
    except OSError:
        sock.close()
        raise SystemExit(
            f"Another orchestrator is already running (lock port {ORCH_LOCK_PORT} "
            "in use). Exiting."
        )
    logger.info("Single-instance lock acquired (port %d)", ORCH_LOCK_PORT)
    return sock
