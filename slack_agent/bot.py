"""Minimal Slack -> Claude Code QnA bot (Socket Mode).

You DM the bot in Slack (from phone/browser). The bot runs here, connects to
Slack over an outbound WebSocket (Socket Mode) -- no inbound/public URL needed,
which is what makes it work behind the corp firewall. It runs Claude Code
headless (`claude -p "<message>"`) and replies in the DM.

Currently in DUMMY MODE: replies with the message uppercased. The real Claude
path is present but commented out.

Restriction: set SLACK_ALLOWED_USERS to a comma-separated list of Slack user
IDs (e.g. U0123ABC) to lock the bot to only those users. Empty = allow anyone
who can DM it.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import ssl
import subprocess
from pathlib import Path


def _load_dotenv() -> None:
    """Minimal .env loader (no dependency). KEY=VALUE lines, # comments."""
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

# Corp networks do TLS interception; make ALL ssl (slack_sdk http + the Socket
# Mode websocket) trust the Windows cert store, which has the corp CA. Must run
# before any TLS connection is opened.
import truststore

truststore.inject_into_ssl()

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("slack_agent")

# `claude` resolves to claude.cmd on Windows via PATHEXT; override with CLAUDE_BIN.
CLAUDE_BIN = os.environ.get("CLAUDE_BIN") or shutil.which("claude") or "claude"
CLAUDE_TIMEOUT = int(os.environ.get("CLAUDE_TIMEOUT", "180"))
# Optional allow-list of Slack user IDs.
ALLOWED_USERS = {
    u.strip() for u in os.environ.get("SLACK_ALLOWED_USERS", "").split(",") if u.strip()
}
# Channel to listen in (by name, no leading #). Resolved to an ID at startup.
TARGET_CHANNEL = os.environ.get("SLACK_CHANNEL", "general-personal")
TARGET_CHANNEL_ID: str | None = None
# Hardcoded mention prepended to every reply (@mati.ratcliffe).
MENTION = "<@U0BLY0DHJF8>"
# Trailing footer the ChatGPT Slack app appends, e.g. "*Enviado usando* <@U0BM445DV7E>"
# (a bold label + a mention of the ChatGPT app), or a plain "enviado usando @ChatGPT".
_FOOTER_RE = re.compile(
    r"\s*\*?\s*enviado usando\s*\*?\s*(?:<@[A-Z0-9]+>|@?\s*chatgpt)\s*$",
    re.IGNORECASE,
)


def strip_footer(text: str) -> str:
    return _FOOTER_RE.sub("", text).strip()


def ask_claude(prompt: str) -> str:
    """DUMMY MODE: echo the message uppercased. Short-lived live test only."""
    print(f"\n>>> Slack: {prompt}")
    return prompt.upper()

    # --- Real Claude mode (disabled for dummy test) ---
    # try:
    #     proc = subprocess.run(
    #         [CLAUDE_BIN, "-p", prompt, "--output-format", "text"],
    #         capture_output=True,
    #         text=True,
    #         timeout=CLAUDE_TIMEOUT,
    #     )
    # except subprocess.TimeoutExpired:
    #     return f"[timeout after {CLAUDE_TIMEOUT}s]"
    #
    # if proc.returncode != 0:
    #     err = (proc.stderr or "").strip()
    #     logger.error("claude exit %s: %s", proc.returncode, err)
    #     return f"[claude error {proc.returncode}] {err[:500]}"
    #
    # return (proc.stdout or "").strip() or "[empty response]"


app = App(token=os.environ.get("SLACK_BOT_TOKEN"))


@app.event("message")
def on_message(event, say, logger):
    # Ignore bot echoes, edits, joins, etc.
    if event.get("bot_id") or event.get("subtype"):
        return
    # Only handle messages in the target channel.
    if TARGET_CHANNEL_ID is None or event.get("channel") != TARGET_CHANNEL_ID:
        return

    user = event.get("user")
    if ALLOWED_USERS and user not in ALLOWED_USERS:
        logger.info("blocked user %s", user)
        say("Not authorized.")
        return

    prompt = strip_footer((event.get("text") or "").strip())
    if not prompt:
        return

    logger.info("query from %s: %s", user, prompt[:120])
    say(f"{MENTION} {ask_claude(prompt)}")


def main() -> None:
    bot_token = os.environ.get("SLACK_BOT_TOKEN")
    app_token = os.environ.get("SLACK_APP_TOKEN")
    if not bot_token or not app_token:
        raise SystemExit(
            "Set SLACK_BOT_TOKEN (xoxb-...) and SLACK_APP_TOKEN (xapp-...). "
            "See .env.example."
        )

    # Resolve the target channel name -> ID (bot must be a member of it).
    global TARGET_CHANNEL_ID
    for page in app.client.users_conversations(types="public_channel", limit=200):
        for ch in page["channels"]:
            if ch["name"] == TARGET_CHANNEL:
                TARGET_CHANNEL_ID = ch["id"]
                break
        if TARGET_CHANNEL_ID:
            break
    if not TARGET_CHANNEL_ID:
        raise SystemExit(
            f"Channel '{TARGET_CHANNEL}' not found among the bot's channels. "
            f"Invite the bot: in Slack, '/invite @<botname>' in #{TARGET_CHANNEL}."
        )

    logger.info(
        "Bot starting (claude bin: %s, channel: #%s = %s)",
        CLAUDE_BIN,
        TARGET_CHANNEL,
        TARGET_CHANNEL_ID,
    )
    SocketModeHandler(app, app_token).start()


if __name__ == "__main__":
    main()
