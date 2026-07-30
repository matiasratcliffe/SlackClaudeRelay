# slack-agent

Minimal Slack bot that relays your DMs to Claude Code (`claude -p`) and replies.
Uses **Socket Mode** (outbound WebSocket) so it works behind a corp firewall with
no public URL. Currently in **dummy mode**: echoes your message uppercased.

You chat from Slack on your phone/browser — nothing but the Python lib runs here.

## One-time Slack app setup (in a browser)

Use a **personal free workspace** (slack.com/create) to avoid corp admin gates.

1. Go to https://api.slack.com/apps -> **Create New App** -> **From scratch**.
   Pick a name + your workspace.
2. **Socket Mode** (left nav) -> toggle **Enable Socket Mode** on. It prompts to
   create an **App-Level Token** with `connections:write` -> create it, copy the
   `xapp-...` token = `SLACK_APP_TOKEN`.
3. **OAuth & Permissions** -> **Bot Token Scopes** -> add: `chat:write`,
   `im:history`, `im:read`.
4. **Event Subscriptions** -> toggle **Enable Events** on -> **Subscribe to bot
   events** -> add `message.im` -> Save.
5. **App Home** -> Show Tabs -> enable **Messages Tab**, and check
   "Allow users to send Slash commands and messages from the messages tab".
6. **Install App** (left nav) -> Install to workspace -> copy the
   **Bot User OAuth Token** `xoxb-...` = `SLACK_BOT_TOKEN`.

## Configure

Copy `.env.example` to `.env` and fill in both tokens. (The bot reads env vars,
not `.env` directly -- export them, or set inline when running.)

## Run

```bash
.venv/Scripts/python.exe -m slack_agent.bot
```

Then in Slack, open a DM with your bot (find it under Apps) and send a message.

## How it works

```
Slack DM -> Socket Mode WS -> bot.py -> claude -p (dummy: uppercase) -> reply
```

Requires the `claude` CLI on PATH and authenticated (for real mode). Override
with `CLAUDE_BIN` / `CLAUDE_TIMEOUT`. Restrict access with `SLACK_ALLOWED_USERS`.
