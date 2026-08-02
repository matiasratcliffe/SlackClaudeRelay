"""Slack-driven Claude orchestrator — persistent, streaming, single serial session.

A long-lived Claude Agent SDK session the operator drives through a Slack relay.
It runs autonomously; only guarded shell commands (config.GUARD_PATTERNS) and the
model's clarifying questions pause and round-trip to Slack via the QuestionQueue.
A background loop announces new Teams unreads to the same channel.

This module is just wiring — behavior lives in the focused modules it imports:
  config        settings + session/cwd resolution
  slack_io      channel resolution + chunked posting + input cleaning
  interaction   the tagged question queue (approvals + elicitation plumbing)
  permissions   the can_use_tool policy (autonomous-unless-guarded)
  teams_poller  the Teams-unread poll

Run:  .venv/Scripts/python.exe -m slack_agent.orchestrator
"""

from __future__ import annotations

import asyncio
import logging

# Corp TLS interception: trust the Windows cert store for all HTTPS. First.
import truststore

truststore.inject_into_ssl()

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
)

from .config import (
    ORCH_SESSION_ID,
    OWNER_USER,
    POLL_TIME_SPAN_MINUTES,
    SLACK_APP_TOKEN,
    SLACK_BOT_TOKEN,
    SYSTEM_PROMPT,
    TARGET_CHANNEL,
    resolve_cwd,
    session_kwargs,
)
from .interaction import QuestionQueue
from .permissions import make_can_use_tool
from .slack_io import Poster, resolve_channel_id, strip_footer
from .teams_poller import poll_teams_unreads

logger = logging.getLogger("orchestrator")


async def main() -> None:
    if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
        raise SystemExit("Set SLACK_BOT_TOKEN and SLACK_APP_TOKEN (see .env.example).")

    app = AsyncApp(token=SLACK_BOT_TOKEN)
    channel_id = await resolve_channel_id(app.client)
    if not channel_id:
        raise SystemExit(f"Channel '{TARGET_CHANNEL}' not found among bot's channels.")

    poster = Poster(app.client, channel_id)
    queue = QuestionQueue(poster.post)

    options = ClaudeAgentOptions(
        # Full Claude Code system prompt + our orchestrator note appended.
        system_prompt={"type": "preset", "preset": "claude_code", "append": SYSTEM_PROMPT},
        # Inherit ALL of the user's ~/.claude context: settings, hooks, CLAUDE.md,
        # permissions, skills, plus project/local for the working repo.
        setting_sources=["user", "project", "local"],
        skills="all",
        # "default" (NOT bypassPermissions) so can_use_tool is actually consulted.
        permission_mode="default",
        can_use_tool=make_can_use_tool(queue),
        cwd=resolve_cwd(),
        **session_kwargs(),
    )
    logger.info("Working dir: %s | session: %s", options.cwd, ORCH_SESSION_ID)

    async with ClaudeSDKClient(options=options) as client:
        lock = asyncio.Lock()

        async def handle_query(text: str) -> None:
            async with lock:  # single serial session
                await poster.post("🧠 …")
                await client.query(text)
                parts: list[str] = []
                async for msg in client.receive_response():
                    if isinstance(msg, AssistantMessage):
                        for block in msg.content:
                            if isinstance(block, TextBlock) and block.text.strip():
                                parts.append(block.text)
                    elif isinstance(msg, ResultMessage):
                        break
                await poster.post("\n\n".join(parts).strip() or "[no text output]", mention=True)

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
            asyncio.create_task(handle_query(text))

        app.event("message")(on_message)

        async def teams_poll_loop() -> None:
            interval = POLL_TIME_SPAN_MINUTES * 60
            logger.info("Teams poll loop started (every %d min)", POLL_TIME_SPAN_MINUTES)
            while True:
                try:
                    await poll_teams_unreads(poster.post)
                except Exception as e:
                    logger.error("teams poll loop: %s", e)
                await asyncio.sleep(interval)

        asyncio.create_task(teams_poll_loop())

        logger.info("Listening on #%s (%s)", TARGET_CHANNEL, channel_id)
        await AsyncSocketModeHandler(app, SLACK_APP_TOKEN).start_async()


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s %(name)s %(levelname)s %(message)s", level=logging.INFO
    )
    asyncio.run(main())
