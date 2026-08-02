"""Concurrent-safe question queue for operator round-trips.

When the orchestrator needs the operator to answer something — a guarded-action
approval or a clarifying question — it calls `queue.ask(...)`, which posts a
tagged prompt (`[Q1] ...`) and blocks until the operator's reply for that tag
arrives. Several questions can be outstanding at once (e.g. from parallel
subagents); each has its own tag so replies are never ambiguous.

Transport-agnostic: constructed with a `post(text, mention=False)` coroutine.
"""

from __future__ import annotations

import asyncio
import re

_TAG_RE = re.compile(r"^\s*(Q\d+)\b[:\s]*(.*)$", re.IGNORECASE | re.DOTALL)


class QuestionQueue:
    def __init__(self, post) -> None:
        self._post = post
        self._pending: dict[str, asyncio.Future] = {}
        self._counter = 0

    @property
    def has_open(self) -> bool:
        return bool(self._pending)

    async def ask(self, body: str) -> str:
        """Post a tagged question and block until the operator answers that tag."""
        self._counter += 1
        qid = f"Q{self._counter}"
        fut = asyncio.get_running_loop().create_future()
        self._pending[qid] = fut
        await self._post(f"*[{qid}]* {body}\n_reply `{qid} <answer>`_", mention=True)
        try:
            return await fut
        finally:
            self._pending.pop(qid, None)

    async def route(self, text: str) -> bool:
        """If `text` answers an open question, resolve it and return True.
        Returns False when there is nothing open (so the caller treats it as a
        new request). With exactly one open question, a bare reply answers it."""
        if not self._pending:
            return False
        m = _TAG_RE.match(text)
        if m and m.group(1).upper() in self._pending:
            self._pending[m.group(1).upper()].set_result(m.group(2).strip())
            return True
        if len(self._pending) == 1:
            next(iter(self._pending.values())).set_result(text)
            return True
        await self._post(
            "Open questions: "
            + ", ".join(sorted(self._pending))
            + " — reply with the tag, e.g. `Q1 yes`.",
            mention=True,
        )
        return True
