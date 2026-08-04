"""Central configuration: loads .env once and exposes every setting/constant.

Every other module imports from here — there is no per-module .env loading or
duplicated constant. Values come from the environment (with sensible defaults)
so nothing sensitive is hardcoded except the owner's Slack id.
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path


def _load_dotenv() -> None:
    """Load KEY=VALUE lines from the project's .env into os.environ (no deps).
    utf-8-sig tolerates the BOM that PowerShell's `Set-Content -Encoding utf8`
    prepends. Existing env vars win (setdefault)."""
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

# --- Slack ----------------------------------------------------------------- #
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
TARGET_CHANNEL = os.environ.get("SLACK_CHANNEL", "general-personal")
OWNER_USER = "U0BLY0DHJF8"  # mati.ratcliffe — the ONLY user the orchestrator obeys
MENTION = f"<@{OWNER_USER}>"
SLACK_MAX = 4096  # Slack hard-caps a single message at 4096 chars.

# --- Claude session -------------------------------------------------------- #
# The desktop-app-created session the orchestrator drives (so it shows in the
# GUI recents and updates live). Resumed on every start; override via env.
ORCH_SESSION_ID = os.environ.get(
    "ORCH_SESSION_ID", "d0617ad4-028b-49d1-90d0-ac22327d19f1"
)

# Localhost port used as a single-instance lock (bind fails if one is running).
ORCH_LOCK_PORT = int(os.environ.get("ORCH_LOCK_PORT", "47615"))

SYSTEM_PROMPT = (
    "You are an orchestrator that the user drives through a Slack relay. Keep "
    "replies concise and self-contained (they are delivered as chat messages). "
    "Dispatch subagents for substantial work. Ask only when you genuinely need "
    "a decision only the user can make, or when a guarded action needs approval."
)

# --- Guarded actions ------------------------------------------------------- #
# What pauses for Slack approval is defined by `permissions.ask` in settings.json
# (the single source of truth), read + matched in permissions.py — plus a small
# always-on safety floor for `teams write`. Nothing to configure here.

# --- Teams poller ---------------------------------------------------------- #
# Master switch for the background Teams poll loop. Default ON; set to any of
# 0/false/no/off to disable.
TEAMS_POLL_ENABLED = os.environ.get("TEAMS_POLL_ENABLED", "1").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
    "",
)
POLL_TIME_SPAN_MINUTES = int(os.environ.get("POLL_TIME_SPAN_MINUTES", "5"))
TEAMS_CMD = os.environ.get("TEAMS_CMD", "teams")  # `teams` CLI on PATH


def resolve_cwd(argv: list[str] | None = None) -> str:
    """Orchestrator working dir. Precedence: --cwd flag > ORCH_CWD env > ~/Repos."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--cwd", default=None)
    args, _ = parser.parse_known_args(argv)
    base = args.cwd or os.environ.get("ORCH_CWD") or str(Path.home() / "Repos")
    return str(Path(base).expanduser())


def session_kwargs() -> dict:
    """Resume the fixed session if its transcript already exists (persists memory
    across restarts), else create it with that id. Either way it lands in
    ~/.claude/projects/<cwd>/<id>.jsonl so it appears in the desktop GUI recents."""
    proj = re.sub(r"[^A-Za-z0-9]", "-", resolve_cwd())
    path = Path.home() / ".claude" / "projects" / proj / f"{ORCH_SESSION_ID}.jsonl"
    return {"resume": ORCH_SESSION_ID} if path.exists() else {"session_id": ORCH_SESSION_ID}
