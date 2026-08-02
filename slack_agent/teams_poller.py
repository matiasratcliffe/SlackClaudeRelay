"""Teams-unread -> Slack poller.

Runs `teams unreads --json` and announces any unread element not seen before to
the Slack channel, tagging the owner. The dedupe store (`teams_seen`) is an
in-memory list that starts empty and grows over the process lifetime, so each
unread is announced only once.

`poll_teams_unreads(post)` takes an injected `post` coroutine so the orchestrator
can reuse it with its own client. Run this module directly to fire one poll:

    .venv/Scripts/python.exe -m slack_agent.teams_poller
"""

from __future__ import annotations

import asyncio
import json
import logging

# Corp TLS interception: trust the Windows cert store for all HTTPS. First.
import truststore

truststore.inject_into_ssl()

from slack_sdk.web.async_client import AsyncWebClient

from .config import SLACK_BOT_TOKEN, TARGET_CHANNEL, TEAMS_CMD
from .slack_io import Poster, resolve_channel_id

logger = logging.getLogger("teams_poller")

# In-memory record of unread elements already announced. Starts empty.
teams_seen: list = []


async def poll_teams_unreads(post) -> list:
    """One poll cycle: run `teams unreads --json`, and for every unread element
    not already in `teams_seen`, call `post(text, mention=True)` (tagging the
    owner). New elements are appended to `teams_seen`. Returns the new elements.

    `post` is a coroutine: `async def post(text: str, mention: bool = False)`.
    Never raises — logs and returns [] on any failure so a caller's loop is safe.
    """
    try:
        proc = await asyncio.create_subprocess_shell(
            f"{TEAMS_CMD} unreads --json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
    except Exception as e:
        logger.error("teams poll: failed to launch CLI: %s", e)
        return []

    if proc.returncode != 0:
        logger.error(
            "teams poll: exit %s: %s",
            proc.returncode,
            err.decode(errors="replace").strip()[:300],
        )
        return []

    text = out.decode(errors="replace").strip()
    try:
        items = json.loads(text) if text else []
    except json.JSONDecodeError:
        logger.error("teams poll: non-JSON output: %s", text[:200])
        return []
    if not isinstance(items, list):
        return []

    new = [x for x in items if x not in teams_seen]
    if new:
        teams_seen.extend(new)
        lines = [f":envelope_with_arrow: *{len(new)}* new Teams unread(s):"]
        for it in new:
            if isinstance(it, dict):
                name = it.get("name", "?")
                cnt = it.get("count", "")
                lines.append(f"• {name}" + (f" — {cnt}" if cnt != "" else ""))
            else:
                lines.append(f"• {it}")
        await post("\n".join(lines), mention=True)
        logger.info("teams poll: %d new unread(s) announced", len(new))
    return new


async def _run_once() -> None:
    """Standalone: connect a Slack web client, resolve the channel, poll once."""
    if not SLACK_BOT_TOKEN:
        raise SystemExit("Set SLACK_BOT_TOKEN (see .env.example).")
    client = AsyncWebClient(token=SLACK_BOT_TOKEN)
    channel_id = await resolve_channel_id(client)
    if not channel_id:
        raise SystemExit(f"Channel '{TARGET_CHANNEL}' not found among bot's channels.")
    new = await poll_teams_unreads(Poster(client, channel_id).post)
    logger.info("poll-once done: %d new, %d seen total", len(new), len(teams_seen))


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s %(name)s %(levelname)s %(message)s", level=logging.INFO
    )
    asyncio.run(_run_once())
