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
    # Only handle plain user DMs; ignore bot echoes, edits, joins, etc.
    if event.get("channel_type") != "im":
        return
    if event.get("bot_id") or event.get("subtype"):
        return

    user = event.get("user")
    if ALLOWED_USERS and user not in ALLOWED_USERS:
        logger.info("blocked user %s", user)
        say("Not authorized.")
        return

    prompt = (event.get("text") or "").strip()
    if not prompt:
        return

    logger.info("query from %s: %s", user, prompt[:120])
    say(ask_claude(prompt))


def main() -> None:
    bot_token = os.environ.get("SLACK_BOT_TOKEN")
    app_token = os.environ.get("SLACK_APP_TOKEN")
    if not bot_token or not app_token:
        raise SystemExit(
            "Set SLACK_BOT_TOKEN (xoxb-...) and SLACK_APP_TOKEN (xapp-...). "
            "See .env.example."
        )

    logger.info("Bot starting (claude bin: %s)", CLAUDE_BIN)
    SocketModeHandler(app, app_token).start()


if __name__ == "__main__":
    main()
