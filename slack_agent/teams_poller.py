"""Teams-unread -> Slack poller.

Runs `teams unreads --json` and announces any unread element not seen before to
the Slack channel, tagging the owner. The dedupe store (`teams_seen`) is an
in-memory list that starts empty and grows over the process lifetime, so each
unread is announced only once.

The poll logic takes an injected `post` coroutine so the orchestrator can reuse
it with its own Slack client. Run this module directly to fire a single poll:

    .venv/Scripts/python.exe -m slack_agent.teams_poller
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

from slack_sdk.web.async_client import AsyncWebClient


def _load_dotenv() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())


_load_dotenv()

logger = logging.getLogger("teams_poller")

POLL_TIME_SPAN_MINUTES = int(os.environ.get("POLL_TIME_SPAN_MINUTES", "10"))
TEAMS_CMD = os.environ.get("TEAMS_CMD", "teams")  # `teams` CLI on PATH
TARGET_CHANNEL = os.environ.get("SLACK_CHANNEL", "general-personal")
OWNER_USER = "U0BLY0DHJF8"  # mati.ratcliffe
MENTION = f"<@{OWNER_USER}>"
_SLACK_MAX = 4096

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
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        raise SystemExit("Set SLACK_BOT_TOKEN (see .env.example).")
    client = AsyncWebClient(token=token)

    resp = await client.users_conversations(types="public_channel", limit=200)
    channel_id = next(
        (c["id"] for c in resp["channels"] if c["name"] == TARGET_CHANNEL), None
    )
    if not channel_id:
        raise SystemExit(f"Channel '{TARGET_CHANNEL}' not found among bot's channels.")

    async def post(text: str, mention: bool = False) -> None:
        body = (f"{MENTION} " if mention else "") + text
        for i in range(0, len(body), _SLACK_MAX):
            await client.chat_postMessage(channel=channel_id, text=body[i : i + _SLACK_MAX])

    new = await poll_teams_unreads(post)
    logger.info("poll-once done: %d new, %d seen total", len(new), len(teams_seen))


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s %(name)s %(levelname)s %(message)s", level=logging.INFO
    )
    asyncio.run(_run_once())
