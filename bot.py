"""
Main entry point for the Executor Status Discord bot.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from utils.weao import (
    fetch_all_executors,
    fetch_roblox_version,
    load_cache,
    save_cache,
    load_roblox_cache,
    save_roblox_cache,
    get_all_alert_channels,
    ensure_data_dir,
)

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set. Create a .env file from .env.example.")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("bot")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None,
)


# ---------------------------------------------------------------------------
# Background checkers
# ---------------------------------------------------------------------------

@tasks.loop(minutes=5)
async def check_executor_updates():
    try:
        current = await fetch_all_executors()
        previous = load_cache()

        changes: list[str] = []
        new_cache: dict = {}

        for exe in current:
            title = exe.get("title")
            if not title:
                continue

            key = title.lower()
            version = exe.get("version")
            updated_status = exe.get("updateStatus", False)
            updated_date = exe.get("updatedDate")

            new_cache[key] = {
                "version": version,
                "updateStatus": updated_status,
                "updatedDate": updated_date,
                "title": title,
            }

            old = previous.get(key)
            if old is None:
                continue

            if old.get("version") != version:
                changes.append(f"**{title}** updated to version `{version}`")
            elif old.get("updateStatus") is False and updated_status is True:
                changes.append(f"**{title}** is now Updated (v{version})")
            elif old.get("updateStatus") is True and updated_status is False:
                changes.append(f"**{title}** is no longer updated")

        save_cache(new_cache)

        if not changes:
            return

        embed = discord.Embed(
            title="Executor Update Detected",
            description="\n".join(changes),
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text="Automatic checker • weao.xyz")

        for guild_id, channel_id in get_all_alert_channels("executor"):
            channel = bot.get_channel(channel_id)
            if channel and isinstance(channel, discord.TextChannel):
                try:
                    await channel.send(embed=embed)
                except Exception as e:
                    logger.warning("Failed to send executor alert to %s: %s", channel_id, e)

    except Exception as e:
        logger.error("Executor checker error: %s", e)


@tasks.loop(minutes=5)
async def check_roblox_updates():
    try:
        current = await fetch_roblox_version("current")
        previous = load_roblox_cache()

        changed_platforms = []
        for platform in ("Windows", "Mac", "Android", "iOS"):
            new_ver = current.get(platform)
            old_ver = previous.get(platform)
            if new_ver and old_ver and new_ver != old_ver:
                changed_platforms.append(
                    f"**{platform}** `{old_ver}` → `{new_ver}`"
                )

        # Save current as new baseline (also on first run)
        save_roblox_cache({
            "Windows": current.get("Windows"),
            "Mac": current.get("Mac"),
            "Android": current.get("Android"),
            "iOS": current.get("iOS"),
            "WindowsDate": current.get("WindowsDate"),
            "MacDate": current.get("MacDate"),
        })

        if not changed_platforms:
            return

        desc = (
            "Roblox has updated. Executors may be down until they update.\n\n"
            + "\n".join(changed_platforms)
        )

        embed = discord.Embed(
            title="Roblox Updated",
            description=desc,
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        for platform in ("Windows", "Mac", "Android", "iOS"):
            ver = current.get(platform)
            date = current.get(f"{platform}Date")
            if ver:
                value = f"`{ver}`"
                if date:
                    value += f"\n{date}"
                embed.add_field(name=platform, value=value, inline=True)

        embed.set_footer(text="Automatic checker • weao.xyz")

        for guild_id, channel_id in get_all_alert_channels("roblox"):
            channel = bot.get_channel(channel_id)
            if channel and isinstance(channel, discord.TextChannel):
                try:
                    await channel.send(embed=embed)
                except Exception as e:
                    logger.warning("Failed to send Roblox alert to %s: %s", channel_id, e)

    except Exception as e:
        logger.error("Roblox checker error: %s", e)


@check_executor_updates.before_loop
@check_roblox_updates.before_loop
async def before_checkers():
    await bot.wait_until_ready()


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@bot.event
async def on_ready():
    logger.info("Logged in as %s (ID: %s)", bot.user, bot.user.id if bot.user else "?")

    from commands.prefix.verification import VerifyButton, CaptchaStartView
    bot.add_view(VerifyButton())
    bot.add_view(CaptchaStartView())

    try:
        synced = await bot.tree.sync()
        logger.info("Synced %d application command(s)", len(synced))
    except Exception as e:
        logger.error("Failed to sync application commands: %s", e)

    if not check_executor_updates.is_running():
        check_executor_updates.start()
        logger.info("Executor update checker started")
    if not check_roblox_updates.is_running():
        check_roblox_updates.start()
        logger.info("Roblox update checker started")


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(
            f"Please wait {error.retry_after:.1f}s before using this command again.",
            delete_after=5,
        )
    elif isinstance(error, commands.CommandNotFound):
        name = ctx.invoked_with
        if name:
            from utils.weao import fetch_executor, build_executor_embed
            exe = await fetch_executor(name)
            if exe:
                embed, view = build_executor_embed(exe)
                await ctx.send(embed=embed, view=view)
    else:
        logger.error("Command error in %s: %s", ctx.command, error)


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.user_id == bot.user.id:
        return

    from commands.prefix.verification import get_guild_config, assign_verified_role

    cfg = get_guild_config(payload.guild_id)
    if not cfg or cfg.get("method") != "reaction":
        return
    if cfg.get("panel_message_id") != payload.message_id:
        return

    emoji = cfg.get("reaction_emoji", "✅")
    if str(payload.emoji) != emoji and getattr(payload.emoji, "name", None) != emoji:
        return

    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return

    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return

    ok, msg = await assign_verified_role(member, guild)
    try:
        await member.send(msg)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Cog loading
# ---------------------------------------------------------------------------

async def load_extensions():
    base = Path(__file__).parent / "commands"
    for category in ("prefix", "slash"):
        folder = base / category
        if not folder.exists():
            continue
        for file in folder.glob("*.py"):
            if file.name.startswith("_"):
                continue
            ext = f"commands.{category}.{file.stem}"
            try:
                await bot.load_extension(ext)
                logger.info("Loaded extension: %s", ext)
            except Exception as e:
                logger.error("Failed to load %s: %s", ext, e)


async def main():
    ensure_data_dir()
    async with bot:
        await load_extensions()
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
