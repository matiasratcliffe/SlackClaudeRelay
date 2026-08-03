"""The Claude Agent SDK session — every Claude concern lives here, nothing Slack.

Isolated from the orchestrator/Slack wiring so it can be exercised on its own:
build the options, connect a session, feed it with `send()` and drain `stream()`.
Kept deliberately transport-agnostic (no Slack import) — the orchestrator is the
only thing that bridges this to a channel.

Full duplex is the whole point. Input and output are decoupled:

  * `send(text)` writes a user message to Claude and returns immediately — it
    NEVER reads the reply.
  * `stream()` is a single always-on reader over the SDK's whole-lifetime
    message stream. It surfaces EVERY completed turn — including proactive ones
    that no `send()` triggered (a background task finishing, a timer firing, a
    sub-agent completing). The SDK funnels those in as `system`/task frames on
    the same stream and wakes a follow-up turn; the reader picks the result up
    the moment that turn ends.

That decoupling is the fix for the old request/response coupling, where the relay
only read Claude's output while handling a user message — so anything Claude
emitted between messages sat buffered until the next one, offsetting every reply.

SDK constraint: exactly ONE task may iterate the message stream (single-consumer),
and it must keep draining it (the internal buffer caps at 100 frames). So run a
single `stream()` consumer for the process lifetime; `send()` may be called from
anywhere concurrently.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterable, AsyncIterator

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
)

from .config import ORCH_SESSION_ID, SYSTEM_PROMPT, resolve_cwd, session_kwargs

logger = logging.getLogger("claude_session")


def build_options(can_use_tool) -> ClaudeAgentOptions:
    """Assemble the orchestrator's ClaudeAgentOptions. Pure — no I/O, no connect —
    so a test can build and inspect it without spawning the CLI."""
    return ClaudeAgentOptions(
        # Full Claude Code system prompt + our orchestrator note appended.
        system_prompt={"type": "preset", "preset": "claude_code", "append": SYSTEM_PROMPT},
        # Inherit ALL of the user's ~/.claude context: settings, hooks, CLAUDE.md,
        # permissions, skills, plus project/local for the working repo.
        setting_sources=["user", "project", "local"],
        skills="all",
        # "default" (NOT bypassPermissions) so can_use_tool is actually consulted.
        permission_mode="default",
        can_use_tool=can_use_tool,
        cwd=resolve_cwd(),
        **session_kwargs(),
    )


async def turns(messages: AsyncIterable) -> AsyncIterator[str]:
    """Group a raw SDK message stream into one string per COMPLETED turn.

    Accumulates assistant text and yields it when the turn's `ResultMessage`
    arrives, then resets. Empty turns (a `ResultMessage` with no assistant text —
    e.g. a silent tool-only turn) are skipped so proactive/background turns don't
    post noise.

    Pure with respect to the SDK client: pass `client.receive_messages()` in
    production, or a hand-built async iterable of AssistantMessage/ResultMessage
    objects in a unit test.
    """
    parts: list[str] = []
    async for msg in messages:
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    parts.append(block.text)
        elif isinstance(msg, ResultMessage):
            answer = "\n\n".join(parts).strip()
            parts = []
            if answer:
                yield answer


class ClaudeSession:
    """A connected ClaudeSDKClient plus the two full-duplex primitives.

    Use as an async context manager. `send()` writes a user message and returns;
    `stream()` is the single always-on reader (exactly one consumer allowed).
    """

    def __init__(self, can_use_tool) -> None:
        self._options = build_options(can_use_tool)
        self._client: ClaudeSDKClient | None = None

    async def __aenter__(self) -> "ClaudeSession":
        self._client = ClaudeSDKClient(options=self._options)
        await self._client.__aenter__()
        logger.info(
            "Claude session connected (cwd=%s, id=%s)", self._options.cwd, ORCH_SESSION_ID
        )
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client is not None:
            await self._client.__aexit__(*exc)
            self._client = None

    async def send(self, text: str) -> None:
        """Write a user message to Claude and return immediately — does NOT read
        the reply. The response surfaces through `stream()` when its turn ends."""
        if self._client is None:
            raise RuntimeError("ClaudeSession.send() before connect")
        await self._client.query(text)

    def stream(self) -> AsyncIterator[str]:
        """Always-on reader: yields the accumulated assistant text of each
        completed turn (proactive turns included; empty turns skipped). Iterate
        this from exactly ONE task for the whole process lifetime."""
        if self._client is None:
            raise RuntimeError("ClaudeSession.stream() before connect")
        return turns(self._client.receive_messages())
