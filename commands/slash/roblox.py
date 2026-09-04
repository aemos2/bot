"""
Slash commands for Roblox version info.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.weao import fetch_roblox_version, build_roblox_embed


class RobloxSlash(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="rversion", description="Show Roblox client versions")
    @app_commands.describe(kind="Which version set to show")
    @app_commands.choices(kind=[
        app_commands.Choice(name="Current", value="current"),
        app_commands.Choice(name="Future", value="future"),
        app_commands.Choice(name="Past", value="past"),
    ])
    @app_commands.checks.cooldown(1, 5.0)
    async def rversion(self, interaction: discord.Interaction, kind: app_commands.Choice[str]):
        await interaction.response.defer(thinking=True)
        try:
            data = await fetch_roblox_version(kind.value)
        except Exception as e:
            await interaction.followup.send(f"Failed to fetch Roblox versions: `{e}`")
            return
        embed = build_roblox_embed(kind.value, data)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(RobloxSlash(bot))
