"""
Main entry point for the Executor Status Discord bot + Wave AI.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import aiohttp
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
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set. Create a .env file from .env.example.")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("bot")

# Wave AI settings
MODEL = "openai/gpt-4o-mini"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.dm_messages = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None,
)


# ---------------------------------------------------------------------------
# Wave AI helper
# ---------------------------------------------------------------------------

async def ask_wave(prompt: str) -> str:
    if not OPENROUTER_API_KEY:
        return "yo api key missing, fix the .env"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/yourusername/executor-status-bot",
        "X-Title": "Wave AI",
    }

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": """You are Skibidi, a super chill and nonchalant Roblox scripting assistant from the Skibidi Hub ecosystem.

Personality:
- Extremely chill and low-key
- Talks short and dry, almost lazy
- Never overhype or get excited
- Uses short replies like "sup", "yo", "bet", "aight", "fs", "ion know", etc.
- Still knowledgeable AF about Lua, executors (Solara, Synapse, Krnl, etc.), game mechanics, exploits and anti-cheat
- Only gives longer answers when the user actually asks a real question
- Never sounds try-hard or corny

Keep almost every reply short and nonchalant unless they ask for actual help.""",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(OPENROUTER_URL, headers=headers, json=payload) as resp:
            data = await resp.json()

            if resp.status != 200:
                error_msg = data.get("error", {}).get("message", "Unknown error")
                logger.error("OpenRouter error: %s", error_msg)
                return "sum went wrong talking to the ai 💀"

            return data["choices"][0]["message"]["content"]


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
    logger.info("Wave AI ready (model: %s)", MODEL)

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
async def on_message(message: discord.Message):
    # Ignore other bots
    if message.author.bot:
        return

    # Let prefix commands still work
    await bot.process_commands(message)

    # Wave AI — only when mentioned or in DMs
    is_mentioned = bot.user and bot.user in message.mentions
    is_dm = isinstance(message.channel, discord.DMChannel)

    if not is_mentioned and not is_dm:
        return

    # Strip the bot mention
    prompt = message.content
    if bot.user:
        prompt = prompt.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "")
    prompt = prompt.strip()

    if not prompt:
        await message.reply("yo")
        return

    async with message.channel.typing():
        try:
            reply = await ask_wave(prompt)

            if len(reply) > 2000:
                for i in range(0, len(reply), 1990):
                    await message.reply(reply[i : i + 1990])
            else:
                await message.reply(reply)
        except Exception as e:
            logger.error("Wave AI error: %s", e)
            await message.reply("sum went wrong 💀")


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
