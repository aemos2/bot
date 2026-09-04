"""
WEAO API helper module.
Handles exploits, Roblox versions, cache, and embeds.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import aiohttp
import discord
from discord.ui import View, Button

logger = logging.getLogger("weao")

WEAO_DOMAINS = [
    "https://weao.xyz",
    "https://whatexpsare.online",
    "https://weao.gg",
]

USER_AGENT = "WEAO-3PService"
HEADERS = {"User-Agent": USER_AGENT}

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_FILE = DATA_DIR / "executor_cache.json"
ROBLOX_CACHE_FILE = DATA_DIR / "roblox_cache.json"
ALERTS_FILE = DATA_DIR / "alerts.json"


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


async def _request(path: str) -> Any:
    last_error: Exception | None = None
    timeout = aiohttp.ClientTimeout(total=12)

    async with aiohttp.ClientSession(headers=HEADERS, timeout=timeout) as session:
        for base in WEAO_DOMAINS:
            url = f"{base}{path}"
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    logger.warning("Domain %s returned status %s", base, resp.status)
            except Exception as e:
                logger.warning("Failed to reach %s: %s", base, e)
                last_error = e
                continue

    raise RuntimeError(f"Could not reach any WEAO domain. Last error: {last_error}") from last_error


async def fetch_all_executors() -> list[dict[str, Any]]:
    data = await _request("/api/status/exploits")
    if not isinstance(data, list):
        raise RuntimeError("Unexpected response format from WEAO API")
    return data


async def fetch_executor(name: str) -> dict[str, Any] | None:
    try:
        data = await _request(f"/api/status/exploits/{name}")
        if isinstance(data, dict) and data.get("title"):
            return data
    except Exception:
        pass

    data = await fetch_all_executors()
    name_lower = name.lower().replace(" ", "")
    for exe in data:
        title = exe.get("title", "")
        if title.lower() == name.lower() or title.lower().replace(" ", "") == name_lower:
            return exe
    return None


async def fetch_roblox_version(kind: str) -> dict[str, Any]:
    """kind: current | future | past"""
    kind = kind.lower().strip()
    if kind not in ("current", "future", "past"):
        raise ValueError("kind must be current, future, or past")
    return await _request(f"/api/versions/{kind}")


def load_cache() -> dict[str, Any]:
    ensure_data_dir()
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Failed to load executor cache: %s", e)
    return {}


def save_cache(data: dict[str, Any]) -> None:
    ensure_data_dir()
    CACHE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_roblox_cache() -> dict[str, Any]:
    ensure_data_dir()
    if ROBLOX_CACHE_FILE.exists():
        try:
            return json.loads(ROBLOX_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_roblox_cache(data: dict[str, Any]) -> None:
    ensure_data_dir()
    ROBLOX_CACHE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_alerts() -> dict[str, Any]:
    ensure_data_dir()
    if ALERTS_FILE.exists():
        try:
            return json.loads(ALERTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_alerts(data: dict[str, Any]) -> None:
    ensure_data_dir()
    ALERTS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def set_alert_channel(guild_id: int, kind: str, channel_id: int | None) -> None:
    """kind: executor | roblox"""
    data = load_alerts()
    gid = str(guild_id)
    if gid not in data:
        data[gid] = {}
    data[gid][kind] = channel_id
    save_alerts(data)


def get_alert_channel(guild_id: int, kind: str) -> int | None:
    data = load_alerts()
    return data.get(str(guild_id), {}).get(kind)


def get_all_alert_channels(kind: str) -> list[tuple[int, int]]:
    """Return list of (guild_id, channel_id) for a kind."""
    data = load_alerts()
    result = []
    for gid, conf in data.items():
        ch = conf.get(kind)
        if ch:
            result.append((int(gid), int(ch)))
    return result


def _type_label(exe: dict) -> str:
    extype = (exe.get("extype") or "").lower()
    if "external" in extype:
        return "External"
    if "executor" in extype:
        return "Internal"
    title = (exe.get("title") or "").lower()
    if "external" in title:
        return "External"
    return "Internal"


class ExecutorView(View):
    def __init__(self, website: str | None = None, discord_url: str | None = None, purchase: str | None = None):
        super().__init__(timeout=None)
        if website:
            self.add_item(Button(label="Website", url=website, style=discord.ButtonStyle.link))
        if discord_url:
            self.add_item(Button(label="Discord", url=discord_url, style=discord.ButtonStyle.link))
        if purchase:
            self.add_item(Button(label="Purchase", url=purchase, style=discord.ButtonStyle.link))


def build_executor_embed(exe: dict[str, Any]) -> tuple[discord.Embed, ExecutorView | None]:
    title = exe.get("title", "Unknown")
    version = exe.get("version", "N/A")
    updated = exe.get("updatedDate", "Unknown")
    free = exe.get("free", False)
    detected = exe.get("detected", False)
    updated_status = exe.get("updateStatus", False)
    platform = exe.get("platform", "Unknown")
    cost = exe.get("cost") or ("Free" if free else "Paid")
    unc = exe.get("uncPercentage")
    sunc = exe.get("suncPercentage")
    decompiler = exe.get("decompiler", False)
    multi = exe.get("multiInject", False)
    website = exe.get("websitelink")
    discord_link = exe.get("discordlink")
    purchase = exe.get("purchaselink")
    rbx = exe.get("rbxversion", "N/A")

    logo = None
    description = None
    slug = exe.get("slug") or {}
    if isinstance(slug, dict):
        logo = slug.get("logo")
        description = slug.get("fullDescription")

    if updated_status:
        color = discord.Color.green()
    else:
        color = discord.Color.red()
    if detected:
        color = discord.Color.orange()

    embed = discord.Embed(
        title=f"{title}  •  v{version}",
        color=color,
        timestamp=discord.utils.utcnow(),
    )

    status_text = "Updated" if updated_status else "Not Updated"
    detect_text = "Detected" if detected else "Undetected"
    price_text = "Free" if free else str(cost)
    exe_type = _type_label(exe)

    embed.add_field(name="Status", value=status_text, inline=True)
    embed.add_field(name="Detection", value=detect_text, inline=True)
    embed.add_field(name="Price", value=price_text, inline=True)

    embed.add_field(name="Platform", value=platform, inline=True)
    embed.add_field(name="Type", value=exe_type, inline=True)
    embed.add_field(name="Last Updated", value=updated, inline=True)
    embed.add_field(name="Roblox Version", value=f"`{rbx}`", inline=True)

    features = []
    if decompiler:
        features.append("Decompiler")
    if multi:
        features.append("Multi-Inject")
    if exe.get("clientmods"):
        features.append("Client Mods")
    if exe.get("raknet"):
        features.append("RakNet")
    if features:
        embed.add_field(name="Features", value=", ".join(features), inline=False)

    scores = []
    if unc is not None:
        scores.append(f"UNC: **{unc}%**")
    if sunc is not None:
        scores.append(f"sUNC: **{sunc}%**")
    if scores:
        embed.add_field(name="Compatibility", value=" • ".join(scores), inline=False)

    if description and len(description) < 900:
        embed.add_field(name="Description", value=description[:900], inline=False)

    if logo:
        embed.set_thumbnail(url=logo)

    embed.set_footer(text="Powered by WEAO")

    view = None
    if website or discord_link or purchase:
        view = ExecutorView(website=website, discord_url=discord_link, purchase=purchase)

    return embed, view


def build_roblox_embed(kind: str, data: dict[str, Any]) -> discord.Embed:
    titles = {
        "current": "Roblox Versions — Current",
        "future": "Roblox Versions — Future",
        "past": "Roblox Versions — Past",
    }
    embed = discord.Embed(
        title=titles.get(kind, f"Roblox Versions — {kind.title()}"),
        color=discord.Color.blurple(),
        timestamp=discord.utils.utcnow(),
    )

    for platform in ("Windows", "Mac", "Android", "iOS"):
        version = data.get(platform)
        date = data.get(f"{platform}Date")
        if version:
            value = f"`{version}`"
            if date:
                value += f"\n{date}"
            embed.add_field(name=platform, value=value, inline=True)

    embed.set_footer(text="Data from weao.xyz")
    return embed
