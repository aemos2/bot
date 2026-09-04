"""
Slash commands for update alert channel configuration.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.weao import set_alert_channel, get_alert_channel


class AlertsSlash(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="execupdatechecker", description="Set channel for executor update alerts")
    @app_commands.describe(channel="Channel to receive alerts (leave empty to disable)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def exec_update_checker(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel = None,
    ):
        if channel is None:
            set_alert_channel(interaction.guild_id, "executor", None)
            await interaction.response.send_message("Executor update alerts disabled.", ephemeral=True)
            return

        set_alert_channel(interaction.guild_id, "executor", channel.id)
        await interaction.response.send_message(
            f"Executor update alerts will be sent to {channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(name="robloxupdatechecker", description="Set channel for Roblox update alerts")
    @app_commands.describe(channel="Channel to receive alerts (leave empty to disable)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def roblox_update_checker(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel = None,
    ):
        if channel is None:
            set_alert_channel(interaction.guild_id, "roblox", None)
            await interaction.response.send_message("Roblox update alerts disabled.", ephemeral=True)
            return

        set_alert_channel(interaction.guild_id, "roblox", channel.id)
        await interaction.response.send_message(
            f"Roblox update alerts will be sent to {channel.mention}.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AlertsSlash(bot))
