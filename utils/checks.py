# utils/checks.py
import os
from typing import Callable
from discord import app_commands
from discord.ext import commands

ADMIN_IDS = {int(x.strip()) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip().isdigit()}

def admin_check():
    """Require executor to be in ADMIN_IDS"""
    def predicate(interaction: commands.Context):
        return interaction.user.id in ADMIN_IDS
    return app_commands.check(predicate)
