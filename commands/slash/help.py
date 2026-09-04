"""
Slash help command.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from commands.prefix.help import HELP_PAGES, HelpView


class HelpSlash(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show help menu")
    async def help_command(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=HELP_PAGES["overview"],
            view=HelpView(interaction.user.id),
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpSlash(bot))
