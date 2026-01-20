# cogs/servers.py
import os
import logging
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.api import PteroAPI, PteroError
from utils.embeds import EmbedFactory
from utils.checks import admin_check

logger = logging.getLogger("pterobot.servers")

class ServersCog(commands.Cog):
    """Server management commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ptero: PteroAPI = bot.ptero
        self.embed = bot.embed
        self.admin_ids = bot.admin_ids
        self.admin_log_channel_id = bot.admin_log_channel_id

    async def dm_or_log(self, member: discord.Member, embed: discord.Embed, admin_message: str):
        """Try to DM the member. If fails, log to admin channel."""
        try:
            await member.send(embed=embed)
            return True
        except Exception as e:
            logger.warning(f"Failed to DM {member} ({e}), logging to admin channel.")
            # log in admin channel
            if self.admin_log_channel_id:
                channel = self.bot.get_channel(self.admin_log_channel_id)
                if channel:
                    await channel.send(f"Failed to DM {member} ({member.id}). Admin log:\n{admin_message}")
            return False

    async def log_action(self, content: str, embed: Optional[discord.Embed] = None):
        if self.admin_log_channel_id:
            channel = self.bot.get_channel(self.admin_log_channel_id)
            if channel:
                await channel.send(content=content, embed=embed)

    @app_commands.command(name="createserver", description="Create a server on the panel")
    @app_commands.describe(name="Server name", ram="RAM (MB)", cpu="CPU (%)", disk="Disk (MB)", version="Docker image or startup version", node_id="Node ID", egg_id="Egg ID", user="Discord user to own server")
    @admin_check()  # admin only
    async def createserver(self, interaction: discord.Interaction, name: str, ram: int, cpu: int, disk: int, version: str, node_id: int, egg_id: int, user: discord.Member):
        await interaction.response.defer(ephemeral=True)
        # validate resources
        if ram < 128 or ram > 32768:
            return await interaction.followup.send(embed=self.embed.error("RAM must be between 128MB and 32768MB"), ephemeral=True)
        if cpu < 1 or cpu > 400:
            return await interaction.followup.send(embed=self.embed.error("CPU must be between 1% and 400%"), ephemeral=True)
        if disk < 100 or disk > 1000000:
            return await interaction.followup.send(embed=self.embed.error("Disk must be between 100MB and 1TB"), ephemeral=True)

        # Validate node & egg
        try:
            node = await self.ptero.get_node(node_id)
        except PteroError as e:
            return await interaction.followup.send(embed=self.embed.error(f"Node validation failed: {e}"), ephemeral=True)
        try:
            egg = await self.ptero.get_egg(egg_id)
        except PteroError as e:
            return await interaction.followup.send(embed=self.embed.error(f"Egg validation failed: {e}"), ephemeral=True)

        # Ensure panel user exists for the Discord member (lookup by synthetic email)
        panel_user_email = f"discord-{user.id}@local"
        created_user = False
        try:
            panel_user = await self.ptero.find_user_by_email(panel_user_email)
            if not panel_user:
                # create user
                password = PteroAPI.generate_password()
                panel_user = await self.ptero.create_user(username=f"{user.display_name}-{user.id}", email=panel_user_email, first_name=user.display_name[:50], last_name="", password=password)
                created_user = True
                created_password = password
            else:
                created_password = None
        except PteroError as e:
            return await interaction.followup.send(embed=self.embed.error(f"User lookup/creation failed: {e}"), ephemeral=True)

        # Create server
        try:
            server = await self.ptero.create_server(
                name=name,
                user_id=panel_user["id"],
                egg_id=egg_id,
                node_id=node_id,
                memory=ram,
                cpu=cpu,
                disk=disk,
                version=version
            )
        except PteroError as e:
            return await interaction.followup.send(embed=self.embed.error(f"Server creation failed: {e}"), ephemeral=True)

        # DM the user
        embed = self.embed.success("✅ SERVER CREATED", description=f"Your server has been created.")
        embed.add_field(name="Server Name", value=name, inline=True)
        embed.add_field(name="Server ID", value=str(server.get("id", server.get("identifier", "unknown"))), inline=True)
        embed.add_field(name="Node", value=str(node_id), inline=True)
        embed.add_field(name="RAM", value=f"{ram} MB", inline=True)
        embed.add_field(name="CPU", value=f"{cpu} %", inline=True)
        embed.add_field(name="Disk", value=f"{disk} MB", inline=True)
        embed.add_field(name="Version", value=str(version), inline=True)
        embed.add_field(name="Panel URL", value=self.ptero.base_url, inline=False)
        embed.add_field(name="Username", value=panel_user.get("username", panel_user.get("email", "unknown")), inline=True)
        if created_password:
            embed.add_field(name="Password", value=created_password, inline=True)
            embed.set_footer(text="Password shown because a new panel user was created for you.")
        # send DM or log
        admin_message = f"Server created: {name} by {interaction.user} for {user} - server_id={server.get('id')}"
        await self.dm_or_log(user, embed, admin_message)
        # log action in admin channel
        await self.log_action(content=f"Server created by {interaction.user} for {user}: {name} (ID {server.get('id')})", embed=embed)
        await interaction.followup.send(embed=self.embed.success("Server creation initiated and user notified (or logged)."), ephemeral=True)

    @app_commands.command(name="delete_server", description="Delete a server")
    @app_commands.describe(server_id="Server ID", user="Discord user to notify")
    @admin_check()
    async def delete_server(self, interaction: discord.Interaction, server_id: str, user: discord.Member):
        await interaction.response.defer(ephemeral=True)
        try:
            await self.ptero.delete_server(server_id)
        except PteroError as e:
            return await interaction.followup.send(embed=self.embed.error(f"Server deletion failed: {e}"), ephemeral=True)

        # DM user
        embed = self.embed.warning("❌ SERVER DELETED", description="Your server has been deleted.")
        embed.add_field(name="Server ID", value=server_id, inline=True)
        embed.add_field(name="Deleted By", value=f"{interaction.user} ({interaction.user.id})", inline=True)
        embed.add_field(name="Date & Time", value=datetime.utcnow().isoformat() + "Z", inline=True)
        admin_message = f"Server {server_id} deleted by {interaction.user} for {user}"
        await self.dm_or_log(user, embed, admin_message)
        await self.log_action(content=f"Server {server_id} deleted by {interaction.user} for {user}")
        await interaction.followup.send(embed=self.embed.success("Server deleted and user notified (or logged)."), ephemeral=True)

    @app_commands.command(name="suspend", description="Suspend a server")
    @app_commands.describe(server_id="Server ID", user="Discord user to notify", reason="Reason (optional)")
    @admin_check()
    async def suspend(self, interaction: discord.Interaction, server_id: str, user: discord.Member, reason: Optional[str] = None):
        await interaction.response.defer(ephemeral=True)
        try:
            await self.ptero.suspend_server(server_id)
        except PteroError as e:
            return await interaction.followup.send(embed=self.embed.error(f"Suspend failed: {e}"), ephemeral=True)
        embed = self.embed.warning("⚠️ SERVER SUSPENDED", description=f"Your server has been suspended.")
        embed.add_field(name="Server ID", value=server_id, inline=True)
        embed.add_field(name="Reason", value=reason or "No reason provided", inline=True)
        admin_message = f"Server {server_id} suspended by {interaction.user} for {user}: {reason}"
        await self.dm_or_log(user, embed, admin_message)
        await self.log_action(content=f"Server {server_id} suspended by {interaction.user} for {user}")
        await interaction.followup.send(embed=self.embed.success("Server suspended and user notified (or logged)."), ephemeral=True)

    @app_commands.command(name="unsuspend", description="Unsuspend a server")
    @app_commands.describe(server_id="Server ID", user="Discord user to notify", reason="Reason (optional)")
    @admin_check()
    async def unsuspend(self, interaction: discord.Interaction, server_id: str, user: discord.Member, reason: Optional[str] = None):
        await interaction.response.defer(ephemeral=True)
        try:
            await self.ptero.unsuspend_server(server_id)
        except PteroError as e:
            return await interaction.followup.send(embed=self.embed.error(f"Unsuspend failed: {e}"), ephemeral=True)
        embed = self.embed.success("✅ SERVER UNSUSPENDED", description=f"Your server has been unsuspended.")
        embed.add_field(name="Server ID", value=server_id, inline=True)
        embed.add_field(name="Reason", value=reason or "No reason provided", inline=True)
        admin_message = f"Server {server_id} unsuspended by {interaction.user} for {user}: {reason}"
        await self.dm_or_log(user, embed, admin_message)
        await self.log_action(content=f"Server {server_id} unsuspended by {interaction.user} for {user}")
        await interaction.followup.send(embed=self.embed.success("Server unsuspended and user notified (or logged)."), ephemeral=True)

    @app_commands.command(name="list_servers", description="List servers (paginated)")
    @app_commands.describe(page="Page number")
    @admin_check()
    async def list_servers(self, interaction: discord.Interaction, page: int = 1):
        await interaction.response.defer(ephemeral=True)
        try:
            data = await self.ptero.list_servers(page=page)
        except PteroError as e:
            return await interaction.followup.send(embed=self.embed.error(f"Failed to list servers: {e}"), ephemeral=True)
        embed = self.embed.info("Servers List", description=f"Page {page}")
        if data.get("data"):
            for s in data["data"]:
                attrs = s.get("attributes", {})
                embed.add_field(name=attrs.get("name", "unknown"), value=f"ID: {attrs.get('id')}\nIdentifier: {attrs.get('identifier')}", inline=False)
        else:
            embed.description = "No servers found."
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="server_info", description="Get server info by ID")
    @app_commands.describe(server_id="Server ID")
    @admin_check()
    async def server_info(self, interaction: discord.Interaction, server_id: str):
        await interaction.response.defer(ephemeral=True)
        try:
            srv = await self.ptero.get_server(server_id)
        except PteroError as e:
            return await interaction.followup.send(embed=self.embed.error(f"Failed to get server: {e}"), ephemeral=True)
        embed = self.embed.info("Server Information")
        embed.add_field(name="Server ID", value=str(server_id), inline=True)
        embed.add_field(name="Name", value=srv.get("name") or srv.get("attributes", {}).get("name", "unknown"), inline=True)
        build = srv.get("attributes", {}).get("limits", {}) if isinstance(srv, dict) else {}
        if build:
            embed.add_field(name="RAM", value=f"{build.get('memory', 'N/A')} MB", inline=True)
            embed.add_field(name="CPU", value=str(build.get('cpu', 'N/A')), inline=True)
            embed.add_field(name="Disk", value=f"{build.get('disk', 'N/A')} MB", inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="server_search", description="Search servers by name or identifier")
    @app_commands.describe(query="Search query")
    @admin_check()
    async def server_search(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(ephemeral=True)
        try:
            results = await self.ptero.search_servers(query=query)
        except PteroError as e:
            return await interaction.followup.send(embed=self.embed.error(f"Search failed: {e}"), ephemeral=True)
        embed = self.embed.info("Server Search Results", description=f"Query: {query}")
        if results:
            for s in results:
                embed.add_field(name=s.get("name", s.get("attributes", {}).get("name", "unknown")), value=f"ID: {s.get('id', s.get('attributes', {}).get('id',''))}", inline=False)
        else:
            embed.description = "No results"
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="set_resources", description="Set server resources")
    @app_commands.describe(server_id="Server ID", ram="RAM (MB)", cpu="CPU (%)", disk="Disk (MB)", user="Discord user to notify")
    @admin_check()
    async def set_resources(self, interaction: discord.Interaction, server_id: str, ram: int, cpu: int, disk: int, user: discord.Member):
        await interaction.response.defer(ephemeral=True)
        # validations
        if ram < 128 or ram > 32768:
            return await interaction.followup.send(embed=self.embed.error("Invalid RAM"), ephemeral=True)
        if cpu < 1 or cpu > 400:
            return await interaction.followup.send(embed=self.embed.error("Invalid CPU"), ephemeral=True)
        if disk < 100 or disk > 1000000:
            return await interaction.followup.send(embed=self.embed.error("Invalid Disk"), ephemeral=True)
        try:
            await self.ptero.set_server_resources(server_id, ram, cpu, disk)
        except PteroError as e:
            return await interaction.followup.send(embed=self.embed.error(f"Failed to set resources: {e}"), ephemeral=True)
        embed = self.embed.success("⚙️ Resources Updated", description="Your server resources have been updated.")
        embed.add_field(name="Server ID", value=server_id, inline=True)
        embed.add_field(name="RAM", value=f"{ram} MB", inline=True)
        embed.add_field(name="CPU", value=f"{cpu} %", inline=True)
        embed.add_field(name="Disk", value=f"{disk} MB", inline=True)
        admin_message = f"Resources changed for {server_id} by {interaction.user} for {user}: RAM={ram} CPU={cpu} DISK={disk}"
        await self.dm_or_log(user, embed, admin_message)
        await self.log_action(content=f"Resources set for {server_id} by {interaction.user}")
        await interaction.followup.send(embed=self.embed.success("Resources updated and user notified (or logged)."), ephemeral=True)

    # Additional helper commands can be added similarly.
