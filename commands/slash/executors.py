"""
Slash commands for executor / exploit status.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.weao import fetch_all_executors, fetch_executor, build_executor_embed
from utils.pagination import CategoryView
from commands.prefix.executors import build_exploit_categories


class ExecutorSlash(commands.Cog):
    """Slash commands related to Roblox executors and exploits."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="exploits", description="Browse executors and external exploits by category")
    @app_commands.checks.cooldown(1, 5.0)
    async def exploits(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        try:
            data = await fetch_all_executors()
        except Exception as e:
            await interaction.followup.send(f"Failed to fetch data: `{e}`")
            return

        categories = build_exploit_categories(data)
        if not categories:
            await interaction.followup.send("No data available right now.")
            return

        first_name = next(iter(categories))
        first_embeds = categories[first_name]
        view = CategoryView(categories, author_id=interaction.user.id, current_category=first_name)
        await interaction.followup.send(embed=first_embeds[0], view=view)

    @app_commands.command(name="check", description="Check the status of a specific executor or external")
    @app_commands.describe(name="Name (e.g. Solara, Wave, Serotonin)")
    @app_commands.checks.cooldown(1, 3.0)
    async def check(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(thinking=True)

        exe = await fetch_executor(name)
        if not exe:
            await interaction.followup.send(
                f"Could not find **{name}**.\n"
                "Use `/exploits` to browse the list."
            )
            return

        embed, view = build_executor_embed(exe)
        await interaction.followup.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(ExecutorSlash(bot))
