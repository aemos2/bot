"""
Prefix commands for Roblox version info.
"""

from __future__ import annotations

import discord
from discord.ext import commands

from utils.weao import fetch_roblox_version, build_roblox_embed


class RobloxPrefix(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _send_version(self, ctx: commands.Context, kind: str):
        async with ctx.typing():
            try:
                data = await fetch_roblox_version(kind)
            except Exception as e:
                await ctx.send(f"Failed to fetch Roblox versions: `{e}`")
                return
            embed = build_roblox_embed(kind, data)
            await ctx.send(embed=embed)

    @commands.command(name="rversion")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def rversion(self, ctx: commands.Context, kind: str = "current"):
        """Show Roblox versions. Usage: !rversion [current|future|past]"""
        kind = kind.lower().strip()
        if kind not in ("current", "future", "past"):
            await ctx.send("Usage: `!rversion [current|future|past]`")
            return
        await self._send_version(ctx, kind)

    @commands.command(name="rvcurrent")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def rv_current(self, ctx: commands.Context):
        """Show current Roblox versions."""
        await self._send_version(ctx, "current")

    @commands.command(name="rvfuture")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def rv_future(self, ctx: commands.Context):
        """Show future Roblox versions."""
        await self._send_version(ctx, "future")

    @commands.command(name="rvpast")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def rv_past(self, ctx: commands.Context):
        """Show past Roblox versions."""
        await self._send_version(ctx, "past")


async def setup(bot: commands.Bot):
    await bot.add_cog(RobloxPrefix(bot))
