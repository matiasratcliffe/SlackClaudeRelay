"""Permission policy for the orchestrator's Claude session.

Autonomous by default: every tool call is allowed except guarded shell commands
(see config.GUARD_PATTERNS), which are routed to the operator via the question
queue for a yes/no. The model's `AskUserQuestion` elicitations are also surfaced
through the same queue and the operator's choice is fed back.

`make_can_use_tool(queue)` builds the SDK `can_use_tool` callback bound to a
QuestionQueue. Requires permission_mode="default" (NOT bypassPermissions, which
would shadow the callback entirely).
"""

from __future__ import annotations

from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

from .config import GUARD_PATTERNS

_YES = {"y", "yes", "ok", "approve", "si", "sí", "dale"}


def is_guarded(tool_name: str, tool_input: dict) -> bool:
    """True if this is a shell command (Bash or PowerShell) matching a guard."""
    if tool_name in ("Bash", "PowerShell"):
        cmd = (tool_input or {}).get("command", "") or ""
        return any(p.search(cmd) for p in GUARD_PATTERNS)
    return False


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

        # Autonomous by default: allow anything not on the guard list.
        if not is_guarded(tool_name, input_data):
            return PermissionResultAllow(updated_input=input_data)

        # Guarded action: ask for approval, with the actual command as context.
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

    return can_use_tool
