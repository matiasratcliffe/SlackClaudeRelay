# slack-agent

A Slack-driven Claude **orchestrator**: a persistent Claude Agent SDK session you
talk to through a Slack relay (from your phone/browser). It runs autonomously,
dispatches its own subagents, and only pauses for you on guarded actions or
clarifying questions — which round-trip to Slack as tagged questions. A
background loop also announces new Microsoft Teams unreads to the same channel.

Uses **Socket Mode** (outbound WebSocket), so it works behind a corporate
firewall with no public URL.

## Module layout

```
slack_agent/
  config.py        loads .env once; all settings + session/cwd resolution
  slack_io.py      channel resolution, chunked Poster, input footer stripping
  interaction.py   QuestionQueue — concurrent-safe [Qn]-tagged operator prompts
  permissions.py   can_use_tool policy: autonomous unless a command is guarded
  teams_poller.py  poll_teams_unreads(post) + standalone one-shot entrypoint
  orchestrator.py  wiring: Claude session + Slack handler + Teams poll loop
```

## Setup (one time, in a browser)

Use a personal free Slack workspace. Create an app at https://api.slack.com/apps
(From scratch), then:

1. **Socket Mode** → enable. **Basic Information → App-Level Tokens** → generate
   one with `connections:write` → copy the `xapp-...` token.
2. **OAuth & Permissions → Bot Token Scopes**: `chat:write`, `channels:read`,
   `channels:history` (add `im:history`/`im:read` if you also want DMs).
3. **Event Subscriptions** → enable → subscribe to bot event `message.channels`.
4. **Install App** → copy the Bot User OAuth Token `xoxb-...`.
5. Invite the bot to your channel: `/invite @<botname>`.

Copy `.env.example` to `.env` and fill in both tokens (the app reads `.env`).

## Run

Orchestrator (main):

```bash
.venv/Scripts/python.exe -m slack_agent.orchestrator
```

Fire a single Teams poll (standalone, for testing):

```bash
.venv/Scripts/python.exe -m slack_agent.teams_poller
```

## How it works

```
Slack msg ─► orchestrator ─► Claude session (dispatches subagents)
   ◄── reply ────────────────┘
   guarded action / clarifying question ─► [Qn] prompt ◄── your tagged reply
Teams unreads ─(every POLL_TIME_SPAN_MINUTES)─► announced to the channel
```

- **Owner lock**: only the configured `OWNER_USER` is obeyed.
- **Autonomous unless guarded**: `permission_mode="default"` + a `can_use_tool`
  policy that allows everything except `config.GUARD_PATTERNS`
  (`git push`, `rm -rf`, `git reset --hard`, `--force`), which ask for approval.
- **Concurrent-safe questions**: each prompt is tagged `[Q1]`, `[Q2]`, …; reply
  `Q1 yes`. A bare reply works when only one is open.
- **Session**: a fixed `ORCH_SESSION_ID` is resumed each start (persistent memory
  + appears in the desktop GUI recents).

Requires the `claude` CLI authenticated, and the `teams` CLI on PATH for polling.
