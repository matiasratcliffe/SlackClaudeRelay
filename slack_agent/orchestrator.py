"""Slack-driven Claude orchestrator (persistent, streaming, single serial session).

One long-lived Claude Agent SDK session ("the Orchestrator") that you drive from
Slack. It runs autonomously (bypassPermissions) and dispatches its own subagents.
A small guard list (e.g. `git push`) is the ONLY thing that pauses for you: a
PreToolUse hook stamps guarded tool calls as "ask", which routes them into the
async `can_use_tool` callback -> posted to Slack -> the callback blocks until you
reply yes/no. The same callback also handles the model's `AskUserQuestion`
elicitations: the questions are posted to Slack and your reply is fed back.

Design choices (v1):
  * Architecture: persistent streaming `ClaudeSDKClient` (context accrues in-process).
  * Autonomy: permission_mode="bypassPermissions" + guard hook -> Slack approval.
  * Concurrency: single serial session. Your next Slack message while the
    Orchestrator is waiting on you IS treated as your answer.

Run:  .venv/Scripts/python.exe -m slack_agent.orchestrator
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
from pathlib import Path

# Corp TLS interception: trust the Windows cert store for all HTTPS. First.
import truststore

truststore.inject_into_ssl()

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    TextBlock,
)


# --------------------------------------------------------------------------- #
# Config (reuses the same .env as the Slack relay bot).
# --------------------------------------------------------------------------- #
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

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s", level=logging.INFO
)
logger = logging.getLogger("orchestrator")

TARGET_CHANNEL = os.environ.get("SLACK_CHANNEL", "general-personal")
OWNER_USER = "U0BLY0DHJF8"  # mati.ratcliffe — the ONLY user the orchestrator obeys
MENTION = f"<@{OWNER_USER}>"
TELEGRAM_MAX = 4096  # Slack single-message char cap is also 4096.

# The ChatGPT Slack app appends "*Enviado usando* <@...>"; strip it off inputs.
_FOOTER_RE = re.compile(
    r"\s*\*?\s*enviado usando\s*\*?\s*(?:<@[A-Z0-9]+>|@?\s*chatgpt)\s*$",
    re.IGNORECASE,
)

# Guarded Bash commands: the ONLY things that pause for Slack approval.
# Edit this list to widen/narrow what the Orchestrator must ask about.
GUARD_PATTERNS = [
    re.compile(r"\bgit\s+push\b"),
    re.compile(r"\bgit\s+reset\s+--hard\b"),
    re.compile(r"\brm\s+-rf\b"),
    re.compile(r"--force\b|\s-f\b"),
]

SYSTEM_PROMPT = (
    "You are an autonomous orchestrator that the user drives from Slack. Work "
    "end-to-end without asking for confirmation, dispatching subagents for "
    "substantial work. Keep Slack replies concise. Only pause to ask when you "
    "genuinely need a decision only the user can make, or when a guarded action "
    "requires approval."
)


def strip_footer(text: str) -> str:
    return _FOOTER_RE.sub("", text).strip()


def resolve_cwd(argv: list[str] | None = None) -> str:
    """Working dir for the Orchestrator. Precedence: --cwd flag > ORCH_CWD env >
    default ~/Repos."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--cwd", default=None)
    args, _ = parser.parse_known_args(argv)
    base = args.cwd or os.environ.get("ORCH_CWD") or str(Path.home() / "Repos")
    return str(Path(base).expanduser())


def is_guarded(tool_name: str, tool_input: dict) -> bool:
    if tool_name == "Bash":
        cmd = tool_input.get("command", "") or ""
        return any(p.search(cmd) for p in GUARD_PATTERNS)
    return False


# --------------------------------------------------------------------------- #
# Runtime state (single serial session).
# --------------------------------------------------------------------------- #
class State:
    client: ClaudeSDKClient | None = None
    channel_id: str | None = None
    app: AsyncApp | None = None
    query_lock = asyncio.Lock()
    pending: asyncio.Future | None = None  # set while awaiting a Slack reply


S = State()


async def post(text: str, mention: bool = False) -> None:
    """Post a message to the target channel, chunked to Slack's limit."""
    prefix = f"{MENTION} " if mention else ""
    body = prefix + text
    for i in range(0, len(body), TELEGRAM_MAX):
        await S.app.client.chat_postMessage(
            channel=S.channel_id, text=body[i : i + TELEGRAM_MAX]
        )


async def ask_user(prompt_text: str) -> str:
    """Post a question/approval to Slack and block until the user replies."""
    loop = asyncio.get_running_loop()
    S.pending = loop.create_future()
    await post(prompt_text, mention=True)
    try:
        return await S.pending
    finally:
        S.pending = None


# --------------------------------------------------------------------------- #
# Permission + elicitation callback (the interactive rail).
# --------------------------------------------------------------------------- #
async def can_use_tool(tool_name, input_data, context):
    # Elicitation: the model wants to ask the user something.
    if tool_name == "AskUserQuestion":
        questions = input_data.get("questions", [])
        answers: dict[str, str] = {}
        for q in questions:
            lines = [f"*{q.get('header','?')}* — {q.get('question','')}"]
            opts = q.get("options", [])
            for idx, opt in enumerate(opts, 1):
                lines.append(f"  {idx}. {opt.get('label','')} — {opt.get('description','')}")
            lines.append("_reply with a number, or free text_")
            reply = (await ask_user("\n".join(lines))).strip()
            chosen = reply
            if reply.isdigit() and 1 <= int(reply) <= len(opts):
                chosen = opts[int(reply) - 1].get("label", reply)
            answers[q.get("question", "")] = chosen
        return PermissionResultAllow(
            updated_input={"questions": questions, "answers": answers}
        )

    # Autonomous by default: allow anything not on the guard list.
    if not is_guarded(tool_name, input_data):
        return PermissionResultAllow(updated_input=input_data)

    # Guarded action: ask for yes/no approval.
    desc = input_data.get("command") if tool_name == "Bash" else str(input_data)
    reply = (await ask_user(f":lock: Approve `{tool_name}`: `{desc}` ?  (yes/no)")).strip().lower()
    if reply in ("y", "yes", "ok", "approve", "si", "sí", "dale"):
        return PermissionResultAllow(updated_input=input_data)
    return PermissionResultDeny(message=f"User denied: {reply!r}")


# --------------------------------------------------------------------------- #
# Query processing.
# --------------------------------------------------------------------------- #
async def handle_query(text: str) -> None:
    async with S.query_lock:
        await post("🧠 …", mention=False)
        await S.client.query(text)
        parts: list[str] = []
        async for msg in S.client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock) and block.text.strip():
                        parts.append(block.text)
            elif isinstance(msg, ResultMessage):
                break
        answer = "\n\n".join(parts).strip() or "[no text output]"
        await post(answer, mention=True)


# --------------------------------------------------------------------------- #
# Slack wiring.
# --------------------------------------------------------------------------- #
async def on_message(event, logger):
    if event.get("bot_id") or event.get("subtype"):
        return
    if event.get("channel") != S.channel_id:
        return
    # Hardcoded safeguard: obey only the owner (mati.ratcliffe).
    if event.get("user") != OWNER_USER:
        return

    text = strip_footer((event.get("text") or "").strip())
    if not text:
        return

    # If the Orchestrator is waiting on us, this message is the answer.
    if S.pending is not None and not S.pending.done():
        S.pending.set_result(text)
        return

    logger.info("query from %s: %s", user, text[:120])
    asyncio.create_task(handle_query(text))


async def main() -> None:
    bot_token = os.environ.get("SLACK_BOT_TOKEN")
    app_token = os.environ.get("SLACK_APP_TOKEN")
    if not bot_token or not app_token:
        raise SystemExit("Set SLACK_BOT_TOKEN and SLACK_APP_TOKEN (see .env.example).")

    S.app = AsyncApp(token=bot_token)
    S.app.event("message")(on_message)

    # Resolve target channel -> id (bot must be a member).
    resp = await S.app.client.users_conversations(types="public_channel", limit=200)
    for ch in resp["channels"]:
        if ch["name"] == TARGET_CHANNEL:
            S.channel_id = ch["id"]
            break
    if not S.channel_id:
        raise SystemExit(f"Channel '{TARGET_CHANNEL}' not found among bot's channels.")

    options = ClaudeAgentOptions(
        # Full Claude Code system prompt + our orchestrator note appended.
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
            "append": SYSTEM_PROMPT,
        },
        # Inherit ALL of the user's ~/.claude context: settings, hooks,
        # CLAUDE.md, permissions, plus project/local for the working repo.
        setting_sources=["user", "project", "local"],
        skills="all",
        # "default" (NOT bypassPermissions) so can_use_tool is actually consulted
        # for every tool call. The callback auto-allows everything except the
        # guarded few, which it routes to Slack for approval. bypassPermissions
        # would shadow the callback entirely (SDK warns about this).
        permission_mode="default",
        can_use_tool=can_use_tool,
        cwd=resolve_cwd(),
    )
    logger.info("Orchestrator working dir: %s", options.cwd)

    logger.info("Orchestrator connecting Claude session…")
    async with ClaudeSDKClient(options=options) as client:
        S.client = client
        handler = AsyncSocketModeHandler(S.app, app_token)
        logger.info("Listening on #%s (%s)", TARGET_CHANNEL, S.channel_id)
        await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
