"""Concurrency control: hierarchical intent locks on the ownership tree, keyed by agent id.

Tree writes take intent-exclusive (IX) locks on every ancestor and an exclusive (X) lock on the
target, so agents in disjoint subtrees never contend. Secondary edges are NOT locked here — they use
optimistic version/CAS via `StorageBackend.cas_update`; `retry()` drives those loops. Locks are
leased so a crashed agent's locks free on expiry.
"""

from __future__ import annotations

import threading
import time

# mode -> set of modes it is compatible with (held by *other* agents on the same path)
_COMPAT = {
    "IS": {"IS", "IX", "S"},
    "IX": {"IS", "IX"},
    "S": {"IS", "S"},
    "X": set(),
}


class LockConflict(RuntimeError):
    pass


class _Holder:
    __slots__ = ("agent_id", "mode", "count", "expiry")

    def __init__(self, agent_id: str, mode: str, expiry: float) -> None:
        self.agent_id = agent_id
        self.mode = mode
        self.count = 1
        self.expiry = expiry


class LockManager:
    """In-memory intent-lock table. A Neo4j deployment would back this with a locks table or
    `apoc.lock.nodes`; the semantics are identical."""

    def __init__(self, store, default_ttl: float = 30.0) -> None:
        self._store = store
        self._ttl = default_ttl
        self._table: dict[str, list[_Holder]] = {}
        self._mx = threading.RLock()

    # --- public API ---
    def acquire_write(self, agent_id: str, node_id: str, ttl: float | None = None) -> None:
        """IX on all ancestors + X on `node_id`. Raises LockConflict on contention."""
        plan = [(a, "IX") for a in self._store.ancestors(node_id)] + [(node_id, "X")]
        self._acquire(agent_id, plan, ttl)

    def acquire_read(self, agent_id: str, node_id: str, ttl: float | None = None) -> None:
        """IS on all ancestors + S on `node_id`."""
        plan = [(a, "IS") for a in self._store.ancestors(node_id)] + [(node_id, "S")]
        self._acquire(agent_id, plan, ttl)

    def release_all(self, agent_id: str) -> None:
        with self._mx:
            for path in list(self._table):
                self._table[path] = [h for h in self._table[path] if h.agent_id != agent_id]
                if not self._table[path]:
                    del self._table[path]

    def holders(self, node_id: str) -> list[tuple[str, str]]:
        with self._mx:
            self._sweep_locked()
            return [(h.agent_id, h.mode) for h in self._table.get(node_id, [])]

    def sweep(self) -> None:
        with self._mx:
            self._sweep_locked()

    def snapshot(self) -> dict[str, list[tuple[str, str]]]:
        """Current lock table: `path -> [(agent_id, mode)]` (expired entries swept first)."""
        with self._mx:
            self._sweep_locked()
            return {p: [(h.agent_id, h.mode) for h in hs] for p, hs in self._table.items()}

    @staticmethod
    def retry(fn, attempts: int = 5):
        """Run a CAS operation `fn() -> bool`, retrying while it reports a stale-version loss."""
        for _ in range(attempts):
            if fn():
                return True
        return False

    # --- internals ---
    def _acquire(self, agent_id, plan, ttl):
        exp = time.time() + (ttl if ttl is not None else self._ttl)
        with self._mx:
            self._sweep_locked()
            for path, mode in plan:                       # check all before granting → atomic
                for h in self._table.get(path, []):
                    if h.agent_id != agent_id and mode not in _COMPAT[h.mode]:
                        raise LockConflict(f"{agent_id} wants {mode} on {path!r}; "
                                           f"held {h.mode} by {h.agent_id}")
            for path, mode in plan:                       # grant (root→leaf order in `plan`)
                self._grant_locked(agent_id, path, mode, exp)

    def _grant_locked(self, agent_id, path, mode, exp):
        holders = self._table.setdefault(path, [])
        for h in holders:
            if h.agent_id == agent_id:                    # re-entrant: keep strongest mode
                h.count += 1
                h.expiry = exp
                if _rank(mode) > _rank(h.mode):
                    h.mode = mode
                return
        holders.append(_Holder(agent_id, mode, exp))

    def _sweep_locked(self):
        now = time.time()
        for path in list(self._table):
            self._table[path] = [h for h in self._table[path] if h.expiry > now]
            if not self._table[path]:
                del self._table[path]


def _rank(mode: str) -> int:
    return {"IS": 0, "S": 1, "IX": 2, "X": 3}[mode]
