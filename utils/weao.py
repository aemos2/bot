"""
WEAO API helper module.

Handles:
- WEAO executor/exploit status
- Roblox version information
- Local caching
- Alert channel configuration
- Discord embeds and buttons
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp
import discord
from discord.ui import Button, View

logger = logging.getLogger("weao")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WEAO_DOMAINS = [
    "https://weao.xyz",
    "https://whatexpsare.online",
    "https://weao.gg",
]

USER_AGENT = "WEAO-3PService"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
}

REQUEST_TIMEOUT = 12

# Cache duration in seconds.
EXECUTOR_CACHE_TTL = 300       # 5 minutes
ROBLOX_CACHE_TTL = 120         # 2 minutes

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

CACHE_FILE = DATA_DIR / "executor_cache.json"
ROBLOX_CACHE_FILE = DATA_DIR / "roblox_cache.json"
ALERTS_FILE = DATA_DIR / "alerts.json"

VALID_VERSION_KINDS = {"current", "future", "past"}
VALID_ALERT_KINDS = {"executor", "roblox"}


# ---------------------------------------------------------------------------
# HTTP session
# ---------------------------------------------------------------------------

_session: aiohttp.ClientSession | None = None


async def get_session() -> aiohttp.ClientSession:
    """
    Return the shared aiohttp session.

    The session is created lazily and reused across requests.
    """
    global _session

    if _session is None or _session.closed:
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

        _session = aiohttp.ClientSession(
            headers=HEADERS,
            timeout=timeout,
        )

    return _session


async def close_session() -> None:
    """Close the shared aiohttp session."""
    global _session

    if _session is not None and not _session.closed:
        await _session.close()

    _session = None


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------

def ensure_data_dir() -> None:
    """Create the data directory if it does not exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def truncate(value: Any, limit: int) -> str:
    """
    Convert a value to a string and safely truncate it.

    Useful for values coming from an external API because Discord
    imposes limits on embed fields and titles.
    """
    if value is None:
        return ""

    text = str(value)

    if len(text) <= limit:
        return text

    return text[: limit - 3] + "..."


def valid_url(value: Any) -> bool:
    """Return True if value is a valid HTTP/HTTPS URL."""
    if not isinstance(value, str):
        return False

    value = value.strip()

    if not value:
        return False

    try:
        parsed = urlparse(value)
    except ValueError:
        return False

    return (
        parsed.scheme in {"http", "https"}
        and bool(parsed.netloc)
    )


def validate_kind(
    kind: str,
    allowed: set[str],
    description: str,
) -> str:
    """Normalize and validate a kind value."""
    kind = str(kind).lower().strip()

    if kind not in allowed:
        raise ValueError(
            f"kind must be one of: {', '.join(sorted(allowed))}"
        )

    return kind


# ---------------------------------------------------------------------------
# HTTP requests
# ---------------------------------------------------------------------------

async def _request(path: str) -> Any:
    """
    Make a GET request against the configured WEAO domains.

    If one domain fails, the next domain is attempted.
    """
    session = await get_session()

    errors: list[str] = []

    for base in WEAO_DOMAINS:
        url = f"{base}{path}"

        try:
            async with session.get(url) as response:
                if response.status != 200:
                    message = f"{base}: HTTP {response.status}"
                    errors.append(message)

                    logger.warning(
                        "WEAO request failed: %s",
                        message,
                    )
                    continue

                try:
                    return await response.json(
                        content_type=None
                    )
                except (aiohttp.ContentTypeError, json.JSONDecodeError) as exc:
                    message = f"{base}: invalid JSON ({exc})"
                    errors.append(message)

                    logger.warning(
                        "WEAO returned invalid JSON: %s",
                        message,
                    )

        except asyncio.TimeoutError:
            message = f"{base}: request timed out"
            errors.append(message)

            logger.warning(
                "WEAO request timed out: %s",
                url,
            )

        except aiohttp.ClientError as exc:
            message = f"{base}: {exc}"
            errors.append(message)

            logger.warning(
                "WEAO request failed: %s",
                message,
            )

        except Exception as exc:
            message = f"{base}: unexpected error ({exc})"
            errors.append(message)

            logger.exception(
                "Unexpected error while requesting %s",
                url,
            )

    details = " | ".join(errors)

    raise RuntimeError(
        f"Could not reach any WEAO domain for {path}. "
        f"{details}"
    )


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _load_json_file(path: Path) -> dict[str, Any]:
    """Safely load a JSON object from disk."""
    ensure_data_dir()

    if not path.exists():
        return {}

    try:
        data = json.loads(
            path.read_text(encoding="utf-8")
        )

        if isinstance(data, dict):
            return data

        logger.warning(
            "Expected JSON object in %s",
            path,
        )

    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "Failed to load %s: %s",
            path,
            exc,
        )

    return {}


def _save_json_file(
    path: Path,
    data: dict[str, Any],
) -> None:
    """Safely save a JSON object to disk."""
    ensure_data_dir()

    try:
        path.write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.error(
            "Failed to save %s: %s",
            path,
            exc,
        )


def load_cache() -> dict[str, Any]:
    """Load executor cache."""
    return _load_json_file(CACHE_FILE)


def save_cache(data: dict[str, Any]) -> None:
    """Save executor cache."""
    _save_json_file(CACHE_FILE, data)


def load_roblox_cache() -> dict[str, Any]:
    """Load Roblox version cache."""
    return _load_json_file(ROBLOX_CACHE_FILE)


def save_roblox_cache(data: dict[str, Any]) -> None:
    """Save Roblox version cache."""
    _save_json_file(ROBLOX_CACHE_FILE, data)


def _cache_is_fresh(
    cache: dict[str, Any],
    ttl: int,
) -> bool:
    """Return True when a cache object is still fresh."""
    timestamp = cache.get("timestamp")

    if not isinstance(timestamp, (int, float)):
        return False

    return (time.time() - timestamp) < ttl


# ---------------------------------------------------------------------------
# Executor API
# ---------------------------------------------------------------------------

async def fetch_all_executors(
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """
    Fetch all executor statuses.

    Uses the local cache unless force_refresh=True.
    """
    cache = load_cache()

    if not force_refresh and _cache_is_fresh(
        cache,
        EXECUTOR_CACHE_TTL,
    ):
        cached_data = cache.get("data")

        if isinstance(cached_data, list):
            logger.debug("Using cached executor data")
            return cached_data

    try:
        data = await _request("/api/status/exploits")

        if not isinstance(data, list):
            raise RuntimeError(
                "Unexpected response format from WEAO API"
            )

        # Keep only dictionary entries.
        executors = [
            item
            for item in data
            if isinstance(item, dict)
        ]

        save_cache(
            {
                "timestamp": time.time(),
                "data": executors,
            }
        )

        return executors

    except Exception:
        # If the API fails, attempt to use stale cache.
        cached_data = cache.get("data")

        if isinstance(cached_data, list):
            logger.warning(
                "WEAO API unavailable; using stale executor cache"
            )
            return cached_data

        raise


async def fetch_executor(
    name: str,
    force_refresh: bool = False,
) -> dict[str, Any] | None:
    """
    Fetch a specific executor.

    The API endpoint is attempted first. If it fails,
    the cached/full executor list is searched.
    """
    name = str(name).strip()

    if not name:
        return None

    # Try the direct endpoint first.
    if not force_refresh:
        try:
            data = await _request(
                f"/api/status/exploits/{name}"
            )

            if (
                isinstance(data, dict)
                and data.get("title")
            ):
                return data

        except Exception as exc:
            logger.debug(
                "Direct executor lookup failed for %r: %s",
                name,
                exc,
            )

    # Fallback to complete list.
    data = await fetch_all_executors(
        force_refresh=force_refresh
    )

    name_lower = name.lower().replace(" ", "")

    for executor in data:
        title = executor.get("title", "")

        if not isinstance(title, str):
            continue

        title_lower = title.lower()

        if (
            title_lower == name.lower()
            or title_lower.replace(" ", "") == name_lower
        ):
            return executor

    return None


# ---------------------------------------------------------------------------
# Roblox version API
# ---------------------------------------------------------------------------

async def fetch_roblox_version(
    kind: str,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    Fetch Roblox version information.

    kind:
        current
        future
        past
    """
    kind = validate_kind(
        kind,
        VALID_VERSION_KINDS,
        "version",
    )

    cache = load_roblox_cache()

    if not force_refresh and _cache_is_fresh(
        cache,
        ROBLOX_CACHE_TTL,
    ):
        cached_data = cache.get(kind)

        if isinstance(cached_data, dict):
            logger.debug(
                "Using cached Roblox %s version data",
                kind,
            )
            return cached_data

    try:
        data = await _request(
            f"/api/versions/{kind}"
        )

        if not isinstance(data, dict):
            raise RuntimeError(
                "Unexpected response format from WEAO API"
            )

        cache[kind] = data
        cache["timestamp"] = time.time()

        save_roblox_cache(cache)

        return data

    except Exception:
        # Use stale cache if available.
        cached_data = cache.get(kind)

        if isinstance(cached_data, dict):
            logger.warning(
                "WEAO API unavailable; using stale Roblox %s cache",
                kind,
            )
            return cached_data

        raise


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

def load_alerts() -> dict[str, Any]:
    """Load alert channel configuration."""
    return _load_json_file(ALERTS_FILE)


def save_alerts(data: dict[str, Any]) -> None:
    """Save alert channel configuration."""
    _save_json_file(ALERTS_FILE, data)


def set_alert_channel(
    guild_id: int,
    kind: str,
    channel_id: int | None,
) -> None:
    """
    Configure an alert channel.

    kind:
        executor
        roblox

    Passing channel_id=None removes/disables the channel.
    """
    kind = validate_kind(
        kind,
        VALID_ALERT_KINDS,
        "alert",
    )

    data = load_alerts()
    guild_key = str(guild_id)

    if guild_key not in data:
        data[guild_key] = {}

    data[guild_key][kind] = channel_id

    save_alerts(data)


def get_alert_channel(
    guild_id: int,
    kind: str,
) -> int | None:
    """Return the configured alert channel for a guild."""
    kind = validate_kind(
        kind,
        VALID_ALERT_KINDS,
        "alert",
    )

    data = load_alerts()

    value = data.get(
        str(guild_id),
        {},
    ).get(kind)

    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid channel ID for guild %s / %s: %r",
            guild_id,
            kind,
            value,
        )
        return None


def get_all_alert_channels(
    kind: str,
) -> list[tuple[int, int]]:
    """
    Return all configured alert channels.

    Returns:
        list of (guild_id, channel_id)
    """
    kind = validate_kind(
        kind,
        VALID_ALERT_KINDS,
        "alert",
    )

    data = load_alerts()
    result: list[tuple[int, int]] = []

    for guild_id, config in data.items():
        if not isinstance(config, dict):
            continue

        channel_id = config.get(kind)

        if channel_id is None:
            continue

        try:
            result.append(
                (
                    int(guild_id),
                    int(channel_id),
                )
            )
        except (TypeError, ValueError):
            logger.warning(
                "Invalid alert configuration: guild=%r channel=%r",
                guild_id,
                channel_id,
            )

    return result


# ---------------------------------------------------------------------------
# Executor helpers
# ---------------------------------------------------------------------------

def _type_label(exe: dict[str, Any]) -> str:
    """Determine whether an executor is Internal or External."""
    extype = exe.get("extype")

    if isinstance(extype, str):
        extype_lower = extype.lower().strip()

        if "external" in extype_lower:
            return "External"

        if "internal" in extype_lower:
            return "Internal"

    title = exe.get("title")

    if isinstance(title, str):
        if "external" in title.lower():
            return "External"

    return "Internal"


# ---------------------------------------------------------------------------
# Discord buttons
# ---------------------------------------------------------------------------

class ExecutorView(View):
    """Buttons for an executor embed."""

    def __init__(
        self,
        website: str | None = None,
        discord_url: str | None = None,
        purchase: str | None = None,
    ):
        super().__init__(timeout=None)

        if valid_url(website):
            self.add_item(
                Button(
                    label="Website",
                    url=website,
                    style=discord.ButtonStyle.link,
                )
            )

        if valid_url(discord_url):
            self.add_item(
                Button(
                    label="Discord",
                    url=discord_url,
                    style=discord.ButtonStyle.link,
                )
            )

        if valid_url(purchase):
            self.add_item(
                Button(
                    label="Purchase",
                    url=purchase,
                    style=discord.ButtonStyle.link,
                )
            )


# ---------------------------------------------------------------------------
# Executor embed
# ---------------------------------------------------------------------------

def build_executor_embed(
    exe: dict[str, Any],
) -> tuple[discord.Embed, ExecutorView | None]:
    """Build a Discord embed from WEAO executor data."""

    title = truncate(
        exe.get("title", "Unknown"),
        256,
    )

    version = truncate(
        exe.get("version", "N/A"),
        100,
    )

    updated = truncate(
        exe.get("updatedDate", "Unknown"),
        1024,
    )

    free = bool(exe.get("free", False))
    detected = bool(exe.get("detected", False))
    updated_status = bool(exe.get("updateStatus", False))

    platform = truncate(
        exe.get("platform", "Unknown"),
        1024,
    )

    cost = exe.get("cost")

    if not cost:
        cost = "Free" if free else "Paid"

    cost = truncate(cost, 1024)

    unc = exe.get("uncPercentage")
    sunc = exe.get("suncPercentage")

    decompiler = bool(
        exe.get("decompiler", False)
    )

    multi_inject = bool(
        exe.get("multiInject", False)
    )

    website = exe.get("websitelink")
    discord_link = exe.get("discordlink")
    purchase = exe.get("purchaselink")

    rbx_version = truncate(
        exe.get("rbxversion", "N/A"),
        1024,
    )

    # -----------------------------------------------------------------------
    # Metadata
    # -----------------------------------------------------------------------

    logo: str | None = None
    description: str | None = None

    slug = exe.get("slug")

    if isinstance(slug, dict):
        raw_logo = slug.get("logo")
        raw_description = slug.get("fullDescription")

        if valid_url(raw_logo):
            logo = raw_logo

        if isinstance(raw_description, str):
            description = raw_description.strip()

    # -----------------------------------------------------------------------
    # Embed color
    # -----------------------------------------------------------------------

    if detected:
        color = discord.Color.orange()
    elif updated_status:
        color = discord.Color.green()
    else:
        color = discord.Color.red()

    embed = discord.Embed(
        title=f"{title} • v{version}",
        color=color,
        timestamp=discord.utils.utcnow(),
    )

    # -----------------------------------------------------------------------
    # Basic information
    # -----------------------------------------------------------------------

    status_text = (
        "Updated"
        if updated_status
        else "Not Updated"
    )

    detection_text = (
        "Detected"
        if detected
        else "Undetected"
    )

    price_text = (
        "Free"
        if free
        else cost
    )

    executor_type = _type_label(exe)

    embed.add_field(
        name="Status",
        value=status_text,
        inline=True,
    )

    embed.add_field(
        name="Detection",
        value=detection_text,
        inline=True,
    )

    embed.add_field(
        name="Price",
        value=price_text,
        inline=True,
    )

    embed.add_field(
        name="Platform",
        value=platform,
        inline=True,
    )

    embed.add_field(
        name="Type",
        value=executor_type,
        inline=True,
    )

    embed.add_field(
        name="Last Updated",
        value=updated,
        inline=True,
    )

    embed.add_field(
        name="Roblox Version",
        value=f"`{rbx_version}`",
        inline=True,
    )

    # -----------------------------------------------------------------------
    # Features
    # -----------------------------------------------------------------------

    features: list[str] = []

    if decompiler:
        features.append("Decompiler")

    if multi_inject:
        features.append("Multi-Inject")

    if exe.get("clientmods"):
        features.append("Client Mods")

    if exe.get("raknet"):
        features.append("RakNet")

    if features:
        embed.add_field(
            name="Features",
            value=", ".join(features)[:1024],
            inline=False,
        )

    # -----------------------------------------------------------------------
    # Compatibility
    # -----------------------------------------------------------------------

    scores: list[str] = []

    if unc is not None:
        scores.append(
            f"UNC: **{truncate(unc, 50)}%**"
        )

    if sunc is not None:
        scores.append(
            f"sUNC: **{truncate(sunc, 50)}%**"
        )

    if scores:
        embed.add_field(
            name="Compatibility",
            value=" • ".join(scores)[:1024],
            inline=False,
        )

    # -----------------------------------------------------------------------
    # Description
    # -----------------------------------------------------------------------

    if description:
        description = truncate(
            description,
            900,
        )

        embed.add_field(
            name="Description",
            value=description,
            inline=False,
        )

    # -----------------------------------------------------------------------
    # Logo
    # -----------------------------------------------------------------------

    if logo:
        embed.set_thumbnail(url=logo)

    # -----------------------------------------------------------------------
    # Footer
    # -----------------------------------------------------------------------

    embed.set_footer(
        text="Powered by WEAO"
    )

    # -----------------------------------------------------------------------
    # Buttons
    # -----------------------------------------------------------------------

    view: ExecutorView | None = None

    if (
        valid_url(website)
        or valid_url(discord_link)
        or valid_url(purchase)
    ):
        view = ExecutorView(
            website=website,
            discord_url=discord_link,
            purchase=purchase,
        )

    return embed, view


# ---------------------------------------------------------------------------
# Roblox embed
# ---------------------------------------------------------------------------

def build_roblox_embed(
    kind: str,
    data: dict[str, Any],
) -> discord.Embed:
    """Build a Discord embed for Roblox version information."""

    kind = validate_kind(
        kind,
        VALID_VERSION_KINDS,
        "version",
    )

    titles = {
        "current": "Roblox Versions — Current",
        "future": "Roblox Versions — Future",
        "past": "Roblox Versions — Past",
    }

    embed = discord.Embed(
        title=titles[kind],
        color=discord.Color.blurple(),
        timestamp=discord.utils.utcnow(),
    )

    platforms = (
        "Windows",
        "Mac",
        "Android",
        "iOS",
    )

    for platform in platforms:
        version = data.get(platform)
        date = data.get(
            f"{platform}Date"
        )

        if version is None:
            continue

        version_text = truncate(
            version,
            1000,
        )

        value = f"`{version_text}`"

        if date:
            value += f"\n{truncate(date, 100)}"

        embed.add_field(
            name=platform,
            value=value[:1024],
            inline=True,
        )

    embed.set_footer(
        text="Data from WEAO"
    )

    return embed
