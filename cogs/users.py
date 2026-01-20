# cogs/users.py
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.api import PteroAPI, PteroError
from utils.embeds import EmbedFactory
from utils.checks import admin_check

logger = logging.getLogger("pterobot.users")

class UsersCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ptero: PteroAPI = bot.ptero
        self.embed = bot.embed
        self.admin_log_channel_id = bot.admin_log_channel_id

    async def dm_or_log(self, member: discord.Member, embed: discord.Embed, admin_message: str):
        try:
            await member.send(embed=embed)
            return True
        except Exception as e:
            if self.admin_log_channel_id:
                channel = self.bot.get_channel(self.admin_log_channel_id)
                if channel:
                    await channel.send(f"Failed to DM {member} ({member.id}). Admin log:\n{admin_message}")
            return False

    @app_commands.command(name="user_list", description="List panel users (paginated)")
    @app_commands.describe(page="Page number")
    @admin_check()
    async def user_list(self, interaction: discord.Interaction, page: int = 1):
        await interaction.response.defer(ephemeral=True)
        try:
            data = await self.ptero.list_users(page=page)
        except PteroError as e:
            return await interaction.followup.send(embed=self.embed.error(f"Failed to list users: {e}"), ephemeral=True)
        embed = self.embed.info("Panel Users", description=f"Page {page}")
        if data.get("data"):
            for u in data["data"]:
                a = u.get("attributes", {})
                embed.add_field(name=a.get("username", a.get("email", "unknown")), value=f"ID: {a.get('id')}", inline=False)
        else:
            embed.description = "No users found."
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="user_search", description="Search users by email or username")
    @app_commands.describe(query="Search query")
    @admin_check()
    async def user_search(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(ephemeral=True)
        try:
            results = await self.ptero.search_users(query=query)
        except PteroError as e:
            return await interaction.followup.send(embed=self.embed.error(f"Search failed: {e}"), ephemeral=True)
        embed = self.embed.info("User Search Results", description=f"Query: {query}")
        if results:
            for u in results:
                embed.add_field(name=u.get("username", u.get("email", "unknown")), value=f"ID: {u.get('id')}", inline=False)
        else:
            embed.description = "No results"
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="delete_user", description="Delete a panel user")
    @app_commands.describe(user_id="Panel user ID", discord_user="Discord user to notify")
    @admin_check()
    async def delete_user(self, interaction: discord.Interaction, user_id: int, discord_user: discord.Member):
        await interaction.response.defer(ephemeral=True)
        try:
            await self.ptero.delete_user(user_id)
        except PteroError as e:
            return await interaction.followup.send(embed=self.embed.error(f"Failed to delete user: {e}"), ephemeral=True)
        embed = self.embed.warning("❌ USER DELETED", description="Your panel user has been deleted.")
        embed.add_field(name="User ID", value=str(user_id), inline=True)
        admin_message = f"Panel user {user_id} deleted by {interaction.user} for {discord_user}"
        await self.dm_or_log(discord_user, embed, admin_message)
        await interaction.followup.send(embed=self.embed.success("User deleted and discord user notified (or logged)."), ephemeral=True)

    @app_commands.command(name="change_password", description="Change a panel user's password")
    @app_commands.describe(user_id="Panel user ID", new_password="New password (leave blank to auto-generate)")
    @admin_check()
    async def change_password(self, interaction: discord.Interaction, user_id: int, new_password: Optional[str] = None):
        await interaction.response.defer(ephemeral=True)
        if not new_password:
            new_password = PteroAPI.generate_password()
            auto = True
        else:
            auto = False
        try:
            await self.ptero.change_user_password(user_id, new_password)
        except PteroError as e:
            return await interaction.followup.send(embed=self.embed.error(f"Failed to change password: {e}"), ephemeral=True)
        embed = self.embed.success("🔐 Password Changed", description="Password updated successfully.")
        embed.add_field(name="User ID", value=str(user_id), inline=True)
        embed.add_field(name="Password", value=new_password, inline=True)
        if auto:
            embed.set_footer(text="Password auto-generated.")
        await interaction.followup.send(embed=embed, ephemeral=True)
