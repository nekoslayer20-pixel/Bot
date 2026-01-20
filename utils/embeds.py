contents=
# utils/embeds.py
import discord

class EmbedFactory:
    def __init__(self):
        self.clr_success = 0x2ECC71  # green
        self.clr_error = 0xE74C3C    # red
        self.clr_warning = 0xF1C40F  # yellow
        self.clr_info = 0x3498DB     # blue

    def success(self, title: str, description: str = None) -> discord.Embed:
        e = discord.Embed(title=title, color=self.clr_success, description=description)
        return e

    def error(self, description: str, title: str = "Error") -> discord.Embed:
        e = discord.Embed(title=title, color=self.clr_error, description=description)
        return e

    def warning(self, title: str, description: str = None) -> discord.Embed:
        e = discord.Embed(title=title, color=self.clr_warning, description=description)
        return e

    def info(self, title: str, description: str = None) -> discord.Embed:
        e = discord.Embed(title=title, color=self.clr_info, description=description)
        return e
