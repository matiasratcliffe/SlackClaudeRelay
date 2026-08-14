"""Pick a fresh trending AI/tech topic from newsletters, avoiding already-explored ones.

Two Claude calls (Agent SDK, inherits ~/.claude — no API key):
  1. gather 5-10 topics trending right now across popular AI/tech newsletters (web tools).
  2. pick one at random that isn't already in the explored-topics file — a semantic match, so the
     same topic worded differently still counts as explored — or NONE if all are covered.
The pick is appended to the file (one topic per line).

Importable: `pick_new_topic(client)` runs both calls against an existing SDK client and returns the
chosen topic (or None). Requires claude-agent-sdk and a logged-in Claude Code.

Usage:  python trending_topic.py [explored_file]
"""

import asyncio
import os
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from claude_next_prompt import ask_full

# Runtime data (the explored-topics list + reports) lives outside the code, in the repo's
# research_output/ scratch dir; override with RESEARCH_DATA_DIR.
DATA_DIR = Path(os.environ.get("RESEARCH_DATA_DIR") or Path(__file__).resolve().parents[2] / "research_output")

NEWSLETTERS = [
    "TLDR AI — https://tldr.tech/ai",
    "The Rundown AI — https://www.therundown.ai/",
    "Ben's Bites — https://bensbites.com/",
    "The Batch (DeepLearning.AI) — https://www.deeplearning.ai/the-batch/",
    "Import AI — https://importai.substack.com/archive",
]
EXPLORED = Path(sys.argv[1]) if len(sys.argv) > 1 else DATA_DIR / "explored_topics.txt"

GATHER = (
    "Look at these current AI/tech newsletters and their latest issues:\n"
    + "\n".join(NEWSLETTERS)
    + "\n\nUsing web search/fetch, collect the 5-10 topics trending RIGHT NOW across them — each a "
    "short noun phrase. Output the list wrapped exactly between a line `BEGIN_TOPICS` and a line "
    "`END_TOPICS`, one topic per line inside, and nothing else inside those markers."
)


def _pick_prompt(explored, trending):
    return (
        "From this list of trending topics:\n" + trending
        + "\n\nPick ONE at random that is NOT already in my explored list below. Treat topics as the "
        "same even when worded differently (semantic match, not literal string match). If every "
        "trending topic is already explored, output exactly NONE.\n\nExplored:\n"
        + (explored or "(none yet)")
        + "\n\nOutput ONLY the chosen topic on a single line (a short noun phrase), or NONE."
    )


def _between(text, start, end):
    if start in text and end in text.split(start, 1)[1]:
        return text.split(start, 1)[1].split(end, 1)[0].strip()
    return text.strip()


def _last_line(text):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


async def pick_new_topic(client, explored_path=EXPLORED, record=None):
    """Gather trending topics, pick one not yet explored, append it, and return it (or None).

    record: optional callable(result, model) invoked per Claude call, for usage/metrics accounting."""
    def _ask(prompt):
        async def run():
            text, result, model = await ask_full(client, prompt)
            if record:
                record(result, model)
            return text
        return run()

    explored = explored_path.read_text(encoding="utf-8").strip() if explored_path.exists() else ""
    trending = _between(await _ask(GATHER), "BEGIN_TOPICS", "END_TOPICS")
    print("Trending topics:\n" + trending + "\n")
    pick = _last_line(await _ask(_pick_prompt(explored, trending)))
    if not pick or pick.upper() == "NONE":
        return None
    with explored_path.open("a", encoding="utf-8") as fh:
        fh.write(pick + "\n")
    return pick


async def main():
    options = ClaudeAgentOptions(
        setting_sources=["user"],
        permission_mode="bypassPermissions",
        allowed_tools=["WebSearch", "WebFetch"],
    )
    async with ClaudeSDKClient(options=options) as client:
        topic = await pick_new_topic(client)
    if topic:
        print(f"Picked (appended to {EXPLORED.name}): {topic}")
    else:
        print("No new topic — all trending topics are already explored.")


if __name__ == "__main__":
    asyncio.run(main())
