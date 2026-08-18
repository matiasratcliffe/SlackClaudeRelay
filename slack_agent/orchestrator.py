"""Slack-driven Claude orchestrator — persistent, full-duplex, single session.

A long-lived Claude Agent SDK session the operator drives through a Slack relay.
It runs autonomously; only guarded shell commands (config.GUARD_PATTERNS) and the
model's clarifying questions pause and round-trip to Slack via the QuestionQueue.
A background loop announces new Teams unreads to the same channel.

Full duplex: input and output are decoupled. Every Slack message is handed to
Claude immediately (`session.send`), and a single always-on reader task drains
`session.stream()` — posting EVERY completed turn to Slack the moment it ends,
including proactive turns (a timer firing, a background task or sub-agent
finishing) that no message triggered. Nothing is buffered waiting for the next
message, so there is no reply offset.

This module is just wiring — behavior lives in the focused modules it imports:
  config          settings + session/cwd resolution
  claude_session  the Claude Agent SDK session (options + send + stream)
  slack_io        channel resolution + chunked posting + input cleaning
  interaction     the tagged question queue (approvals + elicitation plumbing)
  permissions     the can_use_tool policy (autonomous-unless-guarded)
  teams_poller    the Teams-unread poll

Run:  .venv/Scripts/python.exe -m slack_agent.orchestrator
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

# Corp TLS interception: trust the Windows cert store for all HTTPS. First.
import truststore

truststore.inject_into_ssl()

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from .claude_session import ClaudeSession
from .config import (
    ANNOUNCE_MODE,
    OWNER_USER,
    POLL_TIME_SPAN_MINUTES,
    SLACK_APP_TOKEN,
    SLACK_BOT_TOKEN,
    TARGET_CHANNEL,
    TEAMS_POLL_ENABLED,
)
from .interaction import QuestionQueue
from .permissions import make_can_use_tool
from .single_instance import acquire_single_instance
from .slack_io import Poster, resolve_channel_id, strip_footer
from .teams_poller import poll_teams_unreads, teams_preflight

logger = logging.getLogger("orchestrator")


def _current_model() -> str:
    """Best-effort model label for the ready banner: env, else settings.json, else 'default'."""
    m = os.environ.get("ANTHROPIC_MODEL")
    if m:
        return m
    try:
        v = json.loads(
            (Path.home() / ".claude" / "settings.json").read_text(encoding="utf-8-sig")
        ).get("model")
        if v:
            return v
    except (OSError, ValueError):
        pass
    return "default"


async def main() -> None:
    # Refuse to start if another orchestrator is running. Held for process life.
    _lock = acquire_single_instance()  # noqa: F841

    if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
        raise SystemExit("Set SLACK_BOT_TOKEN and SLACK_APP_TOKEN (see .env.example).")

    app = AsyncApp(token=SLACK_BOT_TOKEN)
    channel_id = await resolve_channel_id(app.client)
    if not channel_id:
        raise SystemExit(f"Channel '{TARGET_CHANNEL}' not found among bot's channels.")

    poster = Poster(app.client, channel_id)
    queue = QuestionQueue(poster.post)

    async with ClaudeSession(make_can_use_tool(queue)) as session:

        async def reader() -> None:
            # The single always-on consumer of Claude's output. Posts each
            # completed turn — user-triggered OR proactive — as it finishes.
            try:
                async for answer in session.stream():
                    logger.info("answer: %s", answer)
                    await poster.post(answer, mention=True)
            except Exception:
                logger.exception("reader loop crashed")

        asyncio.create_task(reader())

        async def on_message(event, logger) -> None:
            if event.get("bot_id") or event.get("subtype"):
                return
            if event.get("channel") != channel_id:
                return
            if event.get("user") != OWNER_USER:  # obey only the owner
                return
            text = strip_footer((event.get("text") or "").strip())
            if not text:
                return
            if await queue.route(text):  # an answer to an open question
                return
            logger.info("query: %s", text[:120])
            await poster.post("🧠 …")
            # Fire-and-forget: the reply comes back through the reader, not here.
            await session.send(text)

        app.event("message")(on_message)

        async def teams_poll_loop() -> None:
            interval = POLL_TIME_SPAN_MINUTES * 60
            while True:
                try:
                    await poll_teams_unreads(poster.post)
                except Exception as e:
                    logger.error("teams poll loop: %s", e)
                await asyncio.sleep(interval)

        # Teams setup: synchronous preflight (auth + daemon) before the poller.
        if not TEAMS_POLL_ENABLED:
            logger.info("Teams poll loop disabled (TEAMS_POLL_ENABLED)")
        elif await teams_preflight():
            logger.info("Kicking off Teams poller every %d min", POLL_TIME_SPAN_MINUTES)
            asyncio.create_task(teams_poll_loop())
        else:
            logger.info("Teams poller skipped (see warning above)")

        logger.info("Listening on #%s (%s)", TARGET_CHANNEL, channel_id)
        logger.info("=== Claude orchestrator relay running (full duplex) ===")
        # Announce readiness on the channel too (not just the log), so the
        # operator knows the relay is live — especially after a restart.
        await poster.post(
            "✅ Orchestrator ready — full-duplex relay online.\n"
            f"• model: {_current_model()}\n"
            f"• Teams notifications: {ANNOUNCE_MODE} · poll every {POLL_TIME_SPAN_MINUTES}m"
        )
        await AsyncSocketModeHandler(app, SLACK_APP_TOKEN).start_async()


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s %(name)s %(levelname)s %(message)s", level=logging.INFO
    )
    asyncio.run(main())
