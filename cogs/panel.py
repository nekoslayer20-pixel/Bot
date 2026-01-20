# cogs/panel.py
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.api import PteroAPI, PteroError
from utils.embeds import EmbedFactory
from utils.checks import admin_check

logger = logging.getLogger("pterobot.panel")

class PanelCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ptero: PteroAPI = bot.ptero
        self.embed = bot.embed
        self.admin_log_channel_id = bot.admin_log_channel_id

    @app_commands.command(name="nodes", description="List panel nodes")
    @admin_check()
    async def nodes(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            nodes = await self.ptero.list_nodes()
        except PteroError as e:
            return await interaction.followup.send(embed=self.embed.error(f"Failed to list nodes: {e}"), ephemeral=True)
        embed = self.embed.info("Nodes")
        for n in nodes:
            embed.add_field(name=n.get("name", n.get("attributes", {}).get("name","unknown")), value=f"ID: {n.get('id', n.get('attributes', {}).get('id',''))}", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="eggs", description="List eggs")
    @admin_check()
    async def eggs(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            eggs = await self.ptero.list_eggs()
        except PteroError as e:
            return await interaction.followup.send(embed=self.embed.error(f"Failed to list eggs: {e}"), ephemeral=True)
        embed = self.embed.info("Eggs")
        for e in eggs:
            embed.add_field(name=e.get("name", e.get("attributes", {}).get("name","unknown")), value=f"ID: {e.get('id', e.get('attributes', {}).get('id',''))}", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="panel_status", description="Check panel status")
    @admin_check()
    async def panel_status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            status = await self.ptero.panel_status()
        except PteroError as e:
            return await interaction.followup.send(embed=self.embed.error(f"Failed to get panel status: {e}"), ephemeral=True)
        embed = self.embed.info("Panel Status")
        embed.add_field(name="Status", value=status, inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="maintenance_on", description="Turn on maintenance mode")
    @app_commands.describe(reason="Optional reason to show")
    @admin_check()
    async def maintenance_on(self, interaction: discord.Interaction, reason: Optional[str] = None):
        await interaction.response.defer(ephemeral=True)
        try:
            await self.ptero.maintenance_on()
        except PteroError as e:
            return await interaction.followup.send(embed=self.embed.error(f"Failed to enable maintenance: {e}"), ephemeral=True)
        embed = self.embed.warning("🔧 Maintenance Enabled", description=reason or "Maintenance mode enabled on the panel.")
        # Maintenance may be panel-level; not server-specific: still notify admin channel
        await self.bot.get_channel(self.admin_log_channel_id).send(embed=embed) if self.admin_log_channel_id else None
        await interaction.followup.send(embed=self.embed.success("Maintenance enabled."), ephemeral=True)

    @app_commands.command(name="maintenance_off", description="Turn off maintenance mode")
    @admin_check()
    async def maintenance_off(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            await self.ptero.maintenance_off()
        except PteroError as e:
            return await interaction.followup.send(embed=self.embed.error(f"Failed to disable maintenance: {e}"), ephemeral=True)
        embed = self.embed.success("🔧 Maintenance Disabled", description="Maintenance mode disabled on the panel.")
        await self.bot.get_channel(self.admin_log_channel_id).send(embed=embed) if self.admin_log_channel_id else None
        await interaction.followup.send(embed=self.embed.success("Maintenance disabled."), ephemeral=True)

    @app_commands.command(name="backup_list", description="List backups for a server")
    @app_commands.describe(server_id="Server ID")
    @admin_check()
    async def backup_list(self, interaction: discord.Interaction, server_id: str):
        await interaction.response.defer(ephemeral=True)
        try:
            backups = await self.ptero.list_backups(server_id)
        except PteroError as e:
            return await interaction.followup.send(embed=self.embed.error(f"Failed to list backups: {e}"), ephemeral=True)
        embed = self.embed.info(f"Backups for {server_id}")
        if backups:
            for b in backups:
                embed.add_field(name=b.get("attributes", {}).get("filename", "backup"), value=f"ID: {b.get('id')}", inline=False)
        else:
            embed.description = "No backups found."
        await interaction.followup.send(embed=embed, ephemeral=True)

    # Utility commands
    @app_commands.command(name="ping", description="Ping the bot")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=self.embed.info("Pong!"), ephemeral=True)

    @app_commands.command(name="help", description="Show help")
    async def help(self, interaction: discord.Interaction):
        # Provide a short overview and direct to docs
        await interaction.response.send_message(embed=self.embed.info("Commands available. Use the slash command autocomplete for parameters."), ephemeral=True)

    @app_commands.command(name="manage", description="Open interactive management panel")
    @admin_check()
    async def manage(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        # Provide Buttons and a Select menu example
        view = discord.ui.View(timeout=120)
        class NodeSelect(discord.ui.Select):
            def __init__(self):
                options = [discord.SelectOption(label="List Nodes", description="Show nodes", value="nodes"),
                           discord.SelectOption(label="List Eggs", description="Show eggs", value="eggs")]
                super().__init__(placeholder="Select an action...", min_values=1, max_values=1, options=options)

            async def callback(self, intra: discord.Interaction):
                val = self.values[0]
                if val == "nodes":
                    try:
                        nodes = await self.ptero.list_nodes()
                        e = self.embed.info("Nodes")
                        for n in nodes:
                            e.add_field(name=n.get("name", "unknown"), value=f"ID: {n.get('id')}", inline=False)
                        await intra.response.edit_message(embed=e, view=None)
                    except PteroError as ex:
                        await intra.response.edit_message(embed=self.embed.error(str(ex)), view=None)
                elif val == "eggs":
                    try:
                        eggs = await self.ptero.list_eggs()
                        e = self.embed.info("Eggs")
                        for egg in eggs:
                            e.add_field(name=egg.get("name", "unknown"), value=f"ID: {egg.get('id')}", inline=False)
                        await intra.response.edit_message(embed=e, view=None)
                    except PteroError as ex:
                        await intra.response.edit_message(embed=self.embed.error(str(ex)), view=None)

        class RefreshButton(discord.ui.Button):
            def __init__(self):
                super().__init__(style=discord.ButtonStyle.primary, label="Refresh")

            async def callback(self, intra: discord.Interaction):
                await intra.response.edit_message(embed=self.embed.info("Refreshed."), view=view)

        view.add_item(NodeSelect())
        view.add_item(RefreshButton())
        await interaction.followup.send(embed=self.embed.info("Interactive management panel (expires in 120s)"), view=view, ephemeral=True)
