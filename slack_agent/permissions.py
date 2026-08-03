"""Permission policy for the orchestrator — the Slack transport for Claude's
permission prompts, with settings.json as the single source of truth.

With permission_mode="default", the Claude Code CLI evaluates the settings.json
`permissions` itself: it auto-runs `allow`, auto-blocks `deny`, and calls this
callback for `ask` matches (and anything undecided). The SDK does NOT tell the
callback which rule matched, so we read the `ask`/`deny` patterns from
settings.json ourselves and prompt (via the Slack QuestionQueue) when a call
matches one — allowing everything else, so the agent stays autonomous. There is
no hardcoded guard list; edit settings.json to change what's gated.

The one exception is a tiny SAFETY FLOOR (`teams read`/`teams write`) that is
always gated even if settings.json is missing/unreadable — `write` sends a
message and `read` marks a conversation as seen, both irreversible Teams-state
changes. `AskUserQuestion` elicitations route to the same Slack queue.
Requires permission_mode="default" (NOT bypassPermissions, which shadows this).
"""

from __future__ import annotations

import json
from pathlib import Path

from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

from .config import resolve_cwd

_YES = {"y", "yes", "ok", "approve", "si", "sí", "dale"}

# Always gated even if settings.json is unreadable: `write` sends a message (irreversible)
# and `read` marks a conversation as seen — both change Teams state.
_SAFETY_FLOOR = ("Bash(teams read:*)", "Bash(teams write:*)")


def _settings_paths() -> list[Path]:
    cwd = Path(resolve_cwd())
    return [
        Path.home() / ".claude" / "settings.json",
        cwd / ".claude" / "settings.json",
        cwd / ".claude" / "settings.local.json",
    ]


def _load_rules() -> tuple[list[str], list[str]]:
    """Read permissions.ask / permissions.deny from every settings.json we can find.
    The ask list always includes the safety floor. Never raises."""
    ask: list[str] = list(_SAFETY_FLOOR)
    deny: list[str] = []
    for p in _settings_paths():
        try:
            perms = json.loads(p.read_text(encoding="utf-8-sig")).get("permissions", {})
        except (OSError, ValueError, AttributeError):
            continue
        ask += perms.get("ask", []) or []
        deny += perms.get("deny", []) or []
    return ask, deny


def matches(rule: str, tool_name: str, tool_input: dict) -> bool:
    """True if a Claude-Code permission rule matches this tool call.

      'Tool'             -> whole tool (any input)
      'Tool()' / 'Tool(*)' -> whole tool
      'Tool(prefix:*)'   -> command starts with `prefix`
      'Tool(exact)'      -> command starts with `exact` (specifiers treated as prefixes)

    For Bash/PowerShell rules the COMMAND TEXT is matched regardless of which shell
    tool was actually used, so a gated command can't slip through by switching shells.
    """
    rule = (rule or "").strip()
    if not rule:
        return False
    op = rule.find("(")
    if op == -1:
        return rule == tool_name
    if not rule.endswith(")"):
        return False
    rtool, spec = rule[:op], rule[op + 1 : -1].strip()
    spec = spec[:-2].strip() if spec.endswith(":*") else spec.strip("*").strip()
    if rtool in ("Bash", "PowerShell"):
        if tool_name not in ("Bash", "PowerShell"):
            return False
        if spec == "":
            return True
        return ((tool_input or {}).get("command", "") or "").strip().startswith(spec)
    # Non-shell tools: match by tool name (specifier ignored — conservative).
    return rtool == tool_name


def make_can_use_tool(queue):
    async def can_use_tool(tool_name, input_data, context):
        # Elicitation: the model wants to ask the operator something.
        if tool_name == "AskUserQuestion":
            questions = input_data.get("questions", [])
            answers: dict[str, str] = {}
            for q in questions:
                lines = [f"*{q.get('header', '?')}* — {q.get('question', '')}"]
                opts = q.get("options", [])
                for idx, opt in enumerate(opts, 1):
                    lines.append(
                        f"  {idx}. {opt.get('label', '')} — {opt.get('description', '')}"
                    )
                lines.append("_reply with a number, or free text_")
                reply = (await queue.ask("\n".join(lines))).strip()
                chosen = reply
                if reply.isdigit() and 1 <= int(reply) <= len(opts):
                    chosen = opts[int(reply) - 1].get("label", reply)
                answers[q.get("question", "")] = chosen
            return PermissionResultAllow(
                updated_input={"questions": questions, "answers": answers}
            )

        ask, deny = _load_rules()
        # `deny` is already enforced by the CLI before we're called; re-check as a net.
        if any(matches(r, tool_name, input_data) for r in deny):
            return PermissionResultDeny(message="Denied by settings.json permissions.deny")

        if any(matches(r, tool_name, input_data) for r in ask):
            desc = (
                input_data.get("command")
                if tool_name in ("Bash", "PowerShell")
                else str(input_data)[:300]
            )
            reply = (
                await queue.ask(
                    f":lock: guarded `{tool_name}`\n```{desc}```\napprove? (yes/no)"
                )
            ).strip().lower()
            if reply in _YES:
                return PermissionResultAllow(updated_input=input_data)
            return PermissionResultDeny(message=f"User denied: {reply!r}")

        return PermissionResultAllow(updated_input=input_data)

    return can_use_tool
