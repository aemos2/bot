"""
Prefix commands for executor / exploit status.
"""

from __future__ import annotations

import discord
from discord.ext import commands

from utils.weao import fetch_all_executors, fetch_executor, build_executor_embed
from utils.pagination import CategoryView


def _platform_label(platform: str | None) -> str:
    if not platform:
        return "Unknown"
    p = platform.lower()
    if "windows" in p or p == "pc":
        return "Windows"
    if "mac" in p:
        return "Mac"
    if "android" in p:
        return "Android"
    if "ios" in p:
        return "iOS"
    return platform


def _is_external(exe: dict) -> bool:
    extype = (exe.get("extype") or "").lower()
    if "external" in extype:
        return True
    title = (exe.get("title") or "").lower()
    return "external" in title


def _build_category_pages(items: list[dict], title: str, per_page: int = 12) -> list[discord.Embed]:
    """Turn a list of executors into compact 2-column paginated embeds."""
    items = sorted(items, key=lambda x: (not x.get("updateStatus", False), x.get("title", "").lower()))
    pages: list[discord.Embed] = []
    total = len(items)

    if not items:
        embed = discord.Embed(title=title, description="No entries found.", color=discord.Color.blurple())
        return [embed]

    for i in range(0, total, per_page):
        chunk = items[i : i + per_page]
        embed = discord.Embed(title=title, color=discord.Color.blurple())

        for exe in chunk:
            name = exe.get("title", "?")
            version = exe.get("version", "")
            status = "Updated" if exe.get("updateStatus") else "Not Updated"
            price = "Free" if exe.get("free") else (exe.get("cost") or "Paid")

            # Compact field: name as title, small info as value
            field_name = f"{name}"
            field_value = f"`{version}`\n{status} · {price}"
            embed.add_field(name=field_name, value=field_value, inline=True)

        # Discord shows inline fields in rows of 3; keep it clean
        page_num = (i // per_page) + 1
        total_pages = max(1, (total + per_page - 1) // per_page)
        embed.set_footer(text=f"Page {page_num}/{total_pages}  •  {total} total  •  !check <name>")
        pages.append(embed)

    return pages


def build_exploit_categories(data: list[dict]) -> dict[str, list[discord.Embed]]:
    """
    Build category → list of embeds.
    Categories:
      - Windows Executors
      - Mac Executors
      - Android Executors
      - External Exploits
    """
    visible = [e for e in data if not e.get("hidden")]

    windows_exec = []
    mac_exec = []
    android_exec = []
    externals = []

    for exe in visible:
        if _is_external(exe):
            externals.append(exe)
            continue

        platform = _platform_label(exe.get("platform"))
        if platform == "Windows":
            windows_exec.append(exe)
        elif platform == "Mac":
            mac_exec.append(exe)
        elif platform == "Android":
            android_exec.append(exe)
        else:
            # fallback – treat as windows-style executor
            windows_exec.append(exe)

    categories = {
        "Windows Executors": _build_category_pages(windows_exec, "Windows Executors"),
        "Mac Executors": _build_category_pages(mac_exec, "Mac Executors"),
        "Android Executors": _build_category_pages(android_exec, "Android Executors"),
        "External Exploits": _build_category_pages(externals, "External Exploits"),
    }

    # Remove empty categories so the dropdown stays clean
    return {k: v for k, v in categories.items() if v and not (len(v) == 1 and "No entries found" in (v[0].description or ""))}


class ExecutorPrefix(commands.Cog):
    """Prefix commands related to Roblox executors and exploits."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="exploits", aliases=["executors", "list", "exes"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def exploits(self, ctx: commands.Context):
        """List exploits with a category dropdown."""
        async with ctx.typing():
            try:
                data = await fetch_all_executors()
            except Exception as e:
                await ctx.send(f"Failed to fetch data: `{e}`")
                return

            categories = build_exploit_categories(data)
            if not categories:
                await ctx.send("No data available right now.")
                return

            # Start on the first category
            first_name = next(iter(categories))
            first_embeds = categories[first_name]
            view = CategoryView(categories, author_id=ctx.author.id, current_category=first_name)
            await ctx.send(embed=first_embeds[0], view=view)

    @commands.command(name="check")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def check(self, ctx: commands.Context, *, name: str = None):
        """Check the status of a specific executor or external. Usage: !check Solara"""
        if not name:
            await ctx.send("Usage: `!check <name>`\nExample: `!check Solara`")
            return

        async with ctx.typing():
            exe = await fetch_executor(name)
            if not exe:
                await ctx.send(
                    f"Could not find **{name}**.\n"
                    "Use `!exploits` to browse the list."
                )
                return
            embed, view = build_executor_embed(exe)
            await ctx.send(embed=embed, view=view)

    @commands.command(name="solara")
    async def solara(self, ctx: commands.Context):
        await self.check(ctx, name="Solara")

    @commands.command(name="wave")
    async def wave(self, ctx: commands.Context):
        await self.check(ctx, name="Wave")

    @commands.command(name="potassium")
    async def potassium(self, ctx: commands.Context):
        await self.check(ctx, name="Potassium")

    @commands.command(name="codex")
    async def codex(self, ctx: commands.Context):
        await self.check(ctx, name="Codex")

    @commands.command(name="sirhurt")
    async def sirhurt(self, ctx: commands.Context):
        await self.check(ctx, name="SirHurt")

    @commands.command(name="cosmic")
    async def cosmic(self, ctx: commands.Context):
        await self.check(ctx, name="Cosmic")

    @commands.command(name="real")
    async def real(self, ctx: commands.Context):
        await self.check(ctx, name="Real")

    @commands.command(name="photon")
    async def photon(self, ctx: commands.Context):
        await self.check(ctx, name="Photon")

    @commands.command(name="ronin")
    async def ronin(self, ctx: commands.Context):
        await self.check(ctx, name="Ronin")


async def setup(bot: commands.Bot):
    await bot.add_cog(ExecutorPrefix(bot))
