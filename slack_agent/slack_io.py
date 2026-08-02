"""Slack transport helpers: input cleaning, channel resolution, and posting.

Kept free of any orchestrator/Claude concerns so both the orchestrator and the
standalone Teams poller reuse the exact same posting behavior.
"""

from __future__ import annotations

import re

from .config import MENTION, SLACK_MAX, TARGET_CHANNEL

# The ChatGPT Slack app appends "*Enviado usando* <@...>" (a bold label + a
# mention) or a plain "enviado usando @ChatGPT"; strip either off incoming text.
_FOOTER_RE = re.compile(
    r"\s*\*?\s*enviado usando\s*\*?\s*(?:<@[A-Z0-9]+>|@?\s*chatgpt)\s*$",
    re.IGNORECASE,
)


def strip_footer(text: str) -> str:
    """Remove a trailing ChatGPT relay footer from an incoming message."""
    return _FOOTER_RE.sub("", text).strip()


async def resolve_channel_id(client, name: str = TARGET_CHANNEL) -> str | None:
    """Return the id of the channel `name` the bot is a member of, or None."""
    resp = await client.users_conversations(types="public_channel", limit=200)
    return next((c["id"] for c in resp["channels"] if c["name"] == name), None)


class Poster:
    """Posts messages to one channel, chunked to Slack's size limit, optionally
    prefixed with the owner mention. Wraps any Slack async web client."""

    def __init__(self, client, channel_id: str) -> None:
        self._client = client
        self._channel_id = channel_id

    async def post(self, text: str, mention: bool = False) -> None:
        body = (f"{MENTION} " if mention else "") + text
        for i in range(0, len(body), SLACK_MAX):
            await self._client.chat_postMessage(
                channel=self._channel_id, text=body[i : i + SLACK_MAX]
            )
