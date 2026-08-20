"""Autonomous research bot: pick a fresh trending topic, hold a self-guided walkthrough discussion
with Claude, then compile a one-page markdown "what we've learned" report into scratchpad.

Flow:
  1. `trending_topic.pick_new_topic` selects a topic not yet explored.
  2. A discussion runs for a random 5-10 turns. The opening prompt makes Claude teach the topic in
     depth and END EVERY answer with follow-up questions, so its own suggestions drive each next
     turn. The final discussion turn answers every still-open question so nothing is left dangling.
  3. One last prompt compiles the whole discussion into a concise one-page report; the script writes
     it to a NEW file in the output dir.

Guardrails: the model gets **web read only** (WebSearch/WebFetch) — no shell, no file writes, no
edits. The script itself writes the report (a new file) plus a `<name>-transcript.md` sibling
holding the full conversation (every prompt + response).

Reports + the explored-topics list live in `<repo>/research_output/` (override the whole dir with
RESEARCH_DATA_DIR, or just the report dir with RESEARCH_OUT_DIR).
Config (env): RESEARCH_MIN_WAIT / RESEARCH_MAX_WAIT seconds
(default 60/900), RESEARCH_TURNS (override the random turn count), RESEARCH_INSTANT=1 (no waits).
RESEARCH_TOPIC forces a specific topic (skips the auto-picker); RESEARCH_SEED adds your own framing
to anchor the discussion. `--instant` also sets instant. Requires claude-agent-sdk and a logged-in
Claude Code.
"""

import asyncio
import os
import random
import re
import sys
import time
from pathlib import Path

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    PermissionResultAllow,
    PermissionResultDeny,
)

from claude_next_prompt import ask_full
from trending_topic import DATA_DIR, pick_new_topic

# Modest extended-thinking budget — enough to reason, not so much it dominates token cost.
os.environ["MAX_THINKING_TOKENS"] = "6000"

# Reports are written here (alongside the explored-topics list); override with RESEARCH_OUT_DIR.
OUT_DIR = Path(os.environ.get("RESEARCH_OUT_DIR") or DATA_DIR)
WEB_TOOLS = ("WebSearch", "WebFetch")


async def _web_only(tool_name, tool_input, context):
    """Permission gate: allow web reads, deny everything else (no shell, writes, or edits)."""
    if tool_name in WEB_TOOLS:
        return PermissionResultAllow()
    return PermissionResultDeny(message="research bot is read-only over the web")


def _options():
    return ClaudeAgentOptions(
        model="claude-sonnet-5",     # hardcoded — cheaper than Opus for these runs
        system_prompt={"type": "preset", "preset": "claude_code",
                       "append": "Aim for clear, accurate, well-organised answers. Be substantive "
                                 "but concise — cover what matters without padding."},
        setting_sources=["user"],
        permission_mode="default",   # so every tool call falls through to the gate below
        can_use_tool=_web_only,      # sole gate: allow web reads, deny everything else
    )


def opening_prompt(topic, seed=None):
    base = (
        f"Let's do a guided walkthrough to help me learn about: **{topic}**.\n\n"
        "Teach it as an evolving discussion, not a dump. Be substantive and clear, but keep each "
        "answer focused and reasonably concise — a few tight paragraphs, not an essay. Cover the "
        "important ideas well rather than exhaustively.\n\n"
        "Crucial: END EVERY answer with one or more concrete follow-up questions of the form "
        "\"Would you like to know more about X, Y, or Z?\" — chosen to open the most valuable next "
        "threads — so we flow naturally into the next part of the discussion.\n\n"
    )
    if seed:
        base += (
            "Here is specifically what I have in mind — anchor the whole walkthrough to THIS framing: "
            "engage with it critically, pressure-test it, fill in the theory and prior art, and push "
            "it further, rather than teaching the generic textbook version:\n\n"
            f"{seed}\n\n"
        )
    return base + f"Start now with a solid foundation on {topic}."


CONTINUE_PROMPT = (
    "Continue the walkthrough: pick the single most valuable follow-up from the ones you just "
    "offered and explore it clearly and substantively, but stay focused and concise. Then, as "
    "before, END with new \"Would you like to know more about …?\" follow-up questions."
)

WRAP_UP_PROMPT = (
    "This is the final discussion turn. Now go back and thoroughly answer ALL the follow-up "
    "questions still left open anywhere in our conversation — leave nothing unexplored or dangling. "
    "Cover each remaining thread in depth. You can stop offering new follow-ups now; this closes "
    "out the exploration."
)


def report_prompt(topic):
    return (
        f"Now write a brief **one-page** standalone markdown report on **{topic}**.\n\n"
        "Critical: it must be **fully self-contained** — a reader who never saw this discussion, and "
        "who knows nothing about the topic, should read it top-to-bottom and come away with the "
        "gist. So:\n"
        "- Open by saying plainly what the topic IS and why it matters (no assumed background).\n"
        "- Define every term or acronym the first time it appears; don't drop jargon undefined.\n"
        "- Do NOT reference \"our discussion\", \"we\", \"as mentioned\", or the follow-up questions — "
        "the reader has no access to any of that. Write it as an original explainer, not a recap.\n"
        "- Structure it for a cold reader: what it is → why it matters → the key ideas/findings → "
        "the takeaways. Prefer clear full sentences over telegraphic notes.\n"
        "Keep it to one page: cover the important things well, drop the rest. Output ONLY the markdown."
    )


def _wait_seconds(instant):
    if instant:
        return 0.0
    lo = float(os.environ.get("RESEARCH_MIN_WAIT", "60"))
    hi = float(os.environ.get("RESEARCH_MAX_WAIT", "900"))
    return random.uniform(lo, hi)


def _report_path(topic):
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:50] or "topic"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUT_DIR / f"research_{slug}_{int(time.time())}.md"


class Meter:
    """Accumulates run metrics from each turn's ResultMessage (usage/cost) + model id."""

    def __init__(self):
        self.calls = 0
        self.questions = 0
        self.inp = 0
        self.out = 0
        self.cost = 0.0
        self.model = None

    def record(self, result, model):
        self.calls += 1
        if model:
            self.model = model
        usage = getattr(result, "usage", None) or {}
        self.inp += usage.get("input_tokens", 0) or 0
        self.out += usage.get("output_tokens", 0) or 0
        cost = getattr(result, "total_cost_usd", None)
        if cost:
            self.cost += cost


def _fmt_elapsed(elapsed_s):
    """Human elapsed as d/h/m/s, dropping leading zero units (e.g. '3h 18m 52s')."""
    s = int(elapsed_s)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    parts = [(d, "d"), (h, "h"), (m, "m"), (s, "s")]
    while len(parts) > 1 and parts[0][0] == 0:  # trim leading zero units, keep seconds
        parts.pop(0)
    return " ".join(f"{v}{u}" for v, u in parts)


def _transcript_md(topic, turns):
    """Render the full conversation (every prompt + response) as standalone markdown."""
    parts = [f"# Research transcript — {topic}", "",
             f"_Full conversation, generated {time.strftime('%Y-%m-%d %H:%M:%S')}._", "", "---", ""]
    for i, (label, prompt, answer) in enumerate(turns, 1):
        parts += [f"## {i}. {label}", "", "**Prompt**", ""]
        parts.append("\n".join((f"> {ln}" if ln else ">") for ln in prompt.splitlines()))
        parts += ["", "**Response**", "", answer, "", "---", ""]
    return "\n".join(parts)


def _header(topic, meter, elapsed_s):
    """Build the script-computed metadata header (prepended AFTER generation, so the model never
    sees it — it's added deterministically, not by Claude)."""
    total = meter.inp + meter.out
    return "\n".join([
        "## Run metadata",
        f"- **Topic:** {topic}",
        f"- **Model:** {meter.model or 'unknown'}",
        f"- **Questions asked:** {meter.questions}",
        f"- **Total model calls:** {meter.calls}",
        f"- **Elapsed:** {_fmt_elapsed(elapsed_s)}",
        f"- **Tokens:** {meter.inp:,} in / {meter.out:,} out ({total:,} total)",
        f"- **Est. cost (approx):** ${meter.cost:.4f}",
        f"- **Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "---",
        "",
    ])


async def main():
    instant = "--instant" in sys.argv or os.environ.get("RESEARCH_INSTANT") == "1"
    turns = int(os.environ["RESEARCH_TURNS"]) if os.environ.get("RESEARCH_TURNS") else random.randint(5, 10)
    turns = max(3, turns)  # need opening + >=1 continue + wrap-up

    started = time.time()
    meter = Meter()

    seed = os.environ.get("RESEARCH_SEED") or None
    topic = os.environ.get("RESEARCH_TOPIC") or None
    if not topic:  # no override → auto-pick a fresh trending topic
        async with ClaudeSDKClient(options=_options()) as picker:
            topic = await pick_new_topic(picker, record=meter.record)
    if not topic:
        print("No fresh topic to research — all trending topics already explored.")
        return
    print(f"Researching: {topic}  ({turns} turns)\n")

    convo = []  # (label, prompt, answer) for every turn — dumped to the -transcript.md sibling

    async def q(chat, prompt, label, count=True):
        text, result, model = await ask_full(chat, prompt)
        meter.record(result, model)
        if count:
            meter.questions += 1
        convo.append((label, prompt, text))
        return text

    async with ClaudeSDKClient(options=_options()) as chat:
        await q(chat, opening_prompt(topic, seed), "Turn 1 — opening")   # turn 1
        for i in range(2, turns):                                     # turns 2..N-1
            await asyncio.sleep(_wait_seconds(instant))
            await q(chat, CONTINUE_PROMPT, f"Turn {i} — continue")
            print(f"  ...turn {i}/{turns}")
        await asyncio.sleep(_wait_seconds(instant))
        await q(chat, WRAP_UP_PROMPT, f"Turn {turns} — wrap-up")      # turn N: answer open questions
        report = await q(chat, report_prompt(topic), "Report compilation", count=False)  # not a Q

    # Metadata header is built and prepended HERE, after generation — the model never sees it.
    path = _report_path(topic)
    path.write_text(_header(topic, meter, time.time() - started) + report, encoding="utf-8")
    transcript_path = path.with_name(f"{path.stem}-transcript{path.suffix}")
    transcript_path.write_text(_transcript_md(topic, convo), encoding="utf-8")
    print(f"\nReport written: {path}\nTranscript written: {transcript_path}")


if __name__ == "__main__":
    asyncio.run(main())
