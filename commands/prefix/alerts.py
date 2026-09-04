"""
Prefix commands for update alert channel configuration.
"""

from __future__ import annotations

import discord
from discord.ext import commands

from utils.weao import set_alert_channel, get_alert_channel


class AlertsPrefix(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="execupdatechecker")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def exec_update_checker(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """
        Set the channel for automatic executor update alerts.
        Usage: !execupdatechecker #channel
        Omit channel to disable.
        """
        if channel is None:
            set_alert_channel(ctx.guild.id, "executor", None)
            await ctx.send("Executor update alerts disabled.")
            return

        set_alert_channel(ctx.guild.id, "executor", channel.id)
        await ctx.send(f"Executor update alerts will be sent to {channel.mention}.")

    @commands.command(name="robloxupdatechecker")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def roblox_update_checker(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """
        Set the channel for automatic Roblox update alerts.
        Usage: !robloxupdatechecker #channel
        Omit channel to disable.
        """
        if channel is None:
            set_alert_channel(ctx.guild.id, "roblox", None)
            await ctx.send("Roblox update alerts disabled.")
            return

        set_alert_channel(ctx.guild.id, "roblox", channel.id)
        await ctx.send(f"Roblox update alerts will be sent to {channel.mention}.")

    @commands.command(name="alertstatus")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def alert_status(self, ctx: commands.Context):
        """Show current alert channel configuration."""
        exe_ch = get_alert_channel(ctx.guild.id, "executor")
        rbx_ch = get_alert_channel(ctx.guild.id, "roblox")

        embed = discord.Embed(title="Alert Channels", color=discord.Color.blurple())
        embed.add_field(
            name="Executor updates",
            value=f"<#{exe_ch}>" if exe_ch else "Not set",
            inline=False,
        )
        embed.add_field(
            name="Roblox updates",
            value=f"<#{rbx_ch}>" if rbx_ch else "Not set",
            inline=False,
        )
        await ctx.send(embed=embed)

    @exec_update_checker.error
    @roblox_update_checker.error
    async def alerts_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("Administrator permission required.")
        else:
            await ctx.send(f"Error: `{error}`")


async def setup(bot: commands.Bot):
    await bot.add_cog(AlertsPrefix(bot))
