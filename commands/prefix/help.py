"""
Prefix help command.
"""

from __future__ import annotations

import discord
from discord.ext import commands
from discord.ui import View, Select


HELP_PAGES = {
    "overview": discord.Embed(
        title="Help — Overview",
        description="Prefix: `!`  •  Slash: `/`\nUse the dropdown to browse sections.",
        color=discord.Color.blurple(),
    ).add_field(
        name="Sections",
        value=(
            "**Exploits** — List & check\n"
            "**Roblox** — Versions & update alerts\n"
            "**Verification** — Button / Reaction / Captcha\n"
            "**Commands** — Full list"
        ),
        inline=False,
    ),
    "exploits": discord.Embed(
        title="Help — Exploits",
        color=discord.Color.blurple(),
    ).add_field(
        name="Browse",
        value="`!exploits` / `/exploits` — dropdown categories + pages",
        inline=False,
    ).add_field(
        name="Check",
        value="`!check <name>` / `/check`\nShortcuts: `!solara` `!wave` `!potassium` ...",
        inline=False,
    ),
    "roblox": discord.Embed(
        title="Help — Roblox",
        color=discord.Color.blurple(),
    ).add_field(
        name="Versions",
        value=(
            "`!rversion [current|future|past]` / `/rversion`\n"
            "`!rvcurrent` `!rvfuture` `!rvpast`"
        ),
        inline=False,
    ).add_field(
        name="Auto alerts (Admin)",
        value=(
            "`!execupdatechecker #channel` — executor updates\n"
            "`!robloxupdatechecker #channel` — Roblox updates\n"
            "`!alertstatus` — show config\n"
            "Omit channel to disable."
        ),
        inline=False,
    ),
    "verification": discord.Embed(
        title="Help — Verification",
        color=discord.Color.blurple(),
    ).add_field(
        name="Setup",
        value=(
            "`!setupverify <button|reaction|captcha> @Role [#logs]`\n"
            "`!sendverify`"
        ),
        inline=False,
    ).add_field(
        name="Methods",
        value="**button** · **reaction** · **captcha**",
        inline=False,
    ),
    "commands": discord.Embed(
        title="Help — Commands",
        color=discord.Color.blurple(),
    ).add_field(
        name="Exploits",
        value="`!exploits` `!check` `!solara` ...",
        inline=False,
    ).add_field(
        name="Roblox",
        value="`!rversion` `!rvcurrent` `!rvfuture` `!rvpast`",
        inline=False,
    ).add_field(
        name="Alerts (Admin)",
        value="`!execupdatechecker` `!robloxupdatechecker` `!alertstatus`",
        inline=False,
    ).add_field(
        name="Verification (Admin)",
        value="`!setupverify` `!sendverify`",
        inline=False,
    ).add_field(
        name="Utility",
        value="`!help`",
        inline=False,
    ),
}


class HelpSelect(Select):
    def __init__(self, author_id: int):
        options = [
            discord.SelectOption(label="Overview", value="overview"),
            discord.SelectOption(label="Exploits", value="exploits"),
            discord.SelectOption(label="Roblox", value="roblox"),
            discord.SelectOption(label="Verification", value="verification"),
            discord.SelectOption(label="Commands", value="commands"),
        ]
        super().__init__(placeholder="Select a section...", options=options)
        self.author_id = author_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the user who ran this command can use the menu.",
                ephemeral=True,
            )
            return
        page = HELP_PAGES.get(self.values[0], HELP_PAGES["overview"])
        await interaction.response.edit_message(embed=page, view=self.view)


class HelpView(View):
    def __init__(self, author_id: int):
        super().__init__(timeout=180)
        self.add_item(HelpSelect(author_id))


class HelpPrefix(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="help")
    async def help_command(self, ctx: commands.Context):
        """Show help menu."""
        await ctx.send(embed=HELP_PAGES["overview"], view=HelpView(ctx.author.id))


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpPrefix(bot))
