```markdown
# Pterodactyl Discord Bot — Setup Guide

Prerequisites:
- Python 3.10+
- A Discord bot token with "applications.commands" and bot intents.
- A Pterodactyl Panel Application API Key (permissions to manage users/servers).
- A Discord channel ID to receive admin logs (DM fail logging).

Files provided:
- bot.py
- cogs/servers.py
- cogs/users.py
- cogs/panel.py
- utils/api.py
- utils/embeds.py
- utils/checks.py
- .env.example

Steps:

1. Create a virtual environment and install dependencies:
   - python -m venv .venv
   - source .venv/bin/activate (Windows: .venv\Scripts\activate)
   - pip install -U pip
   - pip install discord.py aiohttp python-dotenv

2. Copy `.env.example` to `.env` and fill the values:
   - DISCORD_TOKEN: your bot token
   - PTERO_APP_API: application API key from Pterodactyl (required)
   - PTERO_PANEL_URL: your panel base url
   - ADMIN_IDS: comma-separated Discord user IDs who are allowed privileged actions
   - ADMIN_LOG_CHANNEL_ID: channel ID for admin logs and DM failure logs

3. Run the bot:
   - python bot.py

4. OAuth & Slash command registration:
   - The bot automatically syncs slash commands on startup.
   - Ensure the bot is invited with applications.commands scope and the necessary guilds/permissions.

Security & Permission System:
- Admin-only commands are guarded with the `ADMIN_IDS` list. Only the IDs in that env var can execute admin-only commands (listed in your requirements).
- All responses to command invokers are ephemeral to avoid leaking sensitive data publicly.
- API keys are read exclusively from environment variables (`PTERO_APP_API`, `PTERO_CLIENT_API`).

DM failure handling:
- For every "server-related action" (create/delete/suspend/unsuspend/resource change/etc.), the bot attempts to DM the target Discord user.
- If sending a DM fails (user closed DMs, blocked bot, etc.), the bot writes a notice to the `ADMIN_LOG_CHANNEL_ID` channel with the action details and the victim user ID so admins can follow up.

Notes & Adaptation:
- Pterodactyl installations can differ in API behavior (some require allocation IDs when creating a server). The provided `utils/api.py` aims to be generic but you may need to adapt the payload for `create_server` to include an allocation ID or startup variables.
- Test commands in a staging environment before running on production.
```
