"""Teams-unread -> Slack poller.

Runs `teams unreads --json` and announces any unread element that appeared since
the previous poll to the Slack channel, tagging the owner. The comparison is
against `last_unreads` — a snapshot of the previous poll that is replaced every
poll — so only genuine changes are announced and cleared unreads drop out.

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

# Snapshot of the PREVIOUS poll's unreads. Replaced every poll, so we only ever
# compare against the last poll (orphans that cleared drop out; a chat that
# clears then reappears re-announces). Starts empty.
last_unreads: list = []


async def _run_teams(subcmd: str) -> tuple[int, str]:
    """Run `teams <subcmd>` capturing combined output. Returns (returncode, text)."""
    try:
        proc = await asyncio.create_subprocess_shell(
            f"{TEAMS_CMD} {subcmd}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await proc.communicate()
    except Exception as e:
        logger.error("teams %s: failed to launch: %s", subcmd, e)
        return 1, ""
    return proc.returncode, out.decode(errors="replace").strip()


async def teams_preflight() -> bool:
    """Run once on startup, before the poll loop. Returns True if the poller
    should run. Verifies authentication (skips on 'not authenticated'), then
    ensures the Teams daemon is up (starting it if 'not running')."""
    _, status = await _run_teams("status")
    if status.lower().startswith("authenticated"):
        logger.info("Teams: %s", status)
    else:  # "not authenticated — run: teams login (...)" or unexpected
        logger.warning(
            "Teams not authenticated — skipping poller. Run `teams login`. (%s)",
            status.splitlines()[0] if status else "no output",
        )
        return False

    _, dstat = await _run_teams("daemon status")
    if dstat.lower().startswith("running"):
        logger.info("Teams daemon: %s", dstat)
    else:  # "not running"
        logger.info("Teams daemon not running — starting it (`teams daemon start`)")
        _, dstart = await _run_teams("daemon start")
        logger.info("Teams daemon start: %s", dstart.splitlines()[-1] if dstart else "(no output)")
    return True


async def poll_teams_unreads(post) -> list:
    """One poll cycle: run `teams unreads --json`, and for every unread element
    that wasn't in the previous poll's snapshot (`last_unreads`), call
    `post(text, mention=True)` (tagging the owner). Then replace `last_unreads`
    with the current unreads. Returns the newly-appeared elements.

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

    new = [x for x in items if x not in last_unreads]
    if new:
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
    # Replace the snapshot with the current unreads (drops orphans, updates counts).
    last_unreads[:] = items
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
    logger.info("poll-once done: %d new, %d currently unread", len(new), len(last_unreads))


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s %(name)s %(levelname)s %(message)s", level=logging.INFO
    )
    asyncio.run(_run_once())
