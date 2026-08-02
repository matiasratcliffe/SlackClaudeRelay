"""Register the orchestrator's headless session in the Claude desktop app's
'recents' list.

The desktop app builds recents from local_*.json index files under
%APPDATA%\\Claude\\claude-code-sessions\\<workspace>\\<sub>\\ , each linking to a
CLI transcript via `cliSessionId`. The orchestrator is spawned by the headless
Agent SDK, so it has a transcript but no index entry -> it never appears.

This writes one index entry pointing at the orchestrator transcript, titled
"Orchestrator", with cwd = ~/Repos (unchanged working dir). Restart the desktop
app afterward to see it. Reversible: just delete the file it prints.

Run:  .venv/Scripts/python.exe tools/register_orchestrator_recent.py
"""

import glob
import json
import os
import time
import uuid

CLI_SESSION_ID = "0c1e5d2a-0b17-4e57-9a11-0c1e5d2a0b17"  # orchestrator transcript
CWD = r"C:\Users\maratcli\Repos"
TITLE = "Orchestrator"

store_root = os.path.join(
    os.environ["APPDATA"], "Claude", "claude-code-sessions"
)
# Find the dir that already holds the local_*.json entries (the app's workspace).
candidates = glob.glob(os.path.join(store_root, "*", "*"))
target_dir = None
for d in candidates:
    if os.path.isdir(d) and glob.glob(os.path.join(d, "local_*.json")):
        target_dir = d
        break
if not target_dir:
    raise SystemExit(f"Could not find a local_*.json store under {store_root}")

now = int(time.time() * 1000)
sid = f"local_{uuid.uuid4()}"
entry = {
    "sessionId": sid,
    "cliSessionId": CLI_SESSION_ID,
    "cwd": CWD,
    "originCwd": CWD,
    "lastFocusedAt": now,
    "createdAt": now,
    "lastActivityAt": now,
    "model": "claude-opus-4-8",
    "effort": "high",
    "isArchived": False,
    "title": TITLE,
    "titleSource": "user",
    "permissionMode": "auto",
    "remoteMcpServersConfig": [],
    "chromePermissionMode": "skip_all_permission_checks",
    "completedTurns": 0,
    "alwaysAllowedReasons": [],
    "sessionPermissionUpdates": [],
    "classifierSummaryEnabled": True,
    "reportFindingsCard": True,
    "spawnSeed": {},
}
path = os.path.join(target_dir, sid + ".json")
with open(path, "w", encoding="utf-8") as f:
    json.dump(entry, f, indent=2)

print("Registered recents entry:")
print("  ", path)
print("  title:", TITLE, "-> cliSessionId:", CLI_SESSION_ID)
print("Restart the Claude desktop app to see it. Delete that file to undo.")
