contents=
# bot.py
import os
import asyncio
import logging
from typing import Optional

import aiohttp
import discord
from discord.ext import commands
from discord import app_commands

from utils.api import PteroAPI
from utils.checks import admin_check
from utils.embeds import EmbedFactory

# Cogs
from cogs.servers import ServersCog
from cogs.users import UsersCog
from cogs.panel import PanelCog

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pterobot")

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
PTERO_PANEL_URL = os.environ.get("PTERO_PANEL_URL", "https://panel.example.com")
ADMIN_IDS = [int(x.strip()) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
ADMIN_LOG_CHANNEL_ID = int(os.environ.get("ADMIN_LOG_CHANNEL_ID", "0"))

if not DISCORD_TOKEN:
    logger.error("DISCORD_TOKEN not set in environment.")
    raise SystemExit(1)

intents = discord.Intents.default()
intents.members = True  # needed to DM members and see mentions

class PteroBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="/",
            intents=intents,
            application_id=None,  # let discord.py infer
            help_command=None
        )
        self.session: Optional[aiohttp.ClientSession] = None
        self.ptero: Optional[PteroAPI] = None
        self.embed = EmbedFactory()
        self.admin_ids = set(ADMIN_IDS)
        self.admin_log_channel_id = ADMIN_LOG_CHANNEL_ID

    async def setup_hook(self):
        # create shared aiohttp session and Pterodactyl API helper
        self.session = aiohttp.ClientSession()
        self.ptero = PteroAPI(self.session)

        # register cogs
        await self.add_cog(ServersCog(self))
        await self.add_cog(UsersCog(self))
        await self.add_cog(PanelCog(self))

        # sync commands
        logger.info("Syncing application commands...")
        await self.tree.sync()

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} ({self.user.id})")
        logger.info(f"Admin IDs: {sorted(self.admin_ids)}")

    async def close(self):
        if self.session:
            await self.session.close()
        await super().close()

bot = PteroBot()

# Run bot
if __name__ == "__main__":
    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
