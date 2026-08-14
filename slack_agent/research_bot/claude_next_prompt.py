"""Run one prompt through Claude, print the answer, then a suggested next prompt.

Uses the Claude Agent SDK (like the orchestrator): it inherits your ~/.claude auth/context, so
no API key. The suggestion reuses the same session, so it has the exchange as context.

Requires: pip install claude-agent-sdk   (and a logged-in Claude Code, i.e. run `claude` once).

Usage:
    python claude_next_prompt.py "your prompt"
    echo "your prompt" | python claude_next_prompt.py
"""

import asyncio
import sys

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
)

SUGGEST = ("Based on our exchange so far, suggest the single most useful next prompt I could send "
           "you to continue. Output only the suggested prompt text — no preamble, no quotes.")


async def ask_full(client, prompt):
    """Send `prompt`; return (text, result, model). `result` is the ResultMessage carrying the
    turn's usage/cost; `model` is the responding model id."""
    await client.query(prompt)
    parts, result, model = [], None, None
    async for msg in client.receive_response():
        if isinstance(msg, AssistantMessage):
            parts += [b.text for b in msg.content if isinstance(b, TextBlock)]
            model = getattr(msg, "model", None) or model
        elif isinstance(msg, ResultMessage):
            result = msg
    return "".join(parts).strip(), result, model


async def ask(client, prompt):
    """Send `prompt` and return the assistant's text for that response."""
    text, _, _ = await ask_full(client, prompt)
    return text


async def main():
    prompt = " ".join(sys.argv[1:]).strip() or sys.stdin.read().strip()
    if not prompt:
        sys.exit('usage: claude_next_prompt.py "<prompt>"  (or pipe the prompt on stdin)')
    options = ClaudeAgentOptions(setting_sources=["user"], permission_mode="bypassPermissions")
    async with ClaudeSDKClient(options=options) as client:
        print(await ask(client, prompt))
        print("\n--- suggested next prompt ---\n" + await ask(client, SUGGEST))


if __name__ == "__main__":
    asyncio.run(main())
