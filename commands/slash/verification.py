"""
Slash commands for the server verification system.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from commands.prefix.verification import (
    load_config,
    save_config,
    get_guild_config,
    VerifyButton,
    CaptchaStartView,
)


class VerificationSlash(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setupverify", description="Configure the verification system")
    @app_commands.describe(
        method="Verification method",
        role="Role given after verification",
        log_channel="Optional log channel",
    )
    @app_commands.choices(method=[
        app_commands.Choice(name="Button", value="button"),
        app_commands.Choice(name="Reaction", value="reaction"),
        app_commands.Choice(name="Captcha", value="captcha"),
    ])
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def setup_verify(
        self,
        interaction: discord.Interaction,
        method: app_commands.Choice[str],
        role: discord.Role,
        log_channel: discord.TextChannel = None,
    ):
        config = load_config()
        guild_id = str(interaction.guild_id)

        config[guild_id] = {
            "method": method.value,
            "verified_role_id": role.id,
            "log_channel_id": log_channel.id if log_channel else None,
            "reaction_emoji": "✅",
            "panel_message_id": None,
            "panel_channel_id": None,
        }
        save_config(config)

        embed = discord.Embed(
            title="Verification Configured",
            color=discord.Color.green(),
            description=(
                f"**Method:** {method.value}\n"
                f"**Role:** {role.mention}\n"
                f"**Log channel:** {log_channel.mention if log_channel else 'Not set'}"
            ),
        )
        embed.add_field(
            name="Next step",
            value="Run `/sendverify` in the channel where you want the panel.",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="sendverify", description="Send the verification panel")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def send_verify(self, interaction: discord.Interaction):
        cfg = get_guild_config(interaction.guild_id)
        if not cfg or not cfg.get("verified_role_id"):
            await interaction.response.send_message(
                "Verification is not configured yet.\nUse `/setupverify` first.",
                ephemeral=True,
            )
            return

        method = cfg.get("method", "button")

        if method == "button":
            embed = discord.Embed(
                title="Server Verification",
                description=(
                    "Click the **Verify** button below to gain access to the server.\n\n"
                    "By verifying, you confirm that you have read and agree to the server rules."
                ),
                color=discord.Color.blurple(),
            )
            embed.set_footer(text="Verification System • Button")
            await interaction.response.send_message(embed=embed, view=VerifyButton())

        elif method == "reaction":
            emoji = cfg.get("reaction_emoji", "✅")
            embed = discord.Embed(
                title="Server Verification",
                description=(
                    f"React with {emoji} to this message to gain access to the server.\n\n"
                    "By verifying, you confirm that you have read and agree to the server rules."
                ),
                color=discord.Color.blurple(),
            )
            embed.set_footer(text="Verification System • Reaction")
            await interaction.response.send_message(embed=embed)
            msg = await interaction.original_response()
            try:
                await msg.add_reaction(emoji)
            except Exception:
                await interaction.followup.send("Failed to add reaction.", ephemeral=True)
                return

            config = load_config()
            config[str(interaction.guild_id)]["panel_message_id"] = msg.id
            config[str(interaction.guild_id)]["panel_channel_id"] = msg.channel.id
            save_config(config)

        elif method == "captcha":
            embed = discord.Embed(
                title="Server Verification",
                description=(
                    "Click **Start Captcha** below and solve a short puzzle to gain access.\n\n"
                    "By verifying, you confirm that you have read and agree to the server rules."
                ),
                color=discord.Color.blurple(),
            )
            embed.set_footer(text="Verification System • Captcha")
            await interaction.response.send_message(embed=embed, view=CaptchaStartView())

        else:
            await interaction.response.send_message("Unknown method in config.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(VerificationSlash(bot))
